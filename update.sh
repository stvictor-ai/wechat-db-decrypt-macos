#!/usr/bin/env bash
# update.sh - 日常更新微信数据库快照
# 用法:
#   cd ~/wechat-db-decrypt-macos
#   ./update.sh
#
# 不需要关 SIP,不需要打开微信
# 如果密钥失效,会提示你需要重新提取密钥

set -e

cd "$(dirname "$0")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "${GREEN}[*]${NC} 开始更新微信数据库快照..."
echo

# 检查密钥文件
if [[ ! -f "wechat_keys.json" ]]; then
    echo "${RED}[✗]${NC} 找不到 wechat_keys.json"
    echo "${YELLOW}需要重新提取密钥(此步骤需要关闭 SIP):${NC}"
    echo "  1. 进恢复模式 → csrutil disable → 重启"
    echo "  2. 打开微信并登录"
    echo "  3. cd ~/wechat-db-decrypt-macos"
    echo "  4. PYTHONPATH=\$(lldb -P) python3 find_key_memscan.py"
    echo "  5. 重启回去 → csrutil enable"
    exit 1
fi

# 解密
echo "${GREEN}[*]${NC} 解密数据库..."
python3 decrypt_db.py

echo
echo "${GREEN}[✓]${NC} 更新完成，可以使用 CLI、Web UI 或 MCP Server 查询最新本地快照了"
echo "${YELLOW}    Web UI: python3 web_server.py${NC}"
