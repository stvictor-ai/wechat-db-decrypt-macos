#!/usr/bin/env python3
"""Beginner-friendly launcher for the local WeChat relationship browser."""

import argparse
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser

import wechat_data
import web_server


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def print_step(message):
    print(f"\n[微信聊天分析] {message}")


def print_hint(message):
    print(f"  {message}")


def command_exists(name):
    return shutil.which(name) is not None


def has_decrypted_data(decrypted_dir):
    contact_db = os.path.join(decrypted_dir, "contact", "contact.db")
    message_dir = os.path.join(decrypted_dir, "message")
    if not os.path.isfile(contact_db) or not os.path.isdir(message_dir):
        return False
    return any(
        name.startswith("message_") and name.endswith(".db")
        for name in os.listdir(message_dir)
    )


def find_free_port(host, preferred_port):
    for port in range(preferred_port, preferred_port + 30):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"无法找到可用端口，请先关闭占用 {preferred_port} 附近端口的程序")


def run_decrypt():
    print_step("正在生成或更新本地聊天快照")
    result = subprocess.run([sys.executable, "decrypt_db.py"], cwd=SCRIPT_DIR)
    if result.returncode != 0:
        raise RuntimeError("解密失败，请查看上方日志")


def explain_missing_data():
    print_step("还没有可浏览的数据")
    print_hint("如果你已经提取过密钥，请确认项目目录里有 wechat_keys.json，然后重新运行本启动器。")
    print_hint("如果还没有提取密钥，需要先按 README 的高级步骤完成一次密钥提取。")
    print_hint("密钥提取可能需要临时关闭 SIP；这个步骤不适合做成自动化，请谨慎操作。")


def prepare_data(decrypted_dir, sync):
    keys_path = os.path.join(SCRIPT_DIR, "wechat_keys.json")
    data_ready = has_decrypted_data(decrypted_dir)

    if sync:
        if not os.path.isfile(keys_path):
            explain_missing_data()
            return False
        run_decrypt()
        return has_decrypted_data(decrypted_dir)

    if data_ready:
        print_step("检测到本地聊天快照")
        print_hint("如果想刷新到最新数据，可以运行：python3 launch.py --sync")
        return True

    if os.path.isfile(keys_path):
        if not command_exists("sqlcipher"):
            print_step("缺少 sqlcipher")
            print_hint("请先安装依赖：brew install sqlcipher")
            return False
        run_decrypt()
        return has_decrypted_data(decrypted_dir)

    explain_missing_data()
    return False


def open_browser_later(url):
    time.sleep(0.8)
    webbrowser.open(url)


def serve(host, port, decrypted_dir, should_open):
    web_server.WeChatHandler.decrypted_dir = os.path.abspath(decrypted_dir)
    server = web_server.ThreadingHTTPServer((host, port), web_server.WeChatHandler)
    url = f"http://{host}:{port}/"

    print_step("本地网页已启动")
    print_hint(f"访问地址：{url}")
    print_hint("数据只在本机读取，不会上传到网络。")
    print_hint("关闭这个终端窗口，网页服务也会停止。")

    if should_open:
        threading.Thread(target=open_browser_later, args=(url,), daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止本地网页服务")
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="启动微信聊天关系分析器")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--dir", default=wechat_data.DECRYPTED_DIR, help="解密后的数据库目录")
    parser.add_argument("--sync", action="store_true", help="启动前先刷新本地聊天快照")
    parser.add_argument("--no-open", action="store_true", help="启动后不自动打开浏览器")
    args = parser.parse_args()

    os.chdir(SCRIPT_DIR)
    print_step("正在检查运行环境")
    if sys.version_info < (3, 9):
        print_hint("需要 Python 3.9 或更新版本")
        return 1

    if not prepare_data(args.dir, args.sync):
        return 1

    try:
        port = find_free_port(args.host, args.port)
    except RuntimeError as exc:
        print_step(str(exc))
        return 1

    serve(args.host, port, args.dir, not args.no_open)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
