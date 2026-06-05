# Security Policy

## Sensitive Data

Do not publish or attach:

- `wechat_keys.json` or any extracted key
- files under `decrypted/`
- files under `exported/`
- screenshots containing real messages, contact names, usernames, group names, or paths
- logs containing `wxid_*`, `@chatroom`, database paths, keys, or message contents
- `.claude/` project transcripts if they include private data

If you accidentally committed sensitive data, rotate any affected keys, remove the data from the repository history, and avoid pushing the repository until the history is cleaned.

## Reporting Issues

When reporting a bug, include:

- macOS version
- WeChat version
- Python version
- command used
- redacted error output
- table schemas if relevant, with private values removed

Do not include real databases or chat contents. If a minimal reproduction needs data, create synthetic SQLite fixtures instead.

## Local Runtime Risks

Key extraction may require disabling SIP and attaching a debugger to the WeChat process. This weakens local system protections while it is disabled. Re-enable SIP after extraction if you choose to use that workflow.

Decrypted databases are plaintext SQLite files. Store them on encrypted disks, restrict file permissions, and delete them when no longer needed.

