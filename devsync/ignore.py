from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PATTERNS = [
    ".devsync/",
    ".git/",
    "node_modules/",
    "__pycache__/",
    ".venv/",
    "venv/",
    "dist/",
    "build/",
    "target/",
    ".next/",
    ".turbo/",
    "*.pyc",
    "*.log",
]


@dataclass(frozen=True)
class IgnoreRule:
    pattern: str
    negated: bool = False


class IgnoreMatcher:
    def __init__(self, rules: list[IgnoreRule]):
        self.rules = rules

    @classmethod
    def from_workspace(cls, root: Path) -> "IgnoreMatcher":
        rules = [IgnoreRule(pattern) for pattern in DEFAULT_PATTERNS]
        syncignore = root / ".syncignore"
        if syncignore.exists():
            for raw_line in syncignore.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                negated = line.startswith("!")
                pattern = line[1:].strip() if negated else line
                if pattern:
                    rules.append(IgnoreRule(pattern.replace("\\", "/"), negated))
        return cls(rules)

    def ignored(self, rel_path: str, is_dir: bool = False) -> bool:
        rel = rel_path.replace("\\", "/").strip("/")
        name = rel.rsplit("/", 1)[-1] if rel else rel
        ignored = False

        for rule in self.rules:
            pattern = rule.pattern.strip()
            directory_only = pattern.endswith("/")
            normalized = pattern.strip("/")
            if directory_only and not is_dir:
                continue

            matched = False
            if "/" in normalized:
                matched = fnmatch.fnmatch(rel, normalized) or fnmatch.fnmatch(rel, f"{normalized}/*")
            else:
                matched = fnmatch.fnmatch(name, normalized) or fnmatch.fnmatch(rel, normalized)
                if is_dir:
                    matched = matched or any(part == normalized for part in rel.split("/"))

            if matched:
                ignored = not rule.negated

        return ignored

