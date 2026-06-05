# 微信聊天档案 · WeChat Chat Archive

> **本地优先的微信聊天关系分析工具** — 解密、浏览、搜索、分析，全程在你自己的 Mac 上完成，数据不上传。

A local-first toolkit for decrypting, browsing, searching, and analyzing WeChat for macOS chat history — entirely on your own machine, zero uploads.

---

## 功能一览 · Features

- 🔓 **密钥提取** — 从微信进程内存中提取 SQLCipher 密钥
- 🗄️ **数据库解密** — 将加密数据库解密为本地 SQLite 快照
- 💬 **聊天浏览** — 支持文本、图片、语音时长、视频、链接、撤回等消息类型
- 🔍 **回忆搜索** — FTS 全文搜索 + 自动回退，跨全部联系人
- 📊 **关系报告** — 关系类型推断、互动维度、社交洞察、Markdown 导出
- 🗺️ **年度总览** — 消息量、最活跃联系人、年度热词、互动节奏
- 🤖 **AI 问答** — 用自己的 API Key 向 AI 提问，基于本地数据回答
- 🔒 **隐私安全** — 快照新鲜度、密钥安全检查、一键清理解密数据
- 🎭 **Demo 模式** — 无需真实数据即可体验所有功能
- 🖥️ **桌面启动器** — 双击即用，无需终端

---

## 快速体验 Demo · Try Without Real Data

```bash
# 1. 生成合成演示数据（虚构联系人和消息）
python3 generate_demo.py

# 2. 以 Demo 模式启动，浏览器自动打开
python3 web_server.py --demo
```

Demo 包含 6 段对话、248 条合成消息，覆盖所有消息类型和分析功能。

---

## 环境要求 · Requirements

- macOS（Apple Silicon 推荐）
- WeChat for macOS 4.x，已登录
- Python 3.9+
- [Homebrew](https://brew.sh/)

```bash
brew install llvm sqlcipher
```

---

## 使用步骤 · Quick Start

### 第一步：提取密钥

确保微信已打开并登录：

```bash
PYTHONPATH=$(lldb -P) python3 find_key_memscan.py
```

密钥写入 `wechat_keys.json`（已被 `.gitignore` 排除）。

> ⚠️ 部分系统可能需要临时关闭 SIP：`csrutil disable`，提取完成后重新开启。

### 第二步：解密数据库

```bash
python3 decrypt_db.py
```

解密文件写入 `decrypted/`（已被 `.gitignore` 排除）。

### 第三步：启动 Web UI

```bash
python3 web_server.py
```

打开 [http://127.0.0.1:8765](http://127.0.0.1:8765) 即可使用。

---

## 桌面启动器 · Desktop Launcher

非技术用户可直接双击：

```text
start_desktop.command   # 打开控制台（推荐）
start.command           # 直接打开 Web UI
```

详见 [普通用户使用说明.md](./普通用户使用说明.md)。

---

## AI 问答 · AI Q&A

Web UI 中的 **✦ AI** 视图支持向 AI 提问关于某段关系的任何问题。

- 支持 **Anthropic Claude** 和 **OpenAI**
- API Key 填写后保存在本地浏览器（`localStorage`），不存入服务端
- 发送给 AI 的内容：关系统计数据 + 最近 25 条文本消息，**不含图片/语音/文件原始数据**
- 所有分析在本机完成，只有你的问题和统计摘要会发给 AI

---

## 导出聊天记录 · Export

```bash
# 列出所有会话
python3 export_messages.py

# 导出单个联系人
python3 export_messages.py -c "Alice"
python3 export_messages.py -c wxid_xxx

# 关键词搜索
python3 export_messages.py -s "关键词"

# 导出全部
python3 export_messages.py --all
```

---

## 隐私与安全 · Privacy & Security

- **数据不离开本机** — Web UI 绑定在 `127.0.0.1`，默认不可被外部访问
- **密钥文件不进仓库** — `wechat_keys.json`、`decrypted/`、`exported/` 均在 `.gitignore` 中
- **一键清理** — Web UI「隐私」页面支持一键删除所有解密数据库
- **公开前检查** — 不要提交密钥、解密数据库、导出文件或真实聊天截图

详见 [SECURITY.md](./SECURITY.md) 和 [DISCLAIMER.md](./DISCLAIMER.md)。

---

## 项目结构 · Project Structure

```text
wechat-db-decrypt-macos/
├── find_key_memscan.py   # 密钥提取（内存扫描）
├── decrypt_db.py         # 数据库解密
├── wechat_data.py        # 数据查询核心
├── web_server.py         # Web UI 服务器
├── generate_demo.py      # Demo 数据生成器
├── export_messages.py    # 命令行导出工具
├── mcp_server.py         # MCP 工具服务器
├── desktop_launcher.py   # 桌面启动器
├── web/                  # 前端（纯 HTML/CSS/JS）
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── tests/                # 单元测试
└── 普通用户使用说明.md
```

---

## 注意事项 · Disclaimer

本工具仅用于访问**你自己**授权访问的数据。请勿用于访问、监控或导出他人聊天记录。

This tool is intended only for data you are authorized to access. Do not use it to access, monitor, or export anyone else's conversations without their consent.

详见 [DISCLAIMER.md](./DISCLAIMER.md)。

---

## License

MIT
