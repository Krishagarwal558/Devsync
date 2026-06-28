"""Common local paths used by the desktop app."""

from __future__ import annotations

from pathlib import Path


def default_demo_source() -> Path:
    """Return the current user's Desktop test folder."""
    return Path.home() / "OneDrive" / "Desktop" / "test"


def default_demo_target() -> Path:
    """Return the current user's Desktop test-b folder."""
    return Path.home() / "OneDrive" / "Desktop" / "test-b"

