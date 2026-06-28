from __future__ import annotations

import time
from pathlib import Path

from .scanner import scan_workspace
from .syncer import sync_workspace
from .workspace import Workspace


def watch_workspace(workspace: Workspace, interval: float = 2.0) -> None:
    print(f"Watching {workspace.root} every {interval:g}s. Press Ctrl+C to stop.")
    try:
        while True:
            summary = scan_workspace(workspace)
            if summary.changed:
                print(
                    "changes: "
                    f"+{summary.added} ~{summary.modified} -{summary.deleted} "
                    f"({summary.bytes_indexed} bytes indexed)"
                )
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped watching.")


def watch_sync_workspace(
    source: Workspace,
    target: Path,
    interval: float = 2.0,
    delete: bool = False,
    force: bool = False,
) -> None:
    """Continuously scan a source workspace and sync changes into a target folder."""
    print(f"Watching {source.root} and syncing to {target} every {interval:g}s.")
    print("Press Ctrl+C to stop.")
    try:
        while True:
            scan_summary = scan_workspace(source)
            if scan_summary.changed:
                sync_summary = sync_workspace(source, target, delete=delete, force=force)
                print(
                    "synced: "
                    f"+{scan_summary.added} ~{scan_summary.modified} -{scan_summary.deleted}; "
                    f"copied={sync_summary.copied} skipped={sync_summary.skipped} "
                    f"conflicts={sync_summary.conflicts} deleted={sync_summary.deleted}"
                )
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped watch-sync.")
