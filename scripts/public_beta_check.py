"""Public beta release readiness checks."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    ".gitignore",
    "README.md",
    "LICENSE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "docs/PUBLIC_BETA_GUIDE.md",
    "docs/PUBLIC_BETA_CHECKLIST.md",
    "server/.env.beta.example",
    "server/.env.production.example",
]

REQUIRED_GITIGNORE_RULES = [
    "server/.env.*",
    "!server/.env.*.example",
    "work/",
    "*.sqlite",
    "*.db",
    "__pycache__/",
]

SECRET_PATTERNS = [
    re.compile(r"npg_[A-Za-z0-9]+"),
    re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
    re.compile(r"postgresql(?:\+asyncpg)?://[^:\s]+:[^@\s]+@[^/\s]+/[^\s]+"),
]

ALLOWED_DATABASE_PATTERNS = [
    re.compile(r"postgresql(?:\+asyncpg)?://devsync:devsync@(localhost|127\.0\.0\.1|postgres):5432/devsync(_test)?$"),
    re.compile(r"postgresql(?:\+asyncpg)?://USER:PASSWORD@HOST(:5432)?/(DB|DBNAME)(\?ssl=require)?$"),
]


def git_tracked_files() -> list[Path]:
    """Return files tracked by Git."""
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [ROOT / line for line in result.stdout.splitlines() if line.strip()]


def check_required_files(errors: list[str]) -> None:
    """Check public beta files exist."""
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).exists():
            errors.append(f"missing required file: {relative}")


def check_gitignore(errors: list[str]) -> None:
    """Check core ignore rules are present."""
    path = ROOT / ".gitignore"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    for rule in REQUIRED_GITIGNORE_RULES:
        if rule not in text:
            errors.append(f".gitignore missing rule: {rule}")


def check_tracked_secrets(errors: list[str]) -> None:
    """Scan tracked text files for high-risk secret patterns."""
    for path in git_tracked_files():
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".exe"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(0).strip("\"'`,)")
                if any(allowed.fullmatch(value) for allowed in ALLOWED_DATABASE_PATTERNS):
                    continue
                relative = path.relative_to(ROOT).as_posix()
                errors.append(f"possible tracked secret in {relative}")


def main() -> int:
    """Run public beta checks."""
    errors: list[str] = []
    check_required_files(errors)
    check_gitignore(errors)
    check_tracked_secrets(errors)

    if errors:
        print("DevSync public beta check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("DevSync public beta check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
