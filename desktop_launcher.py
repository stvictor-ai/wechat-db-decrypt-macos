#!/usr/bin/env python3
"""Small macOS-friendly control window for non-technical users."""

import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox
import webbrowser

import launch
import web_server


class DesktopLauncher:
    def __init__(self, root):
        self.root = root
        self.server = None
        self.server_thread = None
        self.url = ""

        root.title("微信聊天分析")
        root.geometry("420x360")
        root.resizable(False, False)

        self.status = tk.StringVar(value="正在检查本地聊天快照...")
        self.detail = tk.StringVar(value="数据只在本机读取，不会上传。")

        frame = tk.Frame(root, padx=24, pady=24)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="微信聊天分析", font=("PingFang SC", 22, "bold")).pack(anchor="w")
        tk.Label(frame, textvariable=self.status, fg="#1f2329", wraplength=360, justify="left").pack(anchor="w", pady=(16, 4))
        tk.Label(frame, textvariable=self.detail, fg="#7b7f87", wraplength=360, justify="left").pack(anchor="w")

        actions = tk.Frame(frame)
        actions.pack(fill="x", pady=(24, 0))

        self.open_button = tk.Button(actions, text="打开聊天界面", command=self.open_web, state="disabled")
        self.open_button.pack(fill="x", ipady=8, pady=(0, 10))

        self.overview_button = tk.Button(actions, text="打开年度总览", command=lambda: self.open_web("#overview"), state="disabled")
        self.overview_button.pack(fill="x", ipady=8, pady=(0, 10))

        self.report_button = tk.Button(actions, text="打开关系报告", command=lambda: self.open_web("#report"), state="disabled")
        self.report_button.pack(fill="x", ipady=8, pady=(0, 10))

        self.memory_button = tk.Button(actions, text="打开回忆搜索", command=lambda: self.open_web("#memory"), state="disabled")
        self.memory_button.pack(fill="x", ipady=8, pady=(0, 10))

        self.privacy_button = tk.Button(actions, text="打开隐私安全中心", command=lambda: self.open_web("#privacy"), state="disabled")
        self.privacy_button.pack(fill="x", ipady=8, pady=(0, 10))

        self.sync_button = tk.Button(actions, text="刷新聊天快照", command=self.sync_snapshot)
        self.sync_button.pack(fill="x", ipady=8)

        tk.Label(
            frame,
            text="首次使用仍需按 README 完成一次密钥提取。日常使用只需要打开这个窗口。",
            fg="#8b8f99",
            wraplength=360,
            justify="left",
        ).pack(anchor="w", side="bottom")

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        threading.Thread(target=self.start_server_if_ready, daemon=True).start()

    def set_status(self, status, detail=""):
        self.root.after(0, lambda: self.status.set(status))
        if detail:
            self.root.after(0, lambda: self.detail.set(detail))

    def enable_web_actions(self):
        for button in (self.open_button, self.overview_button, self.report_button, self.memory_button, self.privacy_button):
            button.configure(state="normal")

    def start_server_if_ready(self):
        if not launch.has_decrypted_data(launch.wechat_data.DECRYPTED_DIR):
            self.set_status(
                "还没有可浏览的聊天快照",
                "如果已经有 wechat_keys.json，可以点击“刷新聊天快照”。否则需要先完成一次密钥提取。",
            )
            return
        self.start_server()

    def start_server(self):
        if self.server:
            return
        try:
            port = launch.find_free_port(launch.DEFAULT_HOST, launch.DEFAULT_PORT)
            web_server.WeChatHandler.decrypted_dir = os.path.abspath(launch.wechat_data.DECRYPTED_DIR)
            self.server = web_server.ThreadingHTTPServer((launch.DEFAULT_HOST, port), web_server.WeChatHandler)
            self.url = f"http://{launch.DEFAULT_HOST}:{port}/"
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
        except Exception as exc:
            self.set_status("启动本地网页失败", str(exc))
            return
        self.set_status("本地网页已启动", f"访问地址：{self.url}")
        self.root.after(0, self.enable_web_actions)

    def open_web(self, suffix=""):
        if not self.server:
            self.start_server()
        if self.url:
            webbrowser.open(self.url + suffix)

    def sync_snapshot(self):
        self.sync_button.configure(state="disabled", text="正在刷新...")
        threading.Thread(target=self._sync_snapshot, daemon=True).start()

    def _sync_snapshot(self):
        keys_path = os.path.join(launch.SCRIPT_DIR, "wechat_keys.json")
        if not os.path.isfile(keys_path):
            self.set_status("找不到密钥文件", "请先按 README 完成一次密钥提取，然后再刷新聊天快照。")
            self.root.after(0, lambda: self.sync_button.configure(state="normal", text="刷新聊天快照"))
            return

        self.set_status("正在刷新聊天快照", "这一步会重新解密本地数据库，可能需要几分钟。")
        result = subprocess.run([sys.executable, "decrypt_db.py"], cwd=launch.SCRIPT_DIR)
        if result.returncode == 0 and launch.has_decrypted_data(launch.wechat_data.DECRYPTED_DIR):
            self.set_status("聊天快照已更新", "可以打开聊天界面继续查看。")
            self.start_server()
        else:
            self.set_status("刷新失败", "请查看终端日志，常见原因是 sqlcipher 未安装或密钥失效。")
        self.root.after(0, lambda: self.sync_button.configure(state="normal", text="刷新聊天快照"))

    def close(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        self.root.destroy()


def main():
    os.chdir(launch.SCRIPT_DIR)
    root = tk.Tk()
    try:
        DesktopLauncher(root)
        root.mainloop()
    except tk.TclError as exc:
        messagebox.showerror("微信聊天分析", str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
