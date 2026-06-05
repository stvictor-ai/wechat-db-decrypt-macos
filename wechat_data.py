#!/usr/bin/env python3
"""Shared query helpers for decrypted WeChat databases."""

import hashlib
import math
import os
import re
import sqlite3
from collections import Counter
from datetime import datetime


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DECRYPTED_DIR = os.path.join(SCRIPT_DIR, "decrypted")

MSG_TYPE_MAP = {
    1: "文本",
    3: "图片",
    34: "语音",
    42: "名片",
    43: "视频",
    47: "表情",
    48: "位置",
    49: "链接/文件",
    50: "通话",
    10000: "系统",
    10002: "撤回",
}

_ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
_SILK_BYTES_PER_SEC = 4000


def _connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def clean_text(value, max_len=None):
    if value is None:
        text = ""
    elif isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)
    text = text.replace("\x08", "").replace("\x00", "")
    if max_len and len(text) > max_len:
        return text[:max_len] + "..."
    return text


def ts_to_string(ts, fmt="%Y-%m-%d %H:%M:%S"):
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(int(ts)).strftime(fmt)
    except Exception:
        return ""


def get_msg_dbs(decrypted_dir=DECRYPTED_DIR):
    msg_dir = os.path.join(decrypted_dir, "message")
    if not os.path.isdir(msg_dir):
        return []
    return [
        os.path.join(msg_dir, name)
        for name in sorted(os.listdir(msg_dir))
        if re.match(r"^message_\d+\.db$", name)
    ]


def get_session_db(decrypted_dir=DECRYPTED_DIR):
    return os.path.join(decrypted_dir, "session", "session.db")


def get_contact_db(decrypted_dir=DECRYPTED_DIR):
    return os.path.join(decrypted_dir, "contact", "contact.db")


def get_fts_db(decrypted_dir=DECRYPTED_DIR):
    return os.path.join(decrypted_dir, "message", "message_fts.db")


def username_to_table(username):
    return "Msg_" + hashlib.md5(username.encode()).hexdigest()


def load_contacts(decrypted_dir=DECRYPTED_DIR):
    contacts = {}
    full = []
    db = get_contact_db(decrypted_dir)
    if not os.path.isfile(db):
        return contacts, full

    conn = _connect(db)
    try:
        for table in ("contact", "stranger"):
            try:
                rows = conn.execute(
                    f"SELECT username, local_type, verify_flag, remark, nick_name, small_head_url FROM {table}"
                ).fetchall()
            except sqlite3.Error:
                rows = conn.execute(
                    f"SELECT username, 0 AS local_type, 0 AS verify_flag, remark, nick_name, '' AS small_head_url FROM {table}"
                ).fetchall()
            for row in rows:
                username = row["username"]
                if not username or username in contacts:
                    continue
                display = row["remark"] or row["nick_name"] or username
                contacts[username] = display
                full.append({
                    "username": username,
                    "display_name": display,
                    "local_type": row["local_type"] or 0,
                    "verify_flag": row["verify_flag"] or 0,
                    "remark": row["remark"] or "",
                    "nick_name": row["nick_name"] or "",
                    "avatar": row["small_head_url"] or "",
                    "is_group": "@chatroom" in username,
                })
    finally:
        conn.close()
    return contacts, full


def resolve_username(chat_name, contacts):
    if not chat_name:
        return None
    if chat_name in contacts or chat_name.startswith("wxid_") or "@chatroom" in chat_name:
        return chat_name

    needle = chat_name.lower()
    for username, display in contacts.items():
        if needle == display.lower():
            return username
    for username, display in contacts.items():
        if needle in display.lower() or needle in username.lower():
            return username
    return None


def load_fts_name_map(decrypted_dir=DECRYPTED_DIR):
    db = get_fts_db(decrypted_dir)
    if not os.path.isfile(db):
        return {}
    conn = _connect(db)
    try:
        return {int(row["rowid"]): row["username"] for row in conn.execute("SELECT rowid, username FROM name2id")}
    finally:
        conn.close()


def find_all_msg_tables(username, decrypted_dir=DECRYPTED_DIR):
    table = username_to_table(username)
    found = []
    for db_path in get_msg_dbs(decrypted_dir):
        conn = sqlite3.connect(db_path)
        try:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if exists:
                found.append((db_path, table))
        finally:
            conn.close()
    return found


def collect_all_usernames(decrypted_dir=DECRYPTED_DIR):
    result = {}
    for db_path in get_msg_dbs(decrypted_dir):
        conn = sqlite3.connect(db_path)
        try:
            for (username,) in conn.execute("SELECT user_name FROM Name2Id WHERE user_name != ''"):
                result.setdefault(username, db_path)
        finally:
            conn.close()
    return result


def load_msg_name_map(db_path):
    conn = _connect(db_path)
    try:
        return {int(row["rowid"]): row["user_name"] for row in conn.execute("SELECT rowid, user_name FROM Name2Id")}
    finally:
        conn.close()


def parse_message(content, local_type=1, is_group=False, contacts=None, sender_username=""):
    contacts = contacts or {}
    text = clean_text(content)
    sender = ""
    if is_group:
        if sender_username:
            sender = contacts.get(sender_username, sender_username)
        elif ":\n" in text:
            raw_sender, text = text.split(":\n", 1)
            sender = contacts.get(raw_sender, raw_sender)

    # WeChat on macOS encodes sub-type in high bits for extended message types
    normalized = local_type if local_type <= 65535 else local_type & 0xFF
    type_name = MSG_TYPE_MAP.get(normalized, MSG_TYPE_MAP.get(local_type, "其他"))

    is_binary = isinstance(content, bytes) and content[:4] == _ZSTD_MAGIC
    if normalized == 1:
        pass  # plain text, keep as-is
    elif normalized == 10000:
        # system / revoke: show plain text when available, fall back to label
        if is_binary or not text:
            text = f"[{type_name}]"
        else:
            text = text[:300]
    else:
        text = f"[{type_name}]"

    return {"sender": sender, "text": text, "type": type_name}


def get_recent_sessions(limit=50, decrypted_dir=DECRYPTED_DIR):
    contacts, _ = load_contacts(decrypted_dir)
    db = get_session_db(decrypted_dir)
    if not os.path.isfile(db):
        return []
    conn = _connect(db)
    try:
        rows = conn.execute("""
            SELECT username, type, unread_count, summary, last_timestamp,
                   sort_timestamp, last_msg_type, last_sender_display_name
            FROM SessionTable
            WHERE last_timestamp > 0
            ORDER BY sort_timestamp DESC
            LIMIT ?
        """, (limit,)).fetchall()
    finally:
        conn.close()

    sessions = []
    for row in rows:
        username = row["username"]
        summary = clean_text(row["summary"], 180)
        if ":\n" in summary:
            summary = summary.split(":\n", 1)[1]
        sessions.append({
            "username": username,
            "display_name": contacts.get(username, username),
            "is_group": "@chatroom" in username,
            "unread": row["unread_count"] or 0,
            "summary": summary,
            "last_sender": row["last_sender_display_name"] or "",
            "last_type": MSG_TYPE_MAP.get(row["last_msg_type"], str(row["last_msg_type"] or "")),
            "timestamp": row["last_timestamp"] or 0,
            "time": ts_to_string(row["last_timestamp"], "%m-%d %H:%M"),
        })
    return sessions


def is_public_or_system_account(contact):
    username = contact.get("username", "")
    if "@chatroom" in username:
        return False
    system_usernames = {
        "brandsessionholder",
        "notifymessage",
        "qmessage",
        "qqmail",
        "medianote",
        "floatbottle",
        "fmessage",
        "masssendapp",
        "weixin",
        "mphelper",
        "weixinguanhaozhushou",
        "filehelper",
    }
    if username in system_usernames:
        return True
    if username.startswith("gh_"):
        return True
    if username.endswith("@openim"):
        return True
    return bool(contact.get("verify_flag"))


def get_contact_list(query="", limit=100, decrypted_dir=DECRYPTED_DIR):
    _, contacts = load_contacts(decrypted_dir)
    contacts = [
        item for item in contacts
        if not item.get("is_group")
        and not is_public_or_system_account(item)
    ]
    session_by_username = {
        item["username"]: item
        for item in get_recent_sessions(5000, decrypted_dir)
    }

    needle = (query or "").lower()
    if needle:
        contacts = [
            item for item in contacts
            if needle in item["display_name"].lower()
            or needle in item["username"].lower()
            or needle in item["remark"].lower()
            or needle in item["nick_name"].lower()
        ]

    enriched = []
    for item in contacts:
        session = session_by_username.get(item["username"], {})
        enriched.append({
            **item,
            "summary": session.get("summary", ""),
            "last_time": session.get("time", ""),
            "timestamp": session.get("timestamp", 0),
            "has_session": bool(session),
        })

    enriched.sort(key=lambda item: (item["timestamp"], item["display_name"].lower()), reverse=True)
    return enriched[:limit]


def get_voice_duration_map(username, decrypted_dir=DECRYPTED_DIR):
    """Return {local_id: duration_seconds} for voice messages of a chat, estimated from SILK data size."""
    msg_dir = os.path.join(decrypted_dir, "message")
    result = {}
    if not os.path.isdir(msg_dir):
        return result
    for name in sorted(os.listdir(msg_dir)):
        if not re.match(r"^media_\d+\.db$", name):
            continue
        conn = _connect(os.path.join(msg_dir, name))
        try:
            row = conn.execute("SELECT rowid FROM Name2Id WHERE user_name = ?", (username,)).fetchone()
            if not row:
                continue
            rows = conn.execute(
                "SELECT local_id, length(voice_data) as sz FROM VoiceInfo WHERE chat_name_id = ?",
                (row["rowid"],),
            ).fetchall()
            for r in rows:
                result[r["local_id"]] = round(r["sz"] / _SILK_BYTES_PER_SEC, 1)
        except Exception:
            pass
        finally:
            conn.close()
    return result


def get_chat_history(chat_name, limit=80, start_date="", end_date="", decrypted_dir=DECRYPTED_DIR):
    contacts, _ = load_contacts(decrypted_dir)
    username = resolve_username(chat_name, contacts)
    if not username:
        return None

    conditions = []
    params = []
    for label, value, op in (("start_date", start_date, ">="), ("end_date", end_date, "<=")):
        if not value:
            continue
        dt = None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(value, fmt)
                break
            except ValueError:
                pass
        if dt is None:
            name = "开始日期" if label == "start_date" else "结束日期"
            raise ValueError(f"{name}需要使用 YYYY-MM-DD 或 YYYY-MM-DD HH:MM 格式")
        if label == "end_date" and len(value) <= 10:
            dt = dt.replace(hour=23, minute=59, second=59)
        conditions.append(f"create_time {op} ?")
        params.append(int(dt.timestamp()))

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    rows = []
    for db_path, table in find_all_msg_tables(username, decrypted_dir):
        sender_map = load_msg_name_map(db_path)
        conn = _connect(db_path)
        try:
            db_rows = conn.execute(f"""
                SELECT local_id, local_type, create_time, real_sender_id, message_content, source
                FROM [{table}]
                {where}
                ORDER BY create_time DESC
                LIMIT ?
            """, params + [limit]).fetchall()
            for row in db_rows:
                rows.append((db_path, sender_map.get(int(row["real_sender_id"] or 0), ""), row))
        finally:
            conn.close()

    rows.sort(key=lambda item: item[2]["create_time"] or 0, reverse=True)
    rows = rows[:limit]
    is_group = "@chatroom" in username
    messages = []
    for _db_path, sender_username, row in reversed(rows):
        parsed = parse_message(row["message_content"], row["local_type"], is_group, contacts, sender_username)
        is_mine = bool(sender_username and sender_username != username and not is_group)
        messages.append({
            "id": row["local_id"],
            "timestamp": row["create_time"] or 0,
            "time": ts_to_string(row["create_time"], "%Y-%m-%d %H:%M"),
            "type": parsed["type"],
            "sender": parsed["sender"],
            "sender_username": sender_username,
            "is_mine": is_mine,
            "text": parsed["text"],
            "source": clean_text(row["source"], 120),
        })

    voice_ids = [m["id"] for m in messages if m["type"] == "语音"]
    if voice_ids:
        dur_map = get_voice_duration_map(username, decrypted_dir)
        for m in messages:
            if m["type"] == "语音" and m["id"] in dur_map:
                m["duration"] = dur_map[m["id"]]

    return {
        "username": username,
        "display_name": contacts.get(username, username),
        "is_group": is_group,
        "messages": messages,
    }


def _tokenize_for_summary(text):
    words = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    stop = {
        "这个", "那个", "然后", "就是", "可以", "没有", "不是", "我们", "你们",
        "他们", "自己", "一下", "现在", "今天", "明天", "昨天",
    }
    return [word.lower() for word in words if word.lower() not in stop]


def _score_label(score):
    if score >= 75:
        return "高"
    if score >= 45:
        return "中"
    return "低"


def relationship_score(total, active_days, mine_share, last_ts):
    if not total:
        return 0
    volume = min(35, math.log10(total + 1) * 12)
    days = min(28, active_days * 1.8)
    balance = max(0, 22 - abs((mine_share or 0) - 50) * 0.55)
    recency = 12 if last_ts else 0
    return max(1, min(99, round(volume + days + balance + recency)))


def relationship_score_label(score):
    if score >= 78:
        return "稳定活跃"
    if score >= 55:
        return "有来有往"
    if score >= 30:
        return "轻量联系"
    return "样本较少"


def _longest_day_streak(days):
    if not days:
        return 0
    parsed = sorted(datetime.strptime(day, "%Y-%m-%d").date() for day in days)
    longest = 1
    current = 1
    for prev, day in zip(parsed, parsed[1:]):
        if (day - prev).days == 1:
            current += 1
        else:
            longest = max(longest, current)
            current = 1
    return max(longest, current)


def _relationship_profile(total, active_days, avg_per_active_day, balance_score, continuity_score):
    if total < 20 and active_days <= 1:
        return {
            "label": "事务型短联系",
            "confidence": "低",
            "summary": "聊天样本集中且数量少，更像一次目的明确的联系，不适合过度推断关系深度。",
        }
    if active_days >= 20 and total >= 1000 and balance_score >= 55:
        return {
            "label": "稳定熟人关系",
            "confidence": "高",
            "summary": "互动量、持续天数和回应均衡度都比较高，说明你们不是偶发沟通，而是有稳定往来的熟人关系。",
        }
    if active_days >= 8 and avg_per_active_day >= 20:
        return {
            "label": "阶段性高频关系",
            "confidence": "中",
            "summary": "这段时间互动密度明显，像是被某个共同事项、项目、生活阶段或情绪周期拉近的关系。",
        }
    if continuity_score >= 55 and total >= 100:
        return {
            "label": "持续低频关系",
            "confidence": "中",
            "summary": "聊天不一定爆发式密集，但能跨多个日期延续，说明关系有一定稳定性和可达性。",
        }
    return {
        "label": "轻量熟人关系",
        "confidence": "中" if total >= 50 else "低",
        "summary": "已有可观察的互动痕迹，但关系强度仍需要结合线下场景、共同圈层和最近是否持续联系来判断。",
    }


def _dimension(name, score, evidence):
    return {
        "name": name,
        "score": max(0, min(100, int(round(score)))),
        "label": _score_label(score),
        "evidence": evidence,
    }


def get_chat_analysis(chat_name, sample_limit=2000, start_date="", end_date="", decrypted_dir=DECRYPTED_DIR):
    chat = get_chat_history(chat_name, sample_limit, start_date, end_date, decrypted_dir)
    if not chat:
        return None

    messages = chat["messages"]
    total = len(messages)
    mine = sum(1 for msg in messages if msg.get("is_mine"))
    theirs = total - mine
    first_ts = messages[0]["timestamp"] if messages else 0
    last_ts = messages[-1]["timestamp"] if messages else 0

    type_counter = Counter(msg.get("type") or "unknown" for msg in messages)
    hour_counter = Counter()
    day_counter = Counter()
    sender_counter = Counter()
    token_counter = Counter()
    chars = 0
    text_messages = 0
    weekend_messages = 0
    night_messages = 0
    initiator_counter = Counter()
    turn_switches = 0
    previous_mine = None

    for msg in messages:
        ts = msg.get("timestamp") or 0
        if ts:
            dt = datetime.fromtimestamp(ts)
            hour_counter[dt.hour] += 1
            day_counter[dt.strftime("%Y-%m-%d")] += 1
            if dt.weekday() >= 5:
                weekend_messages += 1
            if dt.hour >= 22 or dt.hour < 8:
                night_messages += 1
        if msg.get("sender"):
            sender_counter[msg["sender"]] += 1
        text = clean_text(msg.get("text"))
        if msg.get("type") == "文本":
            text_messages += 1
            chars += min(len(text), 500)
            token_counter.update(_tokenize_for_summary(text))
        if previous_mine is not None and previous_mine != msg.get("is_mine"):
            turn_switches += 1
        previous_mine = msg.get("is_mine")

    for day in day_counter:
        day_messages = [msg for msg in messages if (msg.get("time") or "").startswith(day)]
        if day_messages:
            initiator_counter["我" if day_messages[0].get("is_mine") else chat["display_name"]] += 1

    busiest_hour, busiest_hour_count = ("", 0)
    if hour_counter:
        hour, busiest_hour_count = hour_counter.most_common(1)[0]
        busiest_hour = f"{hour:02d}:00-{hour:02d}:59"

    active_days = len(day_counter)
    avg_per_active_day = round(total / active_days, 1) if active_days else 0
    my_share = round(mine * 100 / total) if total else 0
    their_share = 100 - my_share if total else 0
    if first_ts and last_ts:
        first_day = datetime.fromtimestamp(first_ts).date()
        last_day = datetime.fromtimestamp(last_ts).date()
        span_days = max(1, (last_day - first_day).days + 1)
    else:
        span_days = 0
    active_day_ratio = round(active_days * 100 / span_days) if span_days else 0
    longest_streak = _longest_day_streak(day_counter.keys())
    balance_score = max(0, 100 - abs(my_share - 50) * 2) if total and not chat["is_group"] else 0
    density_score = min(100, avg_per_active_day * 2.5)
    continuity_score = min(100, active_day_ratio * 0.65 + longest_streak * 8)
    expression_score = min(100, (text_messages * 100 / total if total else 0) * 0.55 + min(45, (chars / max(text_messages, 1)) * 0.8))
    boundary_score = max(0, 100 - (night_messages * 100 / total if total else 0) * 0.8) if total else 0
    turn_score = min(100, turn_switches * 100 / max(total - 1, 1)) if total > 1 else 0
    weekend_share = round(weekend_messages * 100 / total) if total else 0
    night_share = round(night_messages * 100 / total) if total else 0

    if total < 20 and active_days <= 1:
        relationship_note = (
            "这段关系目前更像一次短暂、目的明确的联系。聊天集中在同一天，"
            "还没有形成稳定的往来节奏。"
        )
    elif active_days >= 10 and total >= 500:
        relationship_note = (
            "你们之间已经有持续互动的痕迹，聊天分布在多个日期，说明这不是偶发联系，"
            "而是一段有一定熟悉度和重复往来的关系。"
        )
    elif total >= 100:
        relationship_note = (
            "你们有过一段较完整的对话记录，互动量足以看出基本沟通模式，"
            "但关系强度还需要结合最近是否持续联系来判断。"
        )
    else:
        relationship_note = (
            "这段关系有一定聊天记录，但样本还不算多，更适合作为轻量回顾，"
            "不要过度解读单次对话里的语气。"
        )

    if total and not chat["is_group"]:
        if my_share >= 65:
            relationship_note += " 从对话占比看，你更主动一些。"
        elif their_share >= 65:
            relationship_note += f" 从对话占比看，{chat['display_name']} 更主动一些。"
        else:
            relationship_note += " 从对话占比看，双方回应比较均衡。"
    if busiest_hour:
        relationship_note += f" 你们最常在 {busiest_hour} 这个时段交流。"

    rel_score = relationship_score(total, active_days, my_share, last_ts)

    relationship_profile = _relationship_profile(
        total,
        active_days,
        avg_per_active_day,
        balance_score,
        continuity_score,
    )
    relationship_dimensions = [
        _dimension(
            "互动密度",
            density_score,
            f"活跃日均 {avg_per_active_day} 条消息，最高频日期有 {day_counter.most_common(1)[0][1] if day_counter else 0} 条。",
        ),
        _dimension(
            "关系连续性",
            continuity_score,
            f"时间跨度 {span_days} 天，实际活跃 {active_days} 天，最长连续互动 {longest_streak} 天。",
        ),
        _dimension(
            "回应均衡",
            balance_score,
            "双方消息占比接近，说明对话不是单方面输出。" if balance_score >= 60 else "双方消息占比有明显倾斜，可能存在一方更主动或信息流更集中的情况。",
        ),
        _dimension(
            "对话轮转",
            turn_score,
            f"聊天中出现 {turn_switches} 次说话方切换，可反映来回响应的程度。",
        ),
        _dimension(
            "时间边界",
            boundary_score,
            f"夜间消息占 {night_share}%，周末消息占 {weekend_share}%。",
        ),
        _dimension(
            "表达丰富度",
            expression_score,
            f"文本消息 {text_messages} 条，平均文本长度 {round(chars / text_messages, 1) if text_messages else 0} 字。",
        ),
    ]

    lead_side = ""
    if initiator_counter:
        lead_name, lead_count = initiator_counter.most_common(1)[0]
        suffix = "更常开启当天的第一轮对话" if lead_name == "我" else "更常开启当天的第一轮对话"
        lead_side = f"{lead_name}{suffix}（{lead_count} 天）。"

    social_insights = [
        {
            "title": "关系类型推断",
            "body": relationship_profile["summary"],
        },
        {
            "title": "主动性结构",
            "body": (
                lead_side
                or "样本还不足以判断谁更常开启对话。"
            ) + (
                " 对话占比比较均衡，说明双方都在维持沟通。"
                if balance_score >= 70 and not chat["is_group"]
                else " 对话占比有一定倾斜，但仍能看到双方回应。"
                if balance_score >= 45 and not chat["is_group"]
                else " 对话占比有倾斜，建议结合具体聊天内容判断是事务推进、照顾关系，还是单方更主动。"
            ),
        },
        {
            "title": "社交距离",
            "body": (
                "你们有一定跨日期互动，关系不像一次性连接；如果高频日期集中在少数几天，可能是阶段性事件驱动。"
                if continuity_score >= 45
                else "聊天分布较集中，社交距离可能还比较远，更多像围绕具体事项产生的联系。"
            ),
        },
        {
            "title": "时间边界",
            "body": (
                "互动主要发生在白天或常规时段，边界感比较清楚。"
                if night_share < 20
                else "夜间消息占比不低，说明这段关系可能进入了更私人、更即时，或更受情绪/紧急事项驱动的沟通场景。"
            ),
        },
        {
            "title": "解读提醒",
            "body": "这些判断来自聊天频率和节奏，不等于真实亲密度。线下关系、共同身份、工作协作和当时处境都会改变含义。",
        },
    ]

    return {
        "username": chat["username"],
        "display_name": chat["display_name"],
        "is_group": chat["is_group"],
        "total_messages": total,
        "mine_messages": mine,
        "their_messages": theirs,
        "mine_share": my_share,
        "their_share": their_share,
        "first_time": ts_to_string(first_ts, "%Y-%m-%d") if first_ts else "",
        "last_time": ts_to_string(last_ts, "%Y-%m-%d") if last_ts else "",
        "active_days": active_days,
        "avg_per_active_day": avg_per_active_day,
        "busiest_hour": busiest_hour,
        "busiest_hour_count": busiest_hour_count,
        "avg_chars": round(chars / text_messages, 1) if text_messages else 0,
        "relationship_note": relationship_note,
        "relationship_score": rel_score,
        "relationship_score_label": relationship_score_label(rel_score),
        "relationship_profile": relationship_profile,
        "relationship_dimensions": relationship_dimensions,
        "social_insights": social_insights,
        "span_days": span_days,
        "active_day_ratio": active_day_ratio,
        "longest_streak": longest_streak,
        "turn_switches": turn_switches,
        "night_share": night_share,
        "weekend_share": weekend_share,
        "initiators": [{"name": key, "count": value} for key, value in initiator_counter.most_common(4)],
        "top_types": [{"name": key, "count": value} for key, value in type_counter.most_common(6)],
        "top_days": [{"date": key, "count": value} for key, value in day_counter.most_common(5)],
        "top_senders": [{"name": key, "count": value} for key, value in sender_counter.most_common(8)],
        "top_terms": [{"term": key, "count": value} for key, value in token_counter.most_common(12)],
    }


def get_year_overview(year=None, candidate_limit=24, sample_limit=1200, decrypted_dir=DECRYPTED_DIR):
    year = int(year or datetime.now().year)
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    contacts = [
        item for item in get_contact_list("", 300, decrypted_dir)
        if item.get("has_session")
    ][:candidate_limit]

    relationship_rows = []
    month_counter = Counter()
    term_counter = Counter()
    total_messages = 0
    total_active_days = 0

    for contact in contacts:
        analysis = get_chat_analysis(
            contact["username"],
            sample_limit,
            start_date,
            end_date,
            decrypted_dir,
        )
        if not analysis or not analysis.get("total_messages"):
            continue
        total_messages += analysis["total_messages"]
        total_active_days += analysis["active_days"]
        for item in analysis.get("top_days", []):
            month_counter[item["date"][:7]] += item["count"]
        for item in analysis.get("top_terms", []):
            term_counter[item["term"]] += item["count"]
        relationship_rows.append({
            "username": analysis["username"],
            "display_name": analysis["display_name"],
            "summary": contact.get("summary", ""),
            "last_time": contact.get("last_time", ""),
            "last_timestamp": contact.get("timestamp", 0),
            "total_messages": analysis["total_messages"],
            "active_days": analysis["active_days"],
            "relationship_score": analysis["relationship_score"],
            "relationship_score_label": analysis["relationship_score_label"],
            "relationship_type": analysis["relationship_profile"]["label"],
            "longest_streak": analysis["longest_streak"],
            "busiest_hour": analysis["busiest_hour"],
            "night_share": analysis["night_share"],
            "weekend_share": analysis["weekend_share"],
            "top_terms": analysis["top_terms"][:4],
        })

    top_active = sorted(relationship_rows, key=lambda item: item["total_messages"], reverse=True)[:8]
    top_relationships = sorted(relationship_rows, key=lambda item: item["relationship_score"], reverse=True)[:8]
    top_continuity = sorted(
        relationship_rows,
        key=lambda item: (item["longest_streak"], item["active_days"], item["total_messages"]),
        reverse=True,
    )[:8]
    top_late_night = sorted(
        relationship_rows,
        key=lambda item: (item["night_share"], item["total_messages"]),
        reverse=True,
    )[:8]

    month_counts = [
        {"month": f"{year}-{month:02d}", "count": month_counter.get(f"{year}-{month:02d}", 0)}
        for month in range(1, 13)
    ]
    top_terms = [{"term": key, "count": value} for key, value in term_counter.most_common(12)]

    highlights = {
        "most_active": top_active[0] if top_active else None,
        "warmest": top_relationships[0] if top_relationships else None,
        "longest_streak": top_continuity[0] if top_continuity else None,
        "late_night": top_late_night[0] if top_late_night else None,
        "top_term": top_terms[0] if top_terms else None,
    }

    return {
        "year": year,
        "source_note": f"基于最近活跃的 {len(contacts)} 位普通联系人生成，单个联系人最多抽取 {sample_limit} 条消息。",
        "candidate_count": len(contacts),
        "analyzed_count": len(relationship_rows),
        "total_messages": total_messages,
        "total_active_days": total_active_days,
        "avg_messages_per_contact": round(total_messages / len(relationship_rows), 1) if relationship_rows else 0,
        "avg_active_days_per_contact": round(total_active_days / len(relationship_rows), 1) if relationship_rows else 0,
        "highlights": highlights,
        "top_active": top_active,
        "top_relationships": top_relationships,
        "top_continuity": top_continuity,
        "top_late_night": top_late_night,
        "month_counts": month_counts,
        "top_terms": top_terms,
    }


def _fts_tables(conn):
    names = [row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'message_fts_v4_%'"
    )]
    return sorted(
        name for name in names
        if re.match(r"^message_fts_v4_\d+$", name)
    )


def _quoted_fts_query(keyword):
    return '"' + keyword.replace('"', '""') + '"'


def search_messages_fts(keyword, limit=50, decrypted_dir=DECRYPTED_DIR):
    db = get_fts_db(decrypted_dir)
    if not os.path.isfile(db):
        return [], "none"

    contacts, _ = load_contacts(decrypted_dir)
    id_to_username = load_fts_name_map(decrypted_dir)
    conn = _connect(db)
    rows = []
    method = "fts_match"
    try:
        for table in _fts_tables(conn):
            try:
                rows.extend(conn.execute(f"""
                    SELECT acontent AS content, message_local_id, sort_seq, local_type,
                           session_id, sender_id, create_time
                    FROM {table}
                    WHERE {table} MATCH ?
                    ORDER BY create_time DESC
                    LIMIT ?
                """, (_quoted_fts_query(keyword), limit)).fetchall())
            except sqlite3.OperationalError:
                method = "fts_content"
                content_table = f"{table}_content"
                rows.extend(conn.execute(f"""
                    SELECT c0 AS content, c1 AS message_local_id, c2 AS sort_seq,
                           c3 AS local_type, c4 AS session_id, c5 AS sender_id,
                           c6 AS create_time
                    FROM {content_table}
                    WHERE c0 LIKE ?
                    ORDER BY c6 DESC
                    LIMIT ?
                """, (f"%{keyword}%", limit)).fetchall())
    finally:
        conn.close()

    results = []
    for row in rows:
        username = id_to_username.get(int(row["session_id"] or 0), "")
        sender_username = id_to_username.get(int(row["sender_id"] or 0), "")
        is_group = "@chatroom" in username
        parsed = parse_message(row["content"], row["local_type"] or 1, is_group, contacts, sender_username)
        results.append({
            "username": username,
            "display_name": contacts.get(username, username) if username else "",
            "is_group": is_group,
            "sender": parsed["sender"],
            "text": parsed["text"],
            "type": parsed["type"],
            "timestamp": row["create_time"] or 0,
            "time": ts_to_string(row["create_time"], "%Y-%m-%d %H:%M"),
            "local_id": row["message_local_id"],
        })

    results.sort(key=lambda item: item["timestamp"], reverse=True)
    return results[:limit], method


def search_messages_raw(keyword, limit=50, decrypted_dir=DECRYPTED_DIR):
    contacts, _ = load_contacts(decrypted_dir)
    username_to_db = collect_all_usernames(decrypted_dir)
    keyword_lower = keyword.lower()
    results = []
    fetch_limit = limit * 3
    for username, db_path in username_to_db.items():
        if len(results) >= limit:
            break
        table = username_to_table(username)
        conn = _connect(db_path)
        try:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if not exists:
                continue
            rows = conn.execute(f"""
                SELECT local_id, local_type, create_time, message_content
                FROM [{table}]
                WHERE message_content LIKE ?
                ORDER BY create_time DESC
                LIMIT ?
            """, (f"%{keyword}%", fetch_limit)).fetchall()
        finally:
            conn.close()

        is_group = "@chatroom" in username
        for row in rows:
            if len(results) >= limit:
                break
            parsed = parse_message(row["message_content"], row["local_type"], is_group, contacts)
            if keyword_lower not in parsed["text"].lower():
                continue
            results.append({
                "username": username,
                "display_name": contacts.get(username, username),
                "is_group": is_group,
                "sender": parsed["sender"],
                "text": parsed["text"],
                "type": parsed["type"],
                "timestamp": row["create_time"] or 0,
                "time": ts_to_string(row["create_time"], "%Y-%m-%d %H:%M"),
                "local_id": row["local_id"],
            })
    results.sort(key=lambda item: item["timestamp"], reverse=True)
    return results[:limit]


def search_messages(keyword, limit=50, decrypted_dir=DECRYPTED_DIR):
    if not keyword:
        return [], "empty"
    results, method = search_messages_fts(keyword, limit, decrypted_dir)
    if results:
        return results, method
    raw = search_messages_raw(keyword, limit, decrypted_dir)
    return raw, "raw_like"
