#!/usr/bin/env python3
"""微信公众号图文草稿一键发布（处理本地配图 + 封面）。

解决原 create_draft.py 的两点不足：
  1. 只支持远程封面 URL；本脚本支持本地封面文件直接上传为永久素材。
  2. 不处理正文内的本地配图（会导致裂图）；本脚本自动把正文里的
     本地图片经 media/uploadimg 上传到微信 CDN，替换 src。

自动压缩：正文图 > 1MB、封面 > 2MB 时自动转 JPEG 压缩（微信接口硬上限）。

用法:
  python publish_article.py \
      --html 4-formatted.html \
      --cover 3-cover/cover.png \
      --title "文章标题" \
      [--author "作者"] [--digest "摘要"] \
      [--config ~/.workbuddy/wechat_credentials.json]

凭据默认从 config 读取（appid/secret），也可用 --appid/--secret 覆盖。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from io import BytesIO
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None

DEFAULT_CONFIG = r"C:\Users\Administrator\.workbuddy\wechat_credentials.json"

UPLOADIMG_URL = "https://api.weixin.qq.com/cgi-bin/media/uploadimg"
ADD_MATERIAL_URL = "https://api.weixin.qq.com/cgi-bin/material/add_material"
DRAFT_ADD_URL = "https://api.weixin.qq.com/cgi-bin/draft/add"

MAX_BODY_BYTES = 1_000_000      # media/uploadimg 上限 ~1MB
MAX_COVER_BYTES = 2_000_000     # material/add_material(image) 上限 2MB
RESIZE_MAX_W = 1280
JPEG_QUALITY = 82


def _multipart(field_name: str, filename: str, data: bytes, mime: str) -> tuple[bytes, str]:
    boundary = "----WbPublishBoundary7MA4YWxkTrZu0gW"
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode()
    tail = f"\r\n--{boundary}--\r\n".encode()
    return head + data + tail, f"multipart/form-data; boundary={boundary}"


def _post(url: str, body: bytes, ctype: str) -> dict:
    req = urllib.request.Request(url, data=body, headers={"Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def get_token(appid: str, secret: str) -> str:
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={appid}&secret={secret}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        d = json.loads(resp.read())
    if "access_token" not in d:
        raise RuntimeError(f"获取 token 失败: {d}")
    return d["access_token"]


def compress_image(path: Path, limit_bytes: int) -> tuple[bytes, str]:
    """如需压缩则转 JPEG 返回 (bytes, ext)；否则原样返回。"""
    raw = path.read_bytes()
    if len(raw) <= limit_bytes:
        return raw, path.suffix.lstrip(".").lower() or "png"
    if Image is None:
        raise RuntimeError(f"图片 {path.name} 超 {limit_bytes//1000}KB 且未安装 Pillow，无法压缩")
    img = Image.open(path).convert("RGB")
    w, h = img.size
    if w > RESIZE_MAX_W:
        h = int(h * RESIZE_MAX_W / w)
        img = img.resize((RESIZE_MAX_W, h))
    buf = BytesIO()
    q = JPEG_QUALITY
    while True:
        buf.seek(0)
        buf.truncate()
        img.save(buf, format="JPEG", quality=q)
        if buf.tell() <= limit_bytes or q <= 30:
            break
        q -= 10
    return buf.getvalue(), "jpg"


def upload_body_image(token: str, path: Path) -> str:
    data, ext = compress_image(path, MAX_BODY_BYTES)
    mime = "image/jpeg" if ext == "jpg" else f"image/{ext}"
    if ext == "jpg":
        ext = "jpg"
    body, ctype = _multipart("media", f"{path.stem}.{ext}", data, mime)
    d = _post(f"{UPLOADIMG_URL}?access_token={token}", body, ctype)
    if "url" not in d:
        raise RuntimeError(f"正文配图上传失败 {path.name}: {d}")
    return d["url"]


def upload_cover(token: str, path: Path) -> str:
    data, ext = compress_image(path, MAX_COVER_BYTES)
    mime = "image/jpeg" if ext == "jpg" else f"image/{ext}"
    body, ctype = _multipart("media", f"{path.stem}.{ext}", data, mime)
    d = _post(f"{ADD_MATERIAL_URL}?access_token={token}&type=image", body, ctype)
    if "media_id" not in d:
        raise RuntimeError(f"封面上传失败: {d}")
    return d["media_id"]


def replace_local_imgs(html: str, base: Path, token: str, log) -> str:
    imgs = re.findall(r'<img[^>]+src="([^"]+)"', html)
    for src in imgs:
        if src.startswith("http://") or src.startswith("https://"):
            continue
        p = (base / src).resolve()
        if not p.exists():
            log(f"   ⚠️ 本地图片不存在，跳过: {src}")
            continue
        url = upload_body_image(token, p)
        html = html.replace(f'src="{src}"', f'src="{url}"', 1)
        log(f"   ✅ 已上传并替换: {src}")
    return html


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--appid", default="")
    ap.add_argument("--secret", default="")
    ap.add_argument("--html", required=True, help="正文 HTML 文件路径")
    ap.add_argument("--cover", required=True, help="封面图本地路径")
    ap.add_argument("--title", required=True)
    ap.add_argument("--author", default="")
    ap.add_argument("--digest", default="")
    args = ap.parse_args()

    # 凭据
    appid, secret = args.appid, args.secret
    if not appid or not secret:
        cfg = json.load(open(args.config, encoding="utf-8"))
        appid = appid or cfg["appid"]
        secret = secret or cfg["secret"]

    html_path = Path(args.html).resolve()
    base = html_path.parent
    cover_path = Path(args.cover).resolve()

    print("1/4 获取 access_token ...", file=sys.stderr)
    token = get_token(appid, secret)
    print("   ✅ token 获取成功", file=sys.stderr)

    print("2/4 上传正文配图 ...", file=sys.stderr)
    html = html_path.read_text(encoding="utf-8")
    html = replace_local_imgs(html, base, token, lambda m: print("   " + m, file=sys.stderr))

    print("3/4 上传封面 ...", file=sys.stderr)
    if not cover_path.exists():
        print(f"   ❌ 封面不存在: {cover_path}", file=sys.stderr)
        return 1
    thumb_id = upload_cover(token, cover_path)
    print("   ✅ 封面上传成功", file=sys.stderr)

    print("4/4 创建草稿 ...", file=sys.stderr)
    articles = [{
        "title": args.title,
        "content": html,
        "thumb_media_id": thumb_id,
        "need_open_comment": 1,
        "only_fans_can_comment": 0,
        "show_cover_pic": 1,
    }]
    if args.author:
        articles[0]["author"] = args.author[:16]
    if args.digest:
        articles[0]["digest"] = args.digest[:128]
    body = json.dumps({"articles": articles}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{DRAFT_ADD_URL}?access_token={token}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        d = json.loads(resp.read())
    if "media_id" not in d:
        raise RuntimeError(f"创建草稿失败: {d}")
    print(f"   ✅ 草稿创建成功！media_id: {d['media_id']}", file=sys.stderr)
    print(json.dumps({"ok": True, "media_id": d["media_id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
