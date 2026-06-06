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
- 🤖 **AI 关系深度报告** — 用自己的 API Key，让大模型读真实对话，生成结构化关系分析报告
- 🔒 **隐私安全** — 快照新鲜度、密钥安全检查、一键清理解密数据、发布前安全检查脚本
- 🎭 **Demo 模式** — 无需真实数据即可体验所有功能
- 🖥️ **桌面启动器** — 双击即用，无需终端

---

## 快速体验 Demo · Try Without Real Data

**不需要真实微信数据**，可以先用合成数据体验所有功能：

```bash
# 克隆项目
git clone https://github.com/stvictor-ai/wechat-db-decrypt-macos.git
cd wechat-db-decrypt-macos

# 生成演示数据（6 段对话、248 条合成消息，覆盖所有消息类型）
python3 generate_demo.py

# 以 Demo 模式启动，浏览器自动打开
python3 web_server.py --demo
```

浏览器会自动打开 [http://127.0.0.1:8765](http://127.0.0.1:8765)，顶部会显示橙色「演示模式」提示条。

---

## 环境要求 · Requirements

- **macOS**（Apple Silicon / Intel 均支持）
- **WeChat for macOS 4.x**，使用时需保持登录状态
- **Python 3.9+**（系统自带或通过 Homebrew 安装）
- **Homebrew**（用于安装 sqlcipher）

安装依赖：

```bash
brew install llvm sqlcipher
```

> 项目只使用 Python 标准库，不需要 `pip install` 任何第三方包。

---

## 使用步骤 · Quick Start

### 第一步：提取密钥

确保微信已打开并登录，然后运行：

```bash
PYTHONPATH=$(lldb -P) python3 find_key_memscan.py
```

成功后会输出类似：

```text
[+] 找到密钥：xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
[+] 已写入 wechat_keys.json
```

密钥保存在 `wechat_keys.json`，该文件已被 `.gitignore` 排除，**不会被提交到 Git**。

> ⚠️ **如果提示权限错误**：部分系统需要临时关闭 SIP（系统完整性保护）。
> 重启 Mac 时按住电源键进入恢复模式，在终端执行 `csrutil disable`，提取完成后**务必重新开启** `csrutil enable`。

---

### 第二步：解密数据库

```bash
python3 decrypt_db.py
```

脚本会自动找到微信数据库并解密，输出类似：

```text
[+] 解密 contact.db ... OK
[+] 解密 message_0.db ... OK
[+] 解密 session.db ... OK
...
[+] 共解密 12 个数据库，写入 decrypted/
```

解密文件保存在 `decrypted/` 目录，已被 `.gitignore` 排除。

---

### 第三步：启动 Web UI

```bash
python3 web_server.py
```

打开浏览器访问 [http://127.0.0.1:8765](http://127.0.0.1:8765)。

左侧联系人列表加载完成后即可开始使用。

---

## 桌面启动器 · Desktop Launcher

不熟悉终端的用户可以直接双击文件启动：

```text
start_desktop.command   # 打开日志控制台（推荐，方便查看状态）
start.command           # 直接打开 Web UI
```

首次使用需要在 Finder 中右键点击 → 「打开」，之后可以直接双击。

详见 [普通用户使用说明.md](./普通用户使用说明.md)。

---

## AI 关系深度报告 · AI Report

这是本工具的核心 AI 功能。配置好 API Key 后，AI 会**真正读取你们的聊天内容**（而非仅统计数据），生成一份有深度的关系分析报告。

### 配置 API Key

在 Web UI 顶部导航栏点击 **✦ AI**，在配置区填入 API Key：

- **Anthropic Claude**：前往 [console.anthropic.com](https://console.anthropic.com) 创建 API Key（格式：`sk-ant-...`）
- **OpenAI**：前往 [platform.openai.com](https://platform.openai.com) 创建 API Key（格式：`sk-...`）

填写后点击「保存」，Key 仅存储在本地浏览器（`localStorage`），**不会发送到本项目服务端**。

### 生成关系报告

1. 在左侧选择一个联系人
2. 选择消息采样量：**50 / 100 / 200 / 500 条**（越多分析越深，费用也更高）
3. 点击「生成关系报告」，等待 15–30 秒

报告包含以下六个章节：

| 章节 | 内容 |
|------|------|
| 关系判断 | 关系类型、亲密程度、整体健康度 |
| 互动动态 | 谁更主动、话语权分布、情感基调 |
| 话题图谱 | 主要聊什么、关键词背后的关系信号 |
| 关系走势 | 升温还是降温，有无明显转折点或沉默期 |
| 深层洞察 | 最值得注意的一点，附具体消息证据 |
| 给你的建议 | 改善或维护这段关系最重要的一件事 |

### 消息采样说明

为了让 AI 看到关系的**完整脉络**（而不只是最近的内容），系统会按时间段采样：

- 早期（关系开始阶段）：25%
- 中期（关系发展阶段）：25%
- 近期（最近互动）：50%

### 追问

报告生成后，可在下方输入框继续追问，例如：

- 「为什么感觉最近疏远了？」
- 「这段关系值得继续维护吗？」
- 「我们的关系有没有什么隐患？」

### 费用参考（约）

| 采样量 | Anthropic Haiku | OpenAI GPT-4o mini |
|--------|----------------|-------------------|
| 100 条 | ~$0.01 | ~$0.01 |
| 200 条 | ~$0.02 | ~$0.02 |
| 500 条 | ~$0.05 | ~$0.05 |

---

## 回忆搜索 · Memory Search

点击导航栏「回忆」，在搜索框输入关键词，系统会在**所有联系人**的聊天记录中搜索，显示匹配片段和上下文。

适合找：约定时间、地址、文件名、某段对话、某个突然想起的词。

---

## 关系报告 · Relationship Report

点击导航栏「报告」并选择联系人，系统会生成一份基于统计数据的关系画像：

- 关系类型推断（工作、朋友、家人等）
- 6 个互动维度评分
- 5 条社交洞察
- 消息类型分布、活跃时段、高频词

可以点击「导出报告」保存为 Markdown 文件。

---

## 导出聊天记录 · Export

```bash
# 列出所有会话
python3 export_messages.py

# 导出单个联系人（支持昵称或 wxid）
python3 export_messages.py -c "Alice"
python3 export_messages.py -c wxid_xxx

# 关键词搜索导出
python3 export_messages.py -s "关键词"

# 导出全部联系人
python3 export_messages.py --all
```

导出文件保存在 `exported/` 目录。

---

## 隐私与安全 · Privacy & Security

- **数据不离开本机** — Web UI 绑定在 `127.0.0.1`，外部网络无法访问
- **密钥文件不进仓库** — `wechat_keys.json`、`decrypted/`、`exported/` 均在 `.gitignore` 中
- **一键清理** — Web UI「隐私」页面可一键删除所有解密数据库和导出文件
- **敏感字段打码** — 联系人列表中的 wxid 和手机号自动打码显示（如 `wxid_ab***123`）
- **发布前检查** — 提交代码前运行检查脚本，防止意外泄露

```bash
# 手动运行安全检查
python3 check_before_publish.py

# 安装为 git pre-commit hook（之后每次 commit 自动检查）
python3 check_before_publish.py --install
```

详见 [SECURITY.md](./SECURITY.md) 和 [DISCLAIMER.md](./DISCLAIMER.md)。

---

## 常见问题 · FAQ

**Q：提取密钥时提示 `command not found: lldb`？**

A：确保已安装 Xcode Command Line Tools：`xcode-select --install`

**Q：解密时提示 `sqlcipher not found`？**

A：运行 `brew install sqlcipher`，然后重试。

**Q：联系人列表是空的？**

A：检查 `decrypted/` 目录下是否有 `contact.db` 文件。如果没有，重新运行 `python3 decrypt_db.py`。

**Q：AI 报告生成失败？**

A：检查 API Key 是否正确，账户是否有余额。Anthropic 和 OpenAI 都需要先充值才能使用。

**Q：能在 Windows / Linux 上用吗？**

A：不能。密钥提取依赖 macOS 的 `lldb` 调试器，数据库路径也是 macOS 特有的。

---

## 项目结构 · Project Structure

```text
wechat-db-decrypt-macos/
├── find_key_memscan.py      # 密钥提取（内存扫描）
├── decrypt_db.py            # 数据库解密
├── wechat_data.py           # 数据查询核心
├── web_server.py            # Web UI 服务器（含 AI 报告 API）
├── generate_demo.py         # Demo 数据生成器
├── check_before_publish.py  # 发布前安全检查
├── export_messages.py       # 命令行导出工具
├── mcp_server.py            # MCP 工具服务器
├── desktop_launcher.py      # 桌面启动器
├── web/                     # 前端（纯 HTML/CSS/JS，无框架）
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── tests/                   # 单元测试
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
