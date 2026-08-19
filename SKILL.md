---
name: wechat-draft-creator
description: 通过微信官方 API 创建公众号图文草稿。用 AppID + AppSecret 获取 token，上传封面图，创建草稿到草稿箱。适用于需要自动将文章推送到微信公众号草稿箱的场景。
---

# WeChat Draft Creator

通过微信官方 API 将文章自动创建为公众号草稿。

## 前置条件

- AppID + AppSecret（公众号开发者凭据）
- IP 白名单已配置（在 mp.weixin.qq.com → 设置与开发 → 基本配置 → IP白名单 中添加）

## 关键 API 端点

| 操作 | 端点 | 方法 |
|------|------|------|
| 获取 token | `/cgi-bin/token?grant_type=client_credential&appid=APPID&secret=SECRET` | GET |
| 上传封面图 | `/cgi-bin/material/add_material?access_token=TOKEN` | POST (multipart) |
| 创建草稿 | `/cgi-bin/draft/add?access_token=TOKEN` | POST (JSON) |

⚠️ 注意：订阅号使用 `/cgi-bin/draft/add`，不要用 `/cgi-bin/draft/create`

## 工作流

### Step 1: 获取 access_token

```bash
python3 -c "
import urllib.request, json
appid = '你的AppID'
secret = '你的AppSecret'
with urllib.request.urlopen(f'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={appid}&secret={secret}') as resp:
    data = json.loads(resp.read())
    token = data['access_token']
    print(token)
"
```

token 有效期 2 小时，需要定时刷新。

### Step 2: 上传封面图（可选，但推荐）

封面图需要先上传为永久素材，拿到 `media_id`：

```python
import urllib.request, json
# 下载图片二进制数据
img_url = 'https://...'  # 封面图URL
req_dl = urllib.request.Request(img_url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req_dl) as resp:
    img_data = resp.read()

# multipart 上传到微信
boundary = '----Boundary'
body = (
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name=\"type\"\r\n\r\nimage\r\n'
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name=\"media\"; filename=\"cover.jpg\"\r\n'
    f'Content-Type: image/jpeg\r\n\r\n'
).encode() + img_data + f'\r\n--{boundary}--\r\n'.encode()

req = urllib.request.Request(
    f'https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}',
    data=body,
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
)
with urllib.request.urlopen(req, timeout=30) as resp:
    upload = json.loads(resp.read())
    thumb_id = upload['media_id']
```

### Step 3: 创建草稿

```bash
python3 -c "
import urllib.request, json

token = '你的TOKEN'
thumb_id = '你的封面media_id'

draft = {
    'articles': [{
        'title': '文章标题（不超过32字）',
        'author': '作者名（不超过16字节，中文3字节/字）',
        'digest': '摘要（不超过128字）',
        'content': '<section><p>正文HTML内容</p></section>',
        'thumb_media_id': thumb_id,       # 必填！封面图media_id
        'need_open_comment': 1,           # 1=打开评论
        'only_fans_can_comment': 0,       # 0=所有人可评论
        'show_cover_pic': 1              # 1=封面显示在正文中
    }]
}
req = urllib.request.Request(
    f'https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}',
    data=json.dumps(draft).encode(),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read())
    print(data)  # {'media_id': 'xxx'} 表示成功
"
```

## 常见错误

| 错误码 | 含义 | 解决 |
|--------|------|------|
| 40007 | invalid media_id | `thumb_media_id` 必填或填错了 |
| 40066 | invalid url | 用了错误的 API 端点，改用 `/cgi-bin/draft/add` |
| 45110 | author size out of limit | 作者名超过16字节，中文占3字节，请缩短 |
| 40164 | invalid ip not in whitelist | 需要在公众号后台添加当前IP到白名单 |
| 48001 | api unauthorized | 该号没有此API权限（常见于未认证订阅号） |
| 40008 | invalid message type | content 格式有问题 |

## 内容 HTML 规范

- content 为 HTML 格式，大小不超过 2KB
- 图片必须使用「上传图文消息内的图片」接口获取的 URL（即 `media/uploadimg`）
- 外部图片 URL 会被过滤
- 支持 `<section>`、`<p>`、`<span>`、`<img>` 等常用标签
- 不支持 JS 脚本

## 完整 Python 脚本

见 `scripts/create_draft.py`，一键执行：
```bash
python3 {baseDir}/scripts/create_draft.py --appid APPID --secret SECRET --title "标题" --content "内容"
```
