"""Workspace slug helpers."""

from __future__ import annotations

import re


def slugify(value: str) -> str:
    """Convert a workspace name into a stable URL-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower().strip())
    slug = slug.strip("-")
    return slug or "workspace"

