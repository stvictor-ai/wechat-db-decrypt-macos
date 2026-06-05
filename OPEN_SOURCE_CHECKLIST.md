# Open Source Checklist

Run this before publishing the repository.

## Required

- [ ] Confirm `wechat_keys.json` is not tracked.
- [ ] Confirm `decrypted/` is not tracked.
- [ ] Confirm `exported/` is not tracked.
- [ ] Confirm `.claude/` is not tracked.
- [ ] Remove real chat screenshots and database browser screenshots.
- [ ] Search for private identifiers:

```bash
rg -n "/Users/[^x]|wxid_[a-z0-9]{6,}|[0-9]{8,}@chatroom|wechat_keys" \
  --glob '!decrypted/**' \
  --glob '!exported/**' \
  --glob '!wechat_keys*.json' \
  --glob '!.git/**'
```

Review expected placeholders manually.

- [ ] Check tracked files:

```bash
git ls-files '*.db' '*.sqlite' 'wechat_keys*.json' '.claude/**'
```

This command should print nothing.

## Recommended

- [ ] Decide whether to keep WTFPL or switch to MIT / Apache-2.0.
- [ ] Add synthetic test fixtures for search and chat-history queries.
- [ ] Add screenshots generated from synthetic data only.
- [ ] Add a compatibility table for macOS and WeChat versions.
- [ ] Keep the README focused on authorized local data access.
- [ ] Run `python3 -m unittest discover -s tests`.
