#!/usr/bin/env python3
"""Local Web UI for browsing decrypted WeChat messages."""

import argparse
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import wechat_data


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(SCRIPT_DIR, "web")


def _dir_size(path):
    total = 0
    if not os.path.isdir(path):
        return 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            full_path = os.path.join(root, name)
            try:
                total += os.path.getsize(full_path)
            except OSError:
                pass
    return total


def _gitignore_contains(pattern):
    path = os.path.join(SCRIPT_DIR, ".gitignore")
    if not os.path.isfile(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        return pattern in f.read()


def _git_tracks(path):
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=SCRIPT_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return False
    return result.returncode == 0


def get_privacy_status(host, decrypted_dir):
    keys_path = os.path.join(SCRIPT_DIR, "wechat_keys.json")
    latest = ""
    try:
        sessions = wechat_data.get_recent_sessions(1, decrypted_dir)
        if sessions:
            latest = sessions[0].get("time", "")
    except Exception:
        latest = ""

    return {
        "host": host,
        "host_is_local": host in ("127.0.0.1", "localhost", "::1"),
        "keys_exists": os.path.isfile(keys_path),
        "keys_tracked": _git_tracks("wechat_keys.json"),
        "decrypted_exists": os.path.isdir(decrypted_dir),
        "decrypted_size_gb": round(_dir_size(decrypted_dir) / (1024 ** 3), 2),
        "latest_session_time": latest,
        "gitignore_present": all(
            _gitignore_contains(pattern)
            for pattern in ("wechat_keys", "decrypted/", "exported/")
        ),
    }


def _sqlcipher_available():
    brew_path = "/opt/homebrew/opt/sqlcipher/bin/sqlcipher"
    if os.path.isfile(brew_path):
        return True
    return shutil.which("sqlcipher") is not None


def get_snapshot_status(decrypted_dir):
    sessions = []
    try:
        sessions = wechat_data.get_recent_sessions(1, decrypted_dir)
    except Exception:
        sessions = []

    latest_ts = sessions[0].get("timestamp", 0) if sessions else 0
    age_days = None
    if latest_ts:
        age_days = max(0, round((time.time() - int(latest_ts)) / 86400, 1))

    contacts = []
    try:
        contacts = wechat_data.get_contact_list("", 100000, decrypted_dir)
    except Exception:
        contacts = []

    keys_path = os.path.join(SCRIPT_DIR, "wechat_keys.json")
    demo_dir = os.path.join(SCRIPT_DIR, "demo")
    return {
        "decrypted_exists": os.path.isdir(decrypted_dir),
        "decrypted_size_gb": round(_dir_size(decrypted_dir) / (1024 ** 3), 2),
        "latest_session_time": sessions[0].get("time", "") if sessions else "",
        "latest_timestamp": latest_ts,
        "age_days": age_days,
        "contact_count": len(contacts),
        "message_db_count": len(wechat_data.get_msg_dbs(decrypted_dir)),
        "keys_exists": os.path.isfile(keys_path),
        "sqlcipher_available": _sqlcipher_available(),
        "demo_mode": os.path.abspath(decrypted_dir) == os.path.abspath(demo_dir),
    }


def run_refresh(script_dir, decrypted_dir):
    keys_path = os.path.join(script_dir, "wechat_keys.json")
    if not os.path.isfile(keys_path):
        return {
            "success": False,
            "error": "no_keys",
            "message": "找不到密钥文件 wechat_keys.json，请先完成一次密钥提取。",
        }

    if not _sqlcipher_available():
        return {
            "success": False,
            "error": "no_sqlcipher",
            "message": "未找到 sqlcipher，请先安装：brew install sqlcipher",
        }

    script = os.path.join(script_dir, "decrypt_db.py")
    try:
        result = subprocess.run(
            [sys.executable, script, "-o", decrypted_dir],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=script_dir,
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "timeout",
            "message": "解密超时（5 分钟），请检查微信数据库路径是否正常。",
        }

    stdout = result.stdout + result.stderr
    if result.returncode != 0:
        if "Could not find db_storage" in stdout:
            return {
                "success": False,
                "error": "no_db_dir",
                "message": "找不到微信数据库目录，请确认微信已安装且曾经登录过。",
            }
        return {
            "success": False,
            "error": "unknown",
            "message": "解密失败，请重新提取密钥后再试。",
            "log": stdout[:500],
        }

    m = re.search(r"Done: (\d+) decrypted, (\d+) failed", stdout)
    passed = int(m.group(1)) if m else 0
    failed = int(m.group(2)) if m else 0

    if passed == 0 and failed > 0:
        return {
            "success": False,
            "error": "stale_keys",
            "message": f"密钥可能已失效（0 成功，{failed} 失败），需要重新提取密钥。",
            "passed": 0,
            "failed": failed,
        }

    if passed == 0:
        return {
            "success": False,
            "error": "no_output",
            "message": "解密完成但没有生成任何文件，请检查密钥文件是否匹配当前微信账号。",
            "passed": 0,
            "failed": 0,
        }

    return {
        "success": True,
        "error": "none",
        "message": f"快照已更新：{passed} 个数据库解密成功。",
        "passed": passed,
        "failed": failed,
    }


def filter_contact_results(results, decrypted_dir):
    _names, contacts = wechat_data.load_contacts(decrypted_dir)
    allowed = {
        item["username"]
        for item in contacts
        if not item.get("is_group") and not wechat_data.is_public_or_system_account(item)
    }
    return [item for item in results if item.get("username") in allowed]


def _markdown_table(headers, rows):
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value).replace("\n", " ") for value in row) + " |")
    return "\n".join(lines)


def build_report_markdown(data):
    profile = data.get("relationship_profile") or {}
    lines = [
        f"# 我和 {data.get('display_name', 'TA')} 的关系报告",
        "",
        f"- 日期范围：{data.get('first_time') or '未知'} 至 {data.get('last_time') or '未知'}",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- 数据来源：本机微信聊天快照",
        "",
        "## 关系概览",
        "",
        f"- 关系温度：{data.get('relationship_score', 0)} / 99（{data.get('relationship_score_label', '样本较少')}）",
        f"- 关系类型：{profile.get('label', '关系样本')}",
        f"- 置信度：{profile.get('confidence', '中')}",
        f"- 核心判断：{profile.get('summary') or data.get('relationship_note', '')}",
        "",
        "## 核心指标",
        "",
        _markdown_table(
            ["指标", "数值"],
            [
                ["消息总量", data.get("total_messages", 0)],
                ["活跃天数", data.get("active_days", 0)],
                ["时间跨度", f"{data.get('span_days', 0)} 天"],
                ["最长连续互动", f"{data.get('longest_streak', 0)} 天"],
                ["互动占比", f"我 {data.get('mine_share', 0)}% / 对方 {data.get('their_share', 0)}%"],
                ["常聊时段", data.get("busiest_hour") or "-"],
                ["夜间消息占比", f"{data.get('night_share', 0)}%"],
                ["周末消息占比", f"{data.get('weekend_share', 0)}%"],
            ],
        ),
        "",
        "## 社交关系解读",
        "",
    ]
    for item in data.get("social_insights", []):
        lines.extend([f"### {item.get('title', '')}", "", item.get("body", ""), ""])

    dimensions = data.get("relationship_dimensions", [])
    if dimensions:
        lines.extend([
            "## 关系维度",
            "",
            _markdown_table(
                ["维度", "分数", "等级", "证据"],
                [
                    [item.get("name", ""), item.get("score", 0), item.get("label", ""), item.get("evidence", "")]
                    for item in dimensions
                ],
            ),
            "",
        ])

    if data.get("top_days"):
        lines.extend([
            "## 高频日期",
            "",
            _markdown_table(
                ["日期", "消息数"],
                [[item.get("date", ""), item.get("count", 0)] for item in data.get("top_days", [])],
            ),
            "",
        ])

    if data.get("top_types"):
        lines.extend([
            "## 消息类型",
            "",
            _markdown_table(
                ["类型", "数量"],
                [[item.get("name", ""), item.get("count", 0)] for item in data.get("top_types", [])],
            ),
            "",
        ])

    if data.get("top_terms"):
        lines.extend([
            "## 常见关键词",
            "",
            "、".join(f"{item.get('term')}({item.get('count')})" for item in data.get("top_terms", [])),
            "",
        ])

    lines.extend([
        "## 解读边界",
        "",
        "这份报告只基于聊天频率、时间分布、消息占比和文本长度等可解释指标，不等于真实亲密度或人格判断。线下关系、共同身份、工作协作和当时处境都会改变这些指标的含义。",
        "",
    ])
    return "\n".join(lines)


def build_ai_context(contact_name, analysis, recent_messages):
    lines = [
        "你是一个帮助用户理解人际关系的助手。",
        "你的分析完全基于下方提供的聊天统计数据，不做无依据的推断。",
        "用中文回答，简洁有洞察力，避免过度猜测。",
        "",
        f"=== 联系人「{contact_name}」的关系数据 ===",
        f"总消息数：{analysis.get('total_messages', 0)}",
        f"活跃天数：{analysis.get('active_days', 0)}",
        f"日期范围：{analysis.get('first_date', '?')} 至 {analysis.get('last_date', '?')}",
        f"我的占比：{analysis.get('mine_share', 50)}%  对方占比：{analysis.get('their_share', 50)}%",
        f"平均回复间隔：{analysis.get('avg_reply_minutes', '?')} 分钟",
        "",
    ]
    profile = analysis.get("relationship_profile") or {}
    if profile:
        lines += [
            f"关系类型：{profile.get('label', '未知')}（置信度 {profile.get('confidence', '低')}）",
            f"摘要：{profile.get('summary', '')}",
            "",
        ]
    if analysis.get("top_terms"):
        terms = "、".join(t["term"] for t in analysis["top_terms"][:12])
        lines += [f"常见关键词：{terms}", ""]
    if analysis.get("relationship_dimensions"):
        lines.append("=== 关系维度 ===")
        for d in analysis["relationship_dimensions"]:
            lines.append(f"- {d.get('label', '')}: {d.get('value', '')}")
        lines.append("")
    if analysis.get("social_insights"):
        lines.append("=== 社交洞察 ===")
        for ins in analysis["social_insights"]:
            lines.append(f"- {ins.get('title', '')}: {ins.get('body', '')}")
        lines.append("")
    if recent_messages:
        lines.append(f"=== 最近 {len(recent_messages)} 条文本消息 ===")
        for m in recent_messages:
            sender = "我" if m.get("is_mine") else contact_name
            lines.append(f"[{m.get('time', '')}] {sender}：{m.get('text', '')[:120]}")
        lines.append("")
    return "\n".join(lines)


def call_ai(provider, api_key, system_prompt, question):
    if provider == "anthropic":
        payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [{"role": "user", "content": question}],
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
    elif provider == "openai":
        payload = {
            "model": "gpt-4o-mini",
            "max_tokens": 1024,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "content-type": "application/json",
            },
            method="POST",
        )
    else:
        raise ValueError(f"未知 provider: {provider}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"API 返回 {e.code}: {body}")

    if provider == "anthropic":
        return data["content"][0]["text"]
    return data["choices"][0]["message"]["content"]


class WeChatHandler(BaseHTTPRequestHandler):
    decrypted_dir = wechat_data.DECRYPTED_DIR
    demo_mode = False

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/refresh":
            try:
                result = run_refresh(SCRIPT_DIR, self.decrypted_dir)
                self._send_json(result)
            except Exception as exc:
                self._send_json({"success": False, "error": "exception", "message": str(exc)}, 500)
            return

        if parsed.path == "/api/wipe":
            try:
                body = self._read_body()
                if body.get("confirm") != "WIPE":
                    self._send_json({"success": False, "error": "not_confirmed"})
                    return
                wiped = []
                if os.path.isdir(self.decrypted_dir):
                    shutil.rmtree(self.decrypted_dir)
                    wiped.append(os.path.basename(self.decrypted_dir) + "/")
                exported = os.path.join(SCRIPT_DIR, "exported")
                if os.path.isdir(exported):
                    shutil.rmtree(exported)
                    wiped.append("exported/")
                self._send_json({"success": True, "wiped": wiped})
            except Exception as exc:
                self._send_json({"success": False, "error": "exception", "message": str(exc)}, 500)
            return

        if parsed.path == "/api/ai/query":
            try:
                body = self._read_body()
                api_key = (body.get("api_key") or "").strip()
                provider = body.get("provider", "anthropic")
                contact = (body.get("contact") or "").strip()
                question = (body.get("question") or "").strip()
                if not api_key:
                    self._send_json({"success": False, "error": "no_key", "message": "请先填写 API Key"})
                    return
                if not question:
                    self._send_json({"success": False, "error": "no_question", "message": "请输入问题"})
                    return
                if not contact:
                    self._send_json({"success": False, "error": "no_contact", "message": "请先选择联系人"})
                    return
                analysis = wechat_data.get_chat_analysis(contact, 500, decrypted_dir=self.decrypted_dir)
                chat = wechat_data.get_chat_history(contact, 40, decrypted_dir=self.decrypted_dir)
                recent = [m for m in chat.get("messages", []) if m.get("type") == "文本"][-25:]
                contact_name = analysis.get("display_name") or contact
                system_prompt = build_ai_context(contact_name, analysis, recent)
                answer = call_ai(provider, api_key, system_prompt, question)
                self._send_json({"success": True, "answer": answer, "contact": contact_name})
            except Exception as exc:
                self._send_json({"success": False, "error": "api_error", "message": str(exc)[:300]}, 200)
            return

        self.send_error(404)

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_download(self, text, filename, ctype="text/markdown; charset=utf-8"):
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path):
        if not os.path.isfile(path):
            self.send_error(404)
            return
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        try:
            if parsed.path == "/api/sessions":
                limit = int(query.get("limit", ["80"])[0])
                self._send_json({"sessions": wechat_data.get_recent_sessions(limit, self.decrypted_dir)})
                return

            if parsed.path == "/api/chat":
                chat = query.get("username", query.get("chat", [""]))[0]
                limit = int(query.get("limit", ["120"])[0])
                start_date = query.get("start_date", [""])[0]
                end_date = query.get("end_date", [""])[0]
                data = wechat_data.get_chat_history(chat, limit, start_date, end_date, self.decrypted_dir)
                if data is None:
                    self._send_json({"error": "未找到这个聊天"}, 404)
                else:
                    self._send_json(data)
                return

            if parsed.path == "/api/analysis":
                chat = query.get("username", query.get("chat", [""]))[0]
                limit = int(query.get("limit", ["2000"])[0])
                start_date = query.get("start_date", [""])[0]
                end_date = query.get("end_date", [""])[0]
                data = wechat_data.get_chat_analysis(chat, limit, start_date, end_date, self.decrypted_dir)
                if data is None:
                    self._send_json({"error": "未找到这个聊天"}, 404)
                else:
                    self._send_json(data)
                return

            if parsed.path == "/api/report.md":
                chat = query.get("username", query.get("chat", [""]))[0]
                limit = int(query.get("limit", ["2000"])[0])
                start_date = query.get("start_date", [""])[0]
                end_date = query.get("end_date", [""])[0]
                data = wechat_data.get_chat_analysis(chat, limit, start_date, end_date, self.decrypted_dir)
                if data is None:
                    self._send_json({"error": "未找到这个聊天"}, 404)
                else:
                    self._send_download(build_report_markdown(data), "wechat-relationship-report.md")
                return

            if parsed.path == "/api/search":
                keyword = query.get("q", [""])[0].strip()
                limit = int(query.get("limit", ["80"])[0])
                contacts_only = query.get("contacts_only", ["0"])[0] in ("1", "true", "yes")
                search_limit = limit * 4 if contacts_only else limit
                results, method = wechat_data.search_messages(keyword, search_limit, self.decrypted_dir)
                if contacts_only:
                    results = filter_contact_results(results, self.decrypted_dir)[:limit]
                self._send_json({"results": results, "method": method})
                return

            if parsed.path == "/api/contacts":
                q = query.get("q", [""])[0].lower()
                limit = int(query.get("limit", ["100"])[0])
                contacts = wechat_data.get_contact_list(q, limit, self.decrypted_dir)
                self._send_json({"contacts": contacts})
                return

            if parsed.path == "/api/privacy":
                host = self.headers.get("Host", "127.0.0.1").split(":", 1)[0]
                self._send_json(get_privacy_status(host, self.decrypted_dir))
                return

            if parsed.path == "/api/status":
                self._send_json(get_snapshot_status(self.decrypted_dir))
                return

            if parsed.path == "/api/overview":
                year = int(query.get("year", [datetime.now().year])[0])
                limit = int(query.get("limit", ["24"])[0])
                sample_limit = int(query.get("sample_limit", ["1200"])[0])
                data = wechat_data.get_year_overview(year, limit, sample_limit, self.decrypted_dir)
                self._send_json(data)
                return
        except Exception as exc:
            self._send_json({"error": str(exc)}, 500)
            return

        path = parsed.path
        if path == "/":
            path = "/index.html"
        safe_name = os.path.normpath(path.lstrip("/"))
        if safe_name.startswith(".."):
            self.send_error(403)
            return
        self._send_file(os.path.join(STATIC_DIR, safe_name))


def main():
    parser = argparse.ArgumentParser(description="Run the WeChat local Web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--dir", default=wechat_data.DECRYPTED_DIR, help="Decrypted database directory")
    parser.add_argument("--demo", action="store_true",
                        help="Use synthetic demo data from ./demo/ (run generate_demo.py first)")
    args = parser.parse_args()

    if args.demo:
        demo_dir = os.path.join(SCRIPT_DIR, "demo")
        if not os.path.isdir(demo_dir):
            print("Demo data not found. Generate it first:")
            print("  python3 generate_demo.py")
            raise SystemExit(1)
        WeChatHandler.decrypted_dir = demo_dir
        WeChatHandler.demo_mode = True
    else:
        WeChatHandler.decrypted_dir = os.path.abspath(args.dir)

    server = ThreadingHTTPServer((args.host, args.port), WeChatHandler)
    mode = " [DEMO MODE]" if args.demo else ""
    print(f"Web UI: http://{args.host}:{args.port}{mode}")
    print(f"Decrypted DB: {WeChatHandler.decrypted_dir}")
    server.serve_forever()


if __name__ == "__main__":
    main()
