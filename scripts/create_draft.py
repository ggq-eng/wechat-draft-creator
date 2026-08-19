#!/usr/bin/env python3
"""通过微信官方API创建公众号图文草稿。

用法:
  python3 create_draft.py --appid APPID --secret SECRET --title "标题" --content "正文HTML"

可选参数:
  --author "作者名"        默认空，不超过16字节
  --digest "摘要"          默认取正文前54字
  --cover-url "封面图URL"  自动上传为永久素材
  --no-comment             关闭评论
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

def get_token(appid: str, secret: str) -> str:
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={appid}&secret={secret}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read())
        if "access_token" not in data:
            raise RuntimeError(f"获取token失败: {data}")
        return data["access_token"]

def upload_cover(token: str, image_url: str) -> str:
    """下载远程图片并上传为微信永久素材，返回media_id"""
    # 下载图片
    req = urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        img_data = resp.read()

    # multipart上传
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body_parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"type\"\r\n\r\nimage\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"media\"; filename=\"cover.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n".encode(),
        img_data,
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    body = b"".join(body_parts)

    req = urllib.request.Request(
        f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
        if "media_id" not in data:
            raise RuntimeError(f"封面上传失败: {data}")
        return data["media_id"]

def create_draft(
    token: str,
    title: str,
    content: str,
    thumb_media_id: str,
    author: str = "",
    digest: str = "",
    open_comment: bool = True,
) -> str:
    articles = [
        {
            "title": title[:32],
            "content": content,
            "thumb_media_id": thumb_media_id,
            "need_open_comment": 1 if open_comment else 0,
            "only_fans_can_comment": 0,
        }
    ]
    if author:
        articles[0]["author"] = author[:16]
    if digest:
        articles[0]["digest"] = digest[:128]

    body = json.dumps({"articles": articles}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
        if "media_id" not in data:
            raise RuntimeError(f"创建草稿失败: {data}")
        return data["media_id"]


def main() -> int:
    parser = argparse.ArgumentParser(description="通过微信API创建公众号草稿")
    parser.add_argument("--appid", required=True, help="公众号AppID")
    parser.add_argument("--secret", required=True, help="公众号AppSecret")
    parser.add_argument("--title", required=True, help="文章标题（不超过32字）")
    parser.add_argument("--content", required=True, help="正文HTML内容")
    parser.add_argument("--author", default="", help="作者名（不超过16字节）")
    parser.add_argument("--digest", default="", help="摘要（不超过128字）")
    parser.add_argument("--cover-url", default="", help="封面图URL，将自动上传")
    parser.add_argument("--no-comment", action="store_true", help="关闭评论")
    args = parser.parse_args()

    print("1/3 获取 access_token...", file=sys.stderr)
    token = get_token(args.appid, args.secret)
    print(f"   ✅ token获取成功", file=sys.stderr)

    print("2/3 上传封面图...", file=sys.stderr)
    if args.cover_url:
        thumb_id = upload_cover(token, args.cover_url)
        print(f"   ✅ 封面上传成功", file=sys.stderr)
    else:
        # 使用一个默认占位图或空media_id
        # 注意：draft/add要求thumb_media_id必填
        print("   ⚠️ 未提供封面图URL，尝试使用空白封面", file=sys.stderr)
        thumb_id = ""

    if not thumb_id:
        print("   ❌ 需要有效的封面图media_id", file=sys.stderr)
        return 1

    print("3/3 创建草稿...", file=sys.stderr)
    media_id = create_draft(
        token=token,
        title=args.title,
        content=args.content,
        thumb_media_id=thumb_id,
        author=args.author,
        digest=args.digest,
        open_comment=not args.no_comment,
    )
    print(f"   ✅ 草稿创建成功！", file=sys.stderr)
    print(f"   media_id: {media_id}", file=sys.stderr)

    # 输出JSON供其他脚本使用
    print(json.dumps({"ok": True, "media_id": media_id}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
