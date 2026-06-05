#!/usr/bin/env bash

cd "$(dirname "$0")"

python3 launch.py

echo
read -r -n 1 -s -p "按任意键关闭窗口..."
echo
