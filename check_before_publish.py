#!/usr/bin/env python3
"""
发布前安全检查 / Pre-publish safety check

用法:
  python3 check_before_publish.py           # 扫描并打印报告
  python3 check_before_publish.py --install # 安装为 git pre-commit hook
"""

import glob
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

SENSITIVE_PATTERNS = [
    "wechat_keys.json",
    "wechat_keys*.json",
    "*.key",
    "*.pem",
]

REQUIRED_GITIGNORE_ENTRIES = [
    "wechat_keys.json",
    "decrypted/",
    "exported/",
]


def check_key_files():
    for pattern in SENSITIVE_PATTERNS:
        matches = glob.glob(os.path.join(ROOT, pattern))
        if matches:
            names = ", ".join(os.path.basename(m) for m in matches)
            return False, f"密钥文件存在: {names}"
    return True, "密钥文件未找到"


def check_decrypted():
    d = os.path.join(ROOT, "decrypted")
    if not os.path.isdir(d):
        return True, "decrypted/ 目录不存在"
    dbs = glob.glob(os.path.join(d, "*.db"))
    if dbs:
        return False, f"decrypted/ 目录下有 {len(dbs)} 个数据库文件"
    return True, "decrypted/ 目录为空"


def check_exported():
    e = os.path.join(ROOT, "exported")
    if not os.path.isdir(e):
        return True, "exported/ 目录不存在"
    files = [f for f in os.listdir(e) if not f.startswith(".")]
    if files:
        return False, f"exported/ 目录下有 {len(files)} 个文件 — 请确认不含真实数据"
    return True, "exported/ 目录为空"


def check_staged():
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        staged = result.stdout.strip().splitlines()
    except FileNotFoundError:
        return True, "git 未安装，跳过暂存区检查"

    bad = []
    for f in staged:
        base = os.path.basename(f)
        if base.startswith("wechat_keys") or base.endswith((".key", ".pem")):
            bad.append(f)
        if f.startswith("decrypted/") and f.endswith(".db"):
            bad.append(f)
        if f.startswith("exported/"):
            bad.append(f)

    if bad:
        return False, "暂存区含敏感文件: " + ", ".join(bad)
    return True, "暂存区无敏感文件"


def check_gitignore():
    gi_path = os.path.join(ROOT, ".gitignore")
    if not os.path.isfile(gi_path):
        return False, ".gitignore 不存在"
    content = open(gi_path).read()
    missing = [e for e in REQUIRED_GITIGNORE_ENTRIES if e not in content]
    if missing:
        return False, ".gitignore 缺少条目: " + ", ".join(missing)
    return True, ".gitignore 覆盖完整"


def run_checks():
    checks = [
        ("密钥文件", check_key_files),
        ("解密数据库", check_decrypted),
        ("导出文件", check_exported),
        ("暂存区", check_staged),
        (".gitignore", check_gitignore),
    ]

    failures = 0
    for label, fn in checks:
        ok, msg = fn()
        icon = "✓" if ok else "✗"
        print(f"{icon} {msg}")
        if not ok:
            failures += 1

    print()
    if failures == 0:
        print("全部通过，可以安全提交。")
    else:
        print(f"{failures} 项警告，提交前请确认。")

    return failures


def install_hook():
    hooks_dir = os.path.join(ROOT, ".git", "hooks")
    if not os.path.isdir(hooks_dir):
        print("错误：找不到 .git/hooks 目录，请在项目根目录下运行。")
        sys.exit(1)

    dest = os.path.join(hooks_dir, "pre-commit")
    src = os.path.abspath(__file__)
    shutil.copy2(src, dest)
    os.chmod(dest, 0o755)
    print(f"已安装 pre-commit hook: {dest}")
    print("之后每次 git commit 都会自动运行安全检查。")


if __name__ == "__main__":
    if "--install" in sys.argv:
        install_hook()
    else:
        failures = run_checks()
        sys.exit(1 if failures else 0)
