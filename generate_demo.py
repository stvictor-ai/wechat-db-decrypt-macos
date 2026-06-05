#!/usr/bin/env python3
"""Generate synthetic demo data for wechat-db-decrypt-macos.

Creates a demo/ directory with fake WeChat databases so users
without real WeChat data can explore every feature.

Usage:
    python3 generate_demo.py          # creates ./demo/
    python3 generate_demo.py --clean  # removes ./demo/ first
    python3 web_server.py --demo      # serves from ./demo/
"""
import argparse
import hashlib
import os
import random
import shutil
import sqlite3
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEMO_DIR = os.path.join(SCRIPT_DIR, "demo")

random.seed(42)

# ──────────────────────────────────────────────────────────── personas ──────

ME = "wxid_demo_self"

_CONTACTS = [
    {"username": "wxid_zhangwei88",    "remark": "张伟",   "nick_name": "大头"},
    {"username": "wxid_chenxl_2019",   "remark": "陈晓琳", "nick_name": "陈晓琳"},
    {"username": "wxid_limingyang",    "remark": "李明阳", "nick_name": "老李"},
    {"username": "wxid_wangfang88",    "remark": "王芳",   "nick_name": "WangFang"},
    {"username": "wxid_sunli_work",    "remark": "孙丽",   "nick_name": "孙丽"},
    # group participants (no individual session)
    {"username": "wxid_zhaolei_dev",   "remark": "赵磊",   "nick_name": "Racer赵磊"},
    {"username": "wxid_linli_design",  "remark": "",        "nick_name": "林丽"},
]
_GROUP = {"username": "58391047@chatroom", "nick_name": "项目协作群"}

# contacts that have 1-on-1 sessions (ordered by recency)
_SESSION_CONTACTS = ["wxid_zhangwei88", "wxid_chenxl_2019",
                     "wxid_sunli_work",  "wxid_wangfang88", "wxid_limingyang"]

# ──────────────────────────────────────────────────────── timestamp helpers ──

def _ts(year, month, day, hour=12, minute=0):
    import datetime
    return int(datetime.datetime(year, month, day, hour, minute).timestamp())


def _jitter(base, max_minutes=90):
    return base + random.randint(0, max_minutes * 60)


# ──────────────────────────────────────────────────── message corpus ─────────
#
# Each tuple: (local_type, content, sender_is_me)
#   local_type 1  = text
#   local_type 3  = image     (binary placeholder)
#   local_type 34 = voice
#   local_type 43 = video
#   local_type 49 = link/file
#   local_type 10000 = system
#   local_type 10002 = recall

def _txt(text, mine=True): return (1, text, mine)
def _img(mine=True):        return (3,  b"\x00img", mine)
def _voice(mine=True):      return (34, b"\x00voice", mine)
def _video(mine=True):      return (43, b"\x00video", mine)
def _file(mine=True):       return (49, b"\x00file", mine)
def _sys(text):             return (10000, text, False)
def _recall(mine=True):     return (10002, b"\x00recall", mine)


# 张伟 — 老朋友，日常闲聊 + 约饭 + 偶尔工作
_ZHANG_WEI_MSGS = [
    # 1月
    _txt("新年快乐！今年要搞点大事情😄", mine=False),
    _txt("哈哈同乐！你说什么大事？"),
    _txt("先把身子骨练起来，年后跑步去", mine=False),
    _txt("行，周末约"),
    _voice(mine=False),
    _txt("好，周六早上七点，老地方"),
    _txt("没问题，带你媳妇吗", mine=False),
    _txt("她懒得起😂 就我们俩"),
    _sys("「张伟」 撤回了一条消息"),
    _txt("算了我不说了哈哈", mine=False),
    # 2月
    _txt("春节在家闲死了，你在哪", mine=False),
    _txt("老家，刚回来。你没回去？"),
    _txt("今年不想挤高铁，就在这边过了", mine=False),
    _txt("那约一下，去你那边馆子搓一顿"),
    _img(mine=False),
    _txt("这是昨晚吃的，你来晚了", mine=False),
    _txt("这也太好吃了叫我！！！"),
    _voice(mine=False),
    _txt("哈哈下次下次"),
    # 3月
    _txt("你那个项目完成了吗", mine=False),
    _txt("差一点，还有两个接口没对"),
    _txt("加把劲，我这边客户催得很", mine=False),
    _txt("我知道，今晚搞定"),
    _txt("辛苦了，搞完请你喝酒", mine=False),
    _txt("好！说到做到啊"),
    _img(),
    _txt("这是新版UI，你觉得怎么样"),
    _txt("还行，图标可以再大一点", mine=False),
    _txt("好，我让设计改"),
    # 4月
    _txt("周末打球不", mine=False),
    _txt("好啊，几点"),
    _txt("下午两点，体育馆", mine=False),
    _txt("收到，我带球"),
    _voice(),
    _txt("哈哈听到了", mine=False),
    _txt("打完要去吃什么", mine=False),
    _txt("串串！！！"),
    _txt("行，我知道一家新开的", mine=False),
    # 5月
    _txt("你有没有合同模板", mine=False),
    _txt("有，稍等发你"),
    _file(),
    _txt("这个改一下公司名字就行"),
    _txt("好的谢谢兄弟", mine=False),
    _txt("小事"),
    _img(mine=False),
    _txt("这是最新的方案，你看看"),
    _txt("可以，下周开会讨论"),
    # 6月
    _txt("周末去哪", mine=False),
    _txt("没计划，要不骑车？"),
    _txt("好啊，沿江那条路很爽", mine=False),
    _txt("行，早点出发，九点怎么样"),
    _txt("太早了…… 十点", mine=False),
    _txt("哈哈好的，十点见"),
    _img(mine=False),
    _txt("你看这景色，今天超好看"),
    _txt("nb，发我朋友圈用", mine=False),
    _recall(),
    _txt("不发了哈哈，私藏", mine=False),
    # 7月
    _txt("你看了昨晚的比赛没", mine=False),
    _txt("看了！最后那个球太刺激了"),
    _txt("对！我差点从沙发上跳起来", mine=False),
    _txt("哈哈我直播截了好几个图"),
    _img(),
    _txt("这就是最精彩的时刻"),
    _txt("太帅了！", mine=False),
    # 8月
    _txt("最近项目忙死了", mine=False),
    _txt("我也是，连周末都在上班"),
    _txt("唉，不过快了，下个月应该轻松", mine=False),
    _txt("那就好，到时候出去旅游"),
    _txt("去云南怎么样", mine=False),
    _txt("行！我来订酒店"),
    _voice(mine=False),
    _txt("好的，已经记下来了"),
    # 9月
    _txt("云南的票买了吗", mine=False),
    _txt("买了，10月3号出发"),
    _txt("太棒了！！！", mine=False),
    _img(mine=False),
    _txt("我给你看看攻略"),
    _txt("看了，行程很满啊", mine=False),
    _txt("多玩一点，来回不容易"),
    # 10月
    _txt("云南超美！！！", mine=False),
    _img(mine=False),
    _img(),
    _txt("这张拍得好", mine=False),
    _txt("我来修了一下，发你"),
    _img(),
    _txt("nb！！！大师", mine=False),
    _voice(mine=False),
    _txt("哈哈，喜欢就好"),
    # 11月
    _txt("天冷了，多穿衣服", mine=False),
    _txt("好，你也是"),
    _txt("上次说的那个项目你怎么看", mine=False),
    _txt("我觉得可以，就是时间有点赶"),
    _txt("我也这么觉得，跟他说推迟一周", mine=False),
    _txt("好，我支持你的决定"),
    _video(mine=False),
    _txt("你看这个，太搞笑了"),
    _txt("哈哈哈哈哈哈哈哈"),
    # 12月
    _txt("年底了，复盘一下今年", mine=False),
    _txt("总体还不错，比去年进步"),
    _txt("对，明年继续加油", mine=False),
    _txt("一起！"),
    _sys("你已和「张伟」成为微信好友，开始聊天吧"),
    _txt("元旦快乐！！！", mine=False),
    _txt("同乐！！！"),
    _img(mine=False),
    _txt("这是朋友圈发的，分享给你看"),
    _txt("好看！你摄影越来越好了", mine=False),
]

# 陈晓琳 — 日常聊天，生活话题
_CHEN_XIAOLIN_MSGS = [
    _txt("你这周末有空吗", mine=False),
    _txt("有啊，干嘛"),
    _txt("一起去看个展览", mine=False),
    _txt("好啊，什么展"),
    _img(mine=False),
    _txt("这个！摄影展，看起来很好"),
    _txt("行，周六下午怎么样"),
    _txt("好的，下午两点在地铁口见", mine=False),
    _img(),
    _txt("发你今天拍的照片"),
    _txt("拍得好！！！你用什么相机", mine=False),
    _txt("手机拍的哈哈"),
    _txt("手机也能拍成这样太厉害了", mine=False),
    _voice(mine=False),
    _txt("谢谢😊"),
    _txt("你最近在做什么项目", mine=False),
    _txt("一个app，做用户数据分析的"),
    _txt("好有意思！我能试用吗", mine=False),
    _txt("等上线了给你邀请码"),
    _txt("谢谢！期待！", mine=False),
    _txt("昨晚看了个电影，好好哭", mine=False),
    _txt("什么电影，这么感人"),
    _txt("隐入尘烟，你看过吗", mine=False),
    _txt("没有，推荐吗"),
    _txt("强烈推荐，但要准备好纸巾", mine=False),
    _txt("好，周末看"),
    _img(mine=False),
    _txt("这是昨晚做的蛋糕，出锅了！"),
    _txt("天哪好好看！！！你自己做的？"),
    _txt("嗯嗯，学了好久", mine=False),
    _voice(),
    _txt("哇真的！！！下次给我留一块😂"),
    _txt("好啊哈哈", mine=False),
    _txt("最近在健身吗", mine=False),
    _txt("有，每周三次，你呢"),
    _txt("我也开始了，但是好累啊", mine=False),
    _txt("坚持一个月就好了，然后就上瘾"),
    _txt("真的吗……我试试", mine=False),
    _img(mine=False),
    _txt("这是我今天的健身记录"),
    _txt("厉害！！！你坚持了多久了", mine=False),
    _txt("三个月了，感觉很好"),
    _sys("你已和「陈晓琳」成为微信好友，开始聊天吧"),
    _txt("上周聚会你怎么没来", mine=False),
    _txt("加班了，下次一定"),
    _txt("好，下次提前说一声", mine=False),
    _txt("好的好的"),
    _recall(mine=False),
    _txt("刚才说错了，没事😊", mine=False),
]

# 李明阳 — 老同学，偶尔联系
_LI_MINGYANG_MSGS = [
    _txt("好久不见！你最近怎么样", mine=False),
    _txt("还好还好，你呢"),
    _txt("还行，一直在上海这边", mine=False),
    _txt("哦，我在北京，哪天路过找你"),
    _txt("好啊！随时", mine=False),
    _txt("上次同学聚会你也没来", mine=False),
    _txt("哈哈，出差了，错过了"),
    _txt("下次别错过了，大家都想你", mine=False),
    _img(mine=False),
    _txt("这是那次聚会，看看"),
    _txt("大家变化好大！"),
    _txt("是啊，岁月不饶人哈哈", mine=False),
    _txt("你有那个谁的联系方式吗", mine=False),
    _txt("谁？"),
    _txt("大学室友，叫什么来着……", mine=False),
    _txt("哦！他现在在深圳，我把你加给他"),
    _txt("好的谢谢！", mine=False),
    _voice(mine=False),
    _txt("语音没听清，你说什么"),
    _txt("我说下周北京有空出来喝茶不", mine=False),
    _txt("好啊！周几"),
    _txt("周五下午", mine=False),
    _txt("可以，发我位置"),
    _file(mine=False),
    _txt("这是个文档，帮我看看写得怎么样"),
    _txt("好，我看了回你"),
    _txt("谢谢！", mine=False),
]

# 王芳 — 工作关系，话不多
_WANG_FANG_MSGS = [
    _txt("周一的会议改到下午三点了", mine=False),
    _txt("好的，收到"),
    _txt("那份报告今天能发我吗", mine=False),
    _txt("可以，下班前给你"),
    _file(),
    _txt("发你了，看一下"),
    _txt("收到，谢谢！", mine=False),
    _sys("「王芳」 撤回了一条消息"),
    _txt("那个合同你那边有副本吗", mine=False),
    _txt("有，稍等"),
    _file(),
    _txt("好的，我签了发回给你", mine=False),
    _voice(mine=False),
    _txt("好，知道了"),
    _txt("明天的演示材料准备好了吗", mine=False),
    _txt("准备好了，要发你预览吗"),
    _txt("不用了，明天直接演示就行", mine=False),
    _txt("好的"),
]

# 孙丽 — 同事，偶尔工作讨论
_SUN_LI_MSGS = [
    _txt("系统今天又挂了", mine=False),
    _txt("是哦，我看了日志，是数据库连接超时"),
    _txt("能修吗", mine=False),
    _txt("可以，需要重启一下，等我五分钟"),
    _txt("好的，快点", mine=False),
    _txt("好了，试试看"),
    _txt("可以了！谢谢！", mine=False),
    _voice(),
    _txt("收到，我处理一下", mine=False),
    _txt("你这周五能来开会吗", mine=False),
    _txt("可以，几点"),
    _txt("下午两点", mine=False),
    _txt("行，我到时候过去"),
    _img(mine=False),
    _txt("这是新设计稿，你看效果怎么样"),
    _txt("挺好的，细节再打磨一下"),
    _recall(mine=False),
    _txt("刚才发错了", mine=False),
    _txt("哦哦没事"),
]

# 项目协作群 messages (prefixed with sender)
_GROUP_MSGS = [
    (1, "wxid_zhaolei_dev",   "大家好！新人报到，以后多关照"),
    (1, ME,                    "欢迎欢迎！"),
    (1, "wxid_linli_design",  "哇欢迎！"),
    (1, "wxid_zhaolei_dev",   "这个接口文档发一下"),
    (1, ME,                    "好，我整理一下"),
    (49, ME,                   b"\x00file"),   # file
    (1, "wxid_zhaolei_dev",   "收到，谢谢！"),
    (1, "wxid_linli_design",  "这周设计稿我明天出"),
    (1, ME,                    "好的，到时候一起review"),
    (3, "wxid_linli_design",  b"\x00img"),     # image
    (1, "wxid_linli_design",  "这是初版，大家看看"),
    (1, "wxid_zhaolei_dev",   "整体不错，按钮颜色我觉得可以调一下"),
    (1, "wxid_linli_design",  "好的，我改"),
    (1, ME,                    "其他都ok，就按钮那个改一下"),
    (10000, "",                "「赵磊」 修改了群名称"),
    (1, "wxid_zhaolei_dev",   "今天上线了！大家测一下"),
    (1, ME,                    "测了，登录和主流程ok"),
    (1, "wxid_linli_design",  "我这边搜索有点问题"),
    (1, "wxid_zhaolei_dev",   "我看一下"),
    (1, "wxid_zhaolei_dev",   "修好了，重新部署了"),
    (1, "wxid_linli_design",  "好了！太棒了！"),
    (1, ME,                    "撒花🎉🎉🎉"),
    (43, "wxid_zhaolei_dev",  b"\x00video"),   # video
    (1, "wxid_zhaolei_dev",   "庆祝一下，这是上次聚餐视频"),
    (1, "wxid_linli_design",  "哈哈哈哈好怀念"),
    (1, ME,                    "下次再搞！"),
    (10002, "wxid_zhaolei_dev", b"\x00recall"),
]

# ──────────────────────────────────────────────────── utilities ──────────────

def _mkdir(*parts):
    os.makedirs(os.path.join(*parts), exist_ok=True)


def _connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _md5(text):
    return "Msg_" + hashlib.md5(text.encode()).hexdigest()


def _display(c):
    return c["remark"] or c.get("nick_name", c["username"])


# ──────────────────────────────────────────────── build contact.db ───────────

def _build_contact_db():
    db = os.path.join(DEMO_DIR, "contact", "contact.db")
    conn = _connect(db)
    conn.execute("""CREATE TABLE IF NOT EXISTS contact (
        id INTEGER PRIMARY KEY,
        username TEXT, local_type INTEGER DEFAULT 0, alias TEXT DEFAULT '',
        encrypt_username TEXT DEFAULT '', flag INTEGER DEFAULT 0,
        delete_flag INTEGER DEFAULT 0, verify_flag INTEGER DEFAULT 0,
        remark TEXT DEFAULT '', remark_quan_pin TEXT DEFAULT '',
        remark_pin_yin_initial TEXT DEFAULT '', nick_name TEXT DEFAULT '',
        pin_yin_initial TEXT DEFAULT '', quan_pin TEXT DEFAULT '',
        big_head_url TEXT DEFAULT '', small_head_url TEXT DEFAULT '',
        head_img_md5 TEXT DEFAULT '', chat_room_notify INTEGER DEFAULT 0,
        is_in_chat_room INTEGER DEFAULT 0, description TEXT DEFAULT '',
        extra_buffer BLOB, chat_room_type INTEGER DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS stranger (
        id INTEGER PRIMARY KEY, username TEXT, local_type INTEGER DEFAULT 0,
        alias TEXT DEFAULT '', encrypt_username TEXT DEFAULT '',
        flag INTEGER DEFAULT 0, delete_flag INTEGER DEFAULT 0,
        verify_flag INTEGER DEFAULT 0, remark TEXT DEFAULT '',
        remark_quan_pin TEXT DEFAULT '', remark_pin_yin_initial TEXT DEFAULT '',
        nick_name TEXT DEFAULT '', pin_yin_initial TEXT DEFAULT '',
        quan_pin TEXT DEFAULT '', big_head_url TEXT DEFAULT '',
        small_head_url TEXT DEFAULT '', head_img_md5 TEXT DEFAULT '',
        chat_room_notify INTEGER DEFAULT 0, is_in_chat_room INTEGER DEFAULT 0,
        description TEXT DEFAULT '', extra_buffer BLOB,
        chat_room_type INTEGER DEFAULT 0
    )""")
    conn.execute("CREATE TABLE IF NOT EXISTS name2id (username TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE IF NOT EXISTS encrypt_name2id (username TEXT PRIMARY KEY)")
    conn.execute("""CREATE TABLE IF NOT EXISTS chat_room (
        id INTEGER PRIMARY KEY, username TEXT, owner TEXT DEFAULT '',
        ext_buffer BLOB
    )""")

    all_c = _CONTACTS + [
        {"username": ME,                   "remark": "",     "nick_name": "我"},
        {"username": _GROUP["username"],   "remark": "",     "nick_name": _GROUP["nick_name"]},
    ]
    for c in all_c:
        conn.execute(
            "INSERT OR IGNORE INTO contact (username, remark, nick_name) VALUES (?, ?, ?)",
            (c["username"], c.get("remark", ""), c.get("nick_name", c["username"])),
        )
    conn.execute(
        "INSERT OR IGNORE INTO chat_room (username, owner) VALUES (?, ?)",
        (_GROUP["username"], ME),
    )
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────── build message_0.db ─────────

def _build_messages():
    db = os.path.join(DEMO_DIR, "message", "message_0.db")
    conn = _connect(db)
    conn.execute("""CREATE TABLE IF NOT EXISTS Name2Id (
        user_name TEXT PRIMARY KEY, is_session INTEGER DEFAULT 0
    )""")

    # assign numeric rowids: 1=me, 2..N=contacts, N+1=group
    id_map = {ME: 1}
    for i, c in enumerate(_CONTACTS, start=2):
        id_map[c["username"]] = i
    id_map[_GROUP["username"]] = len(_CONTACTS) + 2

    for username, uid in id_map.items():
        is_sess = 1 if username in _SESSION_CONTACTS or username == _GROUP["username"] else 0
        conn.execute(
            "INSERT OR IGNORE INTO Name2Id(rowid, user_name, is_session) VALUES (?, ?, ?)",
            (uid, username, is_sess),
        )

    def make_table(username):
        tname = _md5(username)
        conn.execute(f"""CREATE TABLE IF NOT EXISTS [{tname}] (
            local_id INTEGER PRIMARY KEY,
            server_id INTEGER DEFAULT 0,
            local_type INTEGER DEFAULT 1,
            sort_seq INTEGER DEFAULT 0,
            real_sender_id INTEGER DEFAULT 0,
            create_time INTEGER DEFAULT 0,
            status INTEGER DEFAULT 0,
            upload_status INTEGER DEFAULT 0,
            download_status INTEGER DEFAULT 0,
            server_seq INTEGER DEFAULT 0,
            origin_source INTEGER DEFAULT 0,
            source TEXT DEFAULT '',
            message_content TEXT,
            compress_content TEXT DEFAULT '',
            packed_info_data BLOB
        )""")
        return tname

    # helper: insert rows with ascending timestamps
    voice_rows = []  # (username, local_id, size_bytes)

    def insert_chat(username, msg_list, start_ts, gap_seconds=1200):
        tname = make_table(username)
        my_id = id_map[ME]
        sender_id_map = {c["username"]: id_map[c["username"]] for c in _CONTACTS}
        contact_id = id_map.get(username, 0)
        ts = start_ts
        lid = 1
        jitter_min = min(gap_seconds // 60, 120)  # cap jitter at 2 h
        for (mtype, content, mine) in msg_list:
            ts = _jitter(ts, max_minutes=jitter_min)
            if isinstance(content, bytes):
                blob = content
                text_content = None
            else:
                blob = None
                text_content = content
            real_sender = my_id if mine else contact_id
            conn.execute(
                f"INSERT OR IGNORE INTO [{tname}] VALUES (?,0,?,?,?,?,0,0,0,0,0,'',?,''," + (
                    "?" if blob is not None else "NULL") + ")",
                (lid, mtype, lid * 10, real_sender, ts,
                 text_content, blob) if blob is not None else
                (lid, mtype, lid * 10, real_sender, ts, text_content),
            )
            if mtype == 34:  # voice
                sz = random.randint(8000, 40000)
                voice_rows.append((username, lid, sz))
            lid += 1
            ts += gap_seconds
        return ts  # last timestamp

    def insert_group(start_ts, gap_seconds=800):
        tname = make_table(_GROUP["username"])
        my_id = id_map[ME]
        ts = start_ts
        lid = 1
        jitter_min = min(gap_seconds // 60, 60)
        for (mtype, sender_u, content) in _GROUP_MSGS:
            ts = _jitter(ts, max_minutes=jitter_min)
            real_sender = id_map.get(sender_u, my_id) if sender_u else 0
            if isinstance(content, bytes):
                conn.execute(
                    f"INSERT OR IGNORE INTO [{tname}] VALUES (?,0,?,?,?,?,0,0,0,0,0,'',NULL,'',?)",
                    (lid, mtype, lid * 10, real_sender, ts, content),
                )
            else:
                prefix = ""
                if sender_u and sender_u != ME:
                    nick = next((c["nick_name"] for c in _CONTACTS if c["username"] == sender_u), sender_u)
                    prefix = f"{sender_u}:\n"
                conn.execute(
                    f"INSERT OR IGNORE INTO [{tname}] VALUES (?,0,?,?,?,?,0,0,0,0,0,'',?,'',NULL)",
                    (lid, mtype, lid * 10, real_sender, ts, prefix + content if prefix else content),
                )
            lid += 1
            ts += gap_seconds

    # timestamps and per-conversation gaps — spread across 2024 realistically
    # gap_seconds controls how far apart consecutive messages are
    conversation_cfg = {
        # (start_ts, gap_seconds) — Zhang Wei: daily contact all year
        "wxid_zhangwei88":  (_ts(2024, 1, 3,  9),  86_400),   # ~1 day/msg, ends ~Dec
        # Chen Xiaolin: bi-weekly from March
        "wxid_chenxl_2019": (_ts(2024, 3, 1, 14), 172_800),   # ~2 days/msg
        # Sun Li: work colleague, occasional from Sep
        "wxid_sunli_work":  (_ts(2024, 9, 1, 10), 259_200),   # ~3 days/msg
        # Wang Fang: brief Oct-Nov exchange
        "wxid_wangfang88":  (_ts(2024, 10, 5, 9), 172_800),
        # Li Mingyang: sporadic June reunion
        "wxid_limingyang":  (_ts(2024, 6, 18, 15), 259_200),
        _GROUP["username"]: (_ts(2024, 4, 1, 9),   86_400),    # group: 1 day/msg
    }
    last_ts = {}
    for u in _SESSION_CONTACTS:
        msgs = {
            "wxid_zhangwei88":  _ZHANG_WEI_MSGS,
            "wxid_chenxl_2019": _CHEN_XIAOLIN_MSGS,
            "wxid_sunli_work":  _SUN_LI_MSGS,
            "wxid_wangfang88":  _WANG_FANG_MSGS,
            "wxid_limingyang":  _LI_MINGYANG_MSGS,
        }[u]
        base, gap = conversation_cfg[u]
        last_ts[u] = insert_chat(u, msgs, base, gap_seconds=gap)

    base_g, gap_g = conversation_cfg[_GROUP["username"]]
    insert_group(base_g, gap_seconds=gap_g)
    last_ts[_GROUP["username"]] = base_g + len(_GROUP_MSGS) * gap_g

    conn.commit()
    conn.close()
    return voice_rows, last_ts


# ──────────────────────────────────────────── build media_0.db (voice) ───────

def _build_media_db(voice_rows):
    db = os.path.join(DEMO_DIR, "message", "media_0.db")
    conn = _connect(db)
    conn.execute("""CREATE TABLE IF NOT EXISTS Name2Id (
        user_name TEXT PRIMARY KEY
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS VoiceInfo (
        local_id INTEGER,
        chat_name_id INTEGER,
        voice_data BLOB
    )""")

    uid_cache = {}

    def get_uid(username):
        if username not in uid_cache:
            row = conn.execute("SELECT rowid FROM Name2Id WHERE user_name = ?", (username,)).fetchone()
            if not row:
                conn.execute("INSERT INTO Name2Id (user_name) VALUES (?)", (username,))
                row = conn.execute("SELECT rowid FROM Name2Id WHERE user_name = ?", (username,)).fetchone()
            uid_cache[username] = row[0]
        return uid_cache[username]

    for (username, local_id, size) in voice_rows:
        uid = get_uid(username)
        conn.execute(
            "INSERT INTO VoiceInfo (local_id, chat_name_id, voice_data) VALUES (?, ?, ?)",
            (local_id, uid, bytes(size)),
        )
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────── build session.db ───────────

# Override session sort timestamps to show realistic recency ordering
_SESSION_DISPLAY_TS = {
    "wxid_zhangwei88":    _ts(2024, 12, 31, 20),
    "wxid_chenxl_2019":   _ts(2024, 12, 25, 11),
    "wxid_sunli_work":    _ts(2024, 12, 20, 17),
    "wxid_wangfang88":    _ts(2024, 12, 15, 9),
    "wxid_limingyang":    _ts(2024, 11, 8, 15),
    _GROUP["username"]:   _ts(2024, 10, 20, 14),
}


def _build_session_db(last_ts):
    db = os.path.join(DEMO_DIR, "session", "session.db")
    conn = _connect(db)
    conn.execute("""CREATE TABLE IF NOT EXISTS SessionTable (
        username TEXT PRIMARY KEY,
        type INTEGER DEFAULT 0,
        unread_count INTEGER DEFAULT 0,
        unread_first_msg_srv_id INTEGER DEFAULT 0,
        unread_first_pat_msg_local_id INTEGER DEFAULT 0,
        unread_first_pat_msg_sort_seq INTEGER DEFAULT 0,
        is_hidden INTEGER DEFAULT 0,
        summary TEXT DEFAULT '',
        draft TEXT DEFAULT '',
        status INTEGER DEFAULT 0,
        last_timestamp INTEGER DEFAULT 0,
        sort_timestamp INTEGER DEFAULT 0,
        last_clear_unread_timestamp INTEGER DEFAULT 0,
        last_msg_locald_id INTEGER DEFAULT 0,
        last_msg_type INTEGER DEFAULT 1,
        last_msg_sub_type INTEGER DEFAULT 0,
        last_msg_sender TEXT DEFAULT '',
        last_sender_display_name TEXT DEFAULT '',
        last_msg_ext_type INTEGER DEFAULT 0
    )""")
    conn.execute("CREATE TABLE IF NOT EXISTS Name2Id (user_name TEXT PRIMARY KEY)")

    summaries = {
        "wxid_zhangwei88":  "元旦快乐！！！",
        "wxid_chenxl_2019": "下次别错过了，大家都想你",
        "wxid_sunli_work":  "哦哦没事",
        "wxid_wangfang88":  "好的",
        "wxid_limingyang":  "谢谢！",
        _GROUP["username"]: "下次再搞！",
    }

    ordered = sorted(_SESSION_DISPLAY_TS.items(), key=lambda x: x[1], reverse=True)
    for username, display_ts in ordered:
        conn.execute(
            "INSERT OR REPLACE INTO SessionTable "
            "(username, summary, last_timestamp, sort_timestamp) VALUES (?,?,?,?)",
            (username, summaries.get(username, ""), display_ts, display_ts),
        )
        conn.execute(
            "INSERT OR IGNORE INTO Name2Id (user_name) VALUES (?)", (username,)
        )
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────── build message_fts.db ───────

def _build_fts_db():
    """Populate fts content-table fallback (plain table, not FTS4).

    wechat_data.search_messages_fts falls back to reading
    message_fts_v4_0_content when MATCH fails on a plain table.
    """
    db = os.path.join(DEMO_DIR, "message", "message_fts.db")
    conn = _connect(db)
    conn.execute("CREATE TABLE IF NOT EXISTS name2id (username TEXT PRIMARY KEY)")

    id_map = {ME: 1}
    for i, c in enumerate(_CONTACTS, start=2):
        id_map[c["username"]] = i
    id_map[_GROUP["username"]] = len(_CONTACTS) + 2

    for username, uid in id_map.items():
        conn.execute(
            "INSERT OR IGNORE INTO name2id(rowid, username) VALUES (?, ?)",
            (uid, username),
        )

    conn.execute("""CREATE TABLE IF NOT EXISTS message_fts_v4_0 (
        acontent TEXT,
        message_local_id INTEGER,
        sort_seq INTEGER,
        local_type INTEGER,
        session_id INTEGER,
        sender_id INTEGER,
        create_time INTEGER
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS message_fts_v4_0_content (
        id INTEGER PRIMARY KEY,
        c0 TEXT,     -- acontent
        c1 INTEGER,  -- message_local_id
        c2 INTEGER,  -- sort_seq
        c3 INTEGER,  -- local_type
        c4 INTEGER,  -- session_id
        c5 INTEGER,  -- sender_id
        c6 INTEGER   -- create_time
    )""")

    # index a representative sample of plain-text messages for search
    fts_rows = []

    def add(text, session_username, sender_username, ts, local_id, msg_type=1):
        sid = id_map.get(session_username, 0)
        sender = id_map.get(sender_username, id_map[ME])
        fts_rows.append((text, local_id, local_id * 10, msg_type, sid, sender, ts))

    # Zhang Wei texts
    ts = _ts(2024, 1, 3, 9)
    for i, (mtype, content, mine) in enumerate(_ZHANG_WEI_MSGS):
        if mtype == 1 and isinstance(content, str):
            sender = ME if mine else "wxid_zhangwei88"
            add(content, "wxid_zhangwei88", sender, ts + i * 86_400, i + 1)

    # Chen Xiaolin texts
    ts = _ts(2024, 3, 1, 14)
    for i, (mtype, content, mine) in enumerate(_CHEN_XIAOLIN_MSGS):
        if mtype == 1 and isinstance(content, str):
            sender = ME if mine else "wxid_chenxl_2019"
            add(content, "wxid_chenxl_2019", sender, ts + i * 172_800, i + 1)

    # Group texts
    ts = _ts(2024, 4, 1, 9)
    for i, (mtype, sender_u, content) in enumerate(_GROUP_MSGS):
        if mtype == 1 and isinstance(content, str) and content:
            add(content, _GROUP["username"], sender_u or ME, ts + i * 86_400, i + 1)

    for row in fts_rows:
        conn.execute(
            "INSERT INTO message_fts_v4_0_content (c0,c1,c2,c3,c4,c5,c6) VALUES (?,?,?,?,?,?,?)",
            row,
        )
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────────────────── main ────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clean", action="store_true", help="remove demo/ first")
    args = parser.parse_args()

    if args.clean and os.path.isdir(DEMO_DIR):
        shutil.rmtree(DEMO_DIR)
        print("Removed existing demo/")

    _mkdir(DEMO_DIR, "contact")
    _mkdir(DEMO_DIR, "message")
    _mkdir(DEMO_DIR, "session")

    print("Building contact.db …")
    _build_contact_db()

    print("Building message_0.db …")
    voice_rows, last_ts = _build_messages()

    print(f"  {len(voice_rows)} voice messages → media_0.db")
    _build_media_db(voice_rows)

    print("Building session.db …")
    _build_session_db(last_ts)

    print("Building message_fts.db …")
    _build_fts_db()

    total_msgs = (
        len(_ZHANG_WEI_MSGS) + len(_CHEN_XIAOLIN_MSGS)
        + len(_LI_MINGYANG_MSGS) + len(_WANG_FANG_MSGS)
        + len(_SUN_LI_MSGS) + len(_GROUP_MSGS)
    )
    print(f"\nDone. {total_msgs} synthetic messages across "
          f"{len(_SESSION_CONTACTS) + 1} conversations.")
    print(f"Demo data written to: {DEMO_DIR}")
    print("\nTo launch the demo:")
    print("  python3 web_server.py --demo")


if __name__ == "__main__":
    main()
