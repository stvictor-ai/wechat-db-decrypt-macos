# Contributing

Contributions are welcome when they improve local-first research, compatibility, safety, or usability.

## Good Contributions

- compatibility fixes for new macOS or WeChat versions
- safer key validation and database handling
- better text decoding for message payloads
- FTS and search improvements
- Web UI improvements that keep data local
- tests using synthetic fixtures
- documentation that reduces privacy or operational risk

## Pull Request Checklist

- Do not include real keys, databases, messages, contacts, screenshots, or logs.
- Keep changes scoped to the feature or fix.
- Prefer shared helpers in `wechat_data.py` for query logic used by CLI, Web UI, and MCP.
- Run syntax checks:

```bash
PYTHONPYCACHEPREFIX=/tmp/wechat_pycache python3 -m py_compile \
  find_key.py find_key_memscan.py decrypt_db.py verify_keys.py \
  export_messages.py wechat_data.py web_server.py mcp_server.py
```

- Run synthetic-data tests:

```bash
python3 -m unittest discover -s tests
```

- If you touch search behavior, test both FTS and fallback paths when possible.

## Issue Guidelines

Please redact:

- usernames and chatroom ids
- message text
- local filesystem paths containing real account names
- key material
- screenshots with personal data

Use placeholders such as `wxid_example`, `12345@chatroom`, `/path/to/db_storage`, and `keyword`.

The GitHub issue and pull request templates repeat these checks intentionally. Privacy review is part of the contribution workflow, not a separate afterthought.
