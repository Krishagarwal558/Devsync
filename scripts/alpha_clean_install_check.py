"""Private alpha clean-install check runner."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def health_check(server_url: str) -> bool:
    """Return whether backend health endpoint is reachable."""
    try:
        with urllib.request.urlopen(f"{server_url.rstrip('/')}/health", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload.get("status") == "ok"
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False


def main() -> int:
    """Run clean-install checks that do not mutate cloud data."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-url", default="http://127.0.0.1:8000")
    parser.add_argument("--skip-health", action="store_true")
    args = parser.parse_args()

    checks = []
    if not args.skip_health:
        checks.append(("backend health", health_check(args.server_url)))
    checks.append(("desktop package import", _can_import("desktop")))
    checks.append(("server package import", _can_import("server")))
    checks.append(("alpha smoke script exists", Path("scripts/two_folder_reliability_smoke.py").exists()))

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'} {name}")
    return 1 if failed else 0


def _can_import(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    sys.exit(main())
