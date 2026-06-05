import os
import sqlite3
import tempfile
import unittest

import wechat_data


def _mkdir(path):
    os.makedirs(path, exist_ok=True)


class WeChatDataTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        _mkdir(os.path.join(self.root, "contact"))
        _mkdir(os.path.join(self.root, "session"))
        _mkdir(os.path.join(self.root, "message"))

        self.me = "wxid_me_example"
        self.friend = "wxid_friend_example"
        self.group = "12345678@chatroom"
        self.official = "gh_official_example"

        self._create_contacts()
        self._create_session()
        self._create_message_db()
        self._create_fts_db()

    def tearDown(self):
        self.tmp.cleanup()

    def _create_contacts(self):
        db = os.path.join(self.root, "contact", "contact.db")
        conn = sqlite3.connect(db)
        try:
            conn.execute(
                "CREATE TABLE contact (username TEXT, local_type INTEGER, verify_flag INTEGER, remark TEXT, nick_name TEXT, small_head_url TEXT)"
            )
            conn.execute(
                "CREATE TABLE stranger (username TEXT, local_type INTEGER, verify_flag INTEGER, remark TEXT, nick_name TEXT, small_head_url TEXT)"
            )
            conn.executemany(
                "INSERT INTO contact VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (self.me, 0, 0, "", "Me", ""),
                    (self.friend, 0, 0, "Alice", "Alice Nick", ""),
                    (self.group, 0, 0, "", "Project Group", ""),
                    ("wxid_group_sender", 0, 0, "Bob", "Bob Nick", ""),
                ],
            )
            conn.execute(
                "INSERT INTO contact VALUES (?, ?, ?, ?, ?, ?)",
                (self.official, 1, 24, "", "Official Account", ""),
            )
            conn.commit()
        finally:
            conn.close()

    def _create_session(self):
        db = os.path.join(self.root, "session", "session.db")
        conn = sqlite3.connect(db)
        try:
            conn.execute("""
                CREATE TABLE SessionTable (
                    username TEXT PRIMARY KEY,
                    type INTEGER,
                    unread_count INTEGER,
                    unread_first_msg_srv_id INTEGER,
                    unread_first_pat_msg_local_id INTEGER,
                    unread_first_pat_msg_sort_seq INTEGER,
                    is_hidden INTEGER,
                    summary TEXT,
                    draft TEXT,
                    status INTEGER,
                    last_timestamp INTEGER,
                    sort_timestamp INTEGER,
                    last_clear_unread_timestamp INTEGER,
                    last_msg_locald_id INTEGER,
                    last_msg_type INTEGER,
                    last_msg_sub_type INTEGER,
                    last_msg_sender TEXT,
                    last_sender_display_name TEXT,
                    last_msg_ext_type INTEGER
                )
            """)
            conn.execute(
                "INSERT INTO SessionTable VALUES (?, 0, 0, 0, 0, 0, 0, ?, '', 0, ?, ?, 0, 0, 1, 0, '', '', 0)",
                (self.friend, "latest synthetic message", 1_700_000_030, 1_700_000_030),
            )
            conn.commit()
        finally:
            conn.close()

    def _create_message_db(self):
        db = os.path.join(self.root, "message", "message_0.db")
        table = wechat_data.username_to_table(self.friend)
        group_table = wechat_data.username_to_table(self.group)
        conn = sqlite3.connect(db)
        try:
            conn.execute("CREATE TABLE Name2Id (user_name TEXT PRIMARY KEY, is_session INTEGER)")
            conn.executemany(
                "INSERT INTO Name2Id(rowid, user_name, is_session) VALUES (?, ?, ?)",
                [(1, self.me, 0), (2, self.friend, 1), (3, self.group, 1)],
            )
            conn.execute(f"""
                CREATE TABLE [{table}] (
                    local_id INTEGER PRIMARY KEY,
                    server_id INTEGER,
                    local_type INTEGER,
                    sort_seq INTEGER,
                    real_sender_id INTEGER,
                    create_time INTEGER,
                    status INTEGER,
                    upload_status INTEGER,
                    download_status INTEGER,
                    server_seq INTEGER,
                    origin_source INTEGER,
                    source TEXT,
                    message_content TEXT,
                    compress_content TEXT,
                    packed_info_data BLOB
                )
            """)
            conn.executemany(
                f"INSERT INTO [{table}] VALUES (?, 0, ?, 0, ?, ?, 0, 0, 0, 0, 0, '', ?, '', NULL)",
                [
                    (1, 1, 2, 1_700_000_000, "hello from Alice"),
                    (2, 1, 1, 1_700_000_010, "hello from me"),
                    (3, 1, 2, 1_700_000_020, "keyword in raw message"),
                ],
            )
            conn.execute(f"""
                CREATE TABLE [{group_table}] (
                    local_id INTEGER PRIMARY KEY,
                    server_id INTEGER,
                    local_type INTEGER,
                    sort_seq INTEGER,
                    real_sender_id INTEGER,
                    create_time INTEGER,
                    status INTEGER,
                    upload_status INTEGER,
                    download_status INTEGER,
                    server_seq INTEGER,
                    origin_source INTEGER,
                    source TEXT,
                    message_content TEXT,
                    compress_content TEXT,
                    packed_info_data BLOB
                )
            """)
            conn.executemany(
                f"INSERT INTO [{group_table}] VALUES (?, 0, ?, 0, ?, ?, 0, 0, 0, 0, 0, '', ?, '', NULL)",
                [
                    (1, 1, 0, 1_700_000_050, "wxid_group_sender:\ngroup keyword chat"),
                ],
            )
            conn.commit()
        finally:
            conn.close()

    def _create_fts_db(self):
        db = os.path.join(self.root, "message", "message_fts.db")
        conn = sqlite3.connect(db)
        try:
            conn.execute("CREATE TABLE name2id(username TEXT PRIMARY KEY)")
            conn.executemany(
                "INSERT INTO name2id(rowid, username) VALUES (?, ?)",
                [
                    (1, self.me),
                    (2, self.friend),
                    (3, self.group),
                    (4, "wxid_group_sender"),
                ],
            )
            # A regular table intentionally makes MATCH fail, exercising the content-table fallback.
            conn.execute(
                "CREATE TABLE message_fts_v4_0(acontent TEXT, message_local_id INTEGER, sort_seq INTEGER, local_type INTEGER, session_id INTEGER, sender_id INTEGER, create_time INTEGER)"
            )
            conn.execute(
                "CREATE TABLE message_fts_v4_0_content(id INTEGER PRIMARY KEY, c0 TEXT, c1 INTEGER, c2 INTEGER, c3 INTEGER, c4 INTEGER, c5 INTEGER, c6 INTEGER)"
            )
            conn.execute(
                "INSERT INTO message_fts_v4_0_content VALUES (1, ?, 3, 0, 1, 3, 4, ?)",
                ("group keyword result", 1_700_000_040),
            )
            conn.commit()
        finally:
            conn.close()

    def test_recent_sessions_uses_contact_names(self):
        sessions = wechat_data.get_recent_sessions(5, self.root)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["display_name"], "Alice")
        self.assertEqual(sessions[0]["summary"], "latest synthetic message")

    def test_contact_list_is_enriched_with_recent_session(self):
        contacts = wechat_data.get_contact_list("", 5, self.root)
        self.assertEqual(contacts[0]["display_name"], "Alice")
        self.assertTrue(contacts[0]["has_session"])
        self.assertEqual(contacts[0]["summary"], "latest synthetic message")
        usernames = {c["username"] for c in contacts}
        self.assertNotIn(self.official, usernames)
        self.assertNotIn(self.group, usernames)

    def test_chat_history_merges_sender_identity(self):
        chat = wechat_data.get_chat_history("Alice", 3, decrypted_dir=self.root)
        self.assertEqual(chat["username"], self.friend)
        self.assertEqual([m["text"] for m in chat["messages"]], [
            "hello from Alice",
            "hello from me",
            "keyword in raw message",
        ])
        self.assertEqual([m["is_mine"] for m in chat["messages"]], [False, True, False])

    def test_search_uses_fts_content_fallback(self):
        results, method = wechat_data.search_messages("keyword", 10, self.root)
        self.assertEqual(method, "fts_content")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["display_name"], "Project Group")
        self.assertEqual(results[0]["sender"], "Bob")

    def test_chat_analysis_includes_social_insights(self):
        data = wechat_data.get_chat_analysis("Alice", 20, decrypted_dir=self.root)
        self.assertEqual(data["relationship_profile"]["label"], "事务型短联系")
        self.assertGreaterEqual(len(data["relationship_dimensions"]), 4)
        self.assertGreaterEqual(len(data["social_insights"]), 4)
        self.assertIn("关系类型推断", [item["title"] for item in data["social_insights"]])
        self.assertEqual(data["longest_streak"], 1)

    def test_year_overview_summarizes_active_contacts(self):
        data = wechat_data.get_year_overview(2023, 5, 20, self.root)
        self.assertEqual(data["year"], 2023)
        self.assertEqual(data["analyzed_count"], 1)
        self.assertEqual(data["total_messages"], 3)
        self.assertEqual(data["top_active"][0]["display_name"], "Alice")
        self.assertEqual(data["highlights"]["most_active"]["display_name"], "Alice")

    def test_search_raw_finds_text_messages(self):
        results = wechat_data.search_messages_raw("hello", 10, self.root)
        texts = [r["text"] for r in results]
        self.assertIn("hello from Alice", texts)
        self.assertIn("hello from me", texts)

    def test_search_raw_filters_by_parsed_text(self):
        results = wechat_data.search_messages_raw("keyword", 10, self.root)
        texts = [r["text"] for r in results]
        self.assertIn("keyword in raw message", texts)

    def test_search_raw_finds_group_messages(self):
        results = wechat_data.search_messages_raw("group keyword", 10, self.root)
        self.assertTrue(len(results) >= 1)
        group_results = [r for r in results if r["is_group"]]
        self.assertTrue(len(group_results) >= 1)
        self.assertEqual(group_results[0]["sender"], "Bob")


if __name__ == "__main__":
    unittest.main()
