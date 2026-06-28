from __future__ import annotations

from desktop.app.core.ignore_rules import IgnoreRules


def test_default_ignore_rules() -> None:
    rules = IgnoreRules()

    assert rules.is_ignored_remote_path(".git/config")
    assert rules.is_ignored_remote_path("node_modules/pkg/index.js")
    assert rules.is_ignored_remote_path("logs/app.log")
    assert not rules.is_ignored_remote_path("src/app.py")

