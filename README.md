# wechat-draft-creator

> 来源分类：**待确认** ｜ 导出批次：review

通过微信官方 API 创建公众号图文草稿。用 AppID + AppSecret 获取 token，上传封面图，创建草稿到草稿箱。适用于需要自动将文章推送到微信公众号草稿箱的场景。

## 安装

把本文件夹整体复制到 WorkBuddy 技能目录：

```bash
cp -r . ~/.workbuddy/skills/wechat-draft-creator        # 用户级
# 或
cp -r . <项目>/.workbuddy/skills/wechat-draft-creator   # 项目级
```

重启/刷新 WorkBuddy 后即可在对话中触发。

## 说明

- 本技能从本地 WorkBuddy 环境导出，**所有真实密钥已脱敏为占位符**，使用前请配置你自己的 API Key。
- 若来自技能市场（文件夹名以 `__skillhub` 结尾），版权归原作者，请遵守其许可证。
