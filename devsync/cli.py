from __future__ import annotations

import argparse
from pathlib import Path

from .scanner import scan_workspace, workspace_status
from .snapshots import create_snapshot, list_snapshots, restore_snapshot
from .syncer import sync_workspace
from .watcher import watch_sync_workspace, watch_workspace
from .workspace import ensure_workspace, find_workspace, init_workspace


def _print_scan(summary) -> None:
    print(
        f"added={summary.added} modified={summary.modified} deleted={summary.deleted} "
        f"unchanged={summary.unchanged} files={summary.files_seen} bytes_indexed={summary.bytes_indexed}"
    )


def cmd_init(args) -> int:
    workspace = init_workspace(args.path, args.name)
    print(f"Initialized DevSync workspace: {workspace.root}")
    print(f"Metadata: {workspace.meta_dir}")
    return 0


def cmd_scan(args) -> int:
    workspace = ensure_workspace(args.path)
    summary = scan_workspace(workspace)
    _print_scan(summary)
    return 0


def cmd_status(args) -> int:
    workspace = ensure_workspace(args.path)
    if args.rescan:
        _print_scan(scan_workspace(workspace))
    status = workspace_status(workspace)
    print(f"workspace={status['name'] or status['workspace_id']}")
    print(f"root={workspace.root}")
    print(f"active_files={status['active_files']}")
    print(f"deleted_files={status['deleted_files']}")
    print(f"chunks={status['chunks']}")
    print(f"snapshots={status['snapshots']}")
    print(f"tracked_bytes={status['tracked_bytes']}")
    return 0


def cmd_snapshot(args) -> int:
    workspace = ensure_workspace(args.path)
    snapshot = create_snapshot(workspace, args.name)
    print(f"snapshot={snapshot.id} name={snapshot.name} files={snapshot.file_count}")
    return 0


def cmd_history(args) -> int:
    workspace = ensure_workspace(args.path)
    snapshots = list_snapshots(workspace)
    if not snapshots:
        print("No snapshots yet.")
        return 0
    for snapshot in snapshots:
        print(f"{snapshot.id}  {snapshot.created_at}  files={snapshot.file_count}  {snapshot.name}")
    return 0


def cmd_restore(args) -> int:
    workspace = ensure_workspace(args.path)
    if not args.yes:
        raise SystemExit("Restore writes files. Re-run with --yes to confirm.")
    count = restore_snapshot(workspace, args.snapshot_id, delete_extra=args.delete_extra)
    print(f"Restored {count} files from snapshot {args.snapshot_id}")
    return 0


def cmd_sync(args) -> int:
    source = find_workspace(args.source)
    summary = sync_workspace(
        source,
        Path(args.target),
        delete=args.delete,
        force=args.force,
        dry_run=args.dry_run,
    )
    mode = "dry-run " if summary.dry_run else ""
    print(
        f"{mode}copied={summary.copied} skipped={summary.skipped} "
        f"conflicts={summary.conflicts} deleted={summary.deleted}"
    )
    if summary.conflicts and not args.force:
        print("Conflict note: target edits were saved as *.devsync-conflict-* files before applying source.")
    return 0


def cmd_watch(args) -> int:
    workspace = ensure_workspace(args.path)
    watch_workspace(workspace, interval=args.interval)
    return 0


def cmd_watch_sync(args) -> int:
    source = find_workspace(args.source)
    watch_sync_workspace(
        source,
        Path(args.target),
        interval=args.interval,
        delete=args.delete,
        force=args.force,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="devsync", description="DevSync Python MVP")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Initialize a workspace")
    init.add_argument("path", nargs="?", default=".")
    init.add_argument("--name")
    init.set_defaults(func=cmd_init)

    scan = sub.add_parser("scan", help="Index workspace files into the local chunk store")
    scan.add_argument("path", nargs="?", default=".")
    scan.set_defaults(func=cmd_scan)

    status = sub.add_parser("status", help="Show workspace metadata")
    status.add_argument("path", nargs="?", default=".")
    status.add_argument("--rescan", action="store_true", help="Scan before printing status")
    status.set_defaults(func=cmd_status)

    snapshot = sub.add_parser("snapshot", help="Create a restorable snapshot")
    snapshot.add_argument("path", nargs="?", default=".")
    snapshot.add_argument("--name", default="manual")
    snapshot.set_defaults(func=cmd_snapshot)

    history = sub.add_parser("history", help="List snapshots")
    history.add_argument("path", nargs="?", default=".")
    history.set_defaults(func=cmd_history)

    restore = sub.add_parser("restore", help="Restore a snapshot")
    restore.add_argument("snapshot_id")
    restore.add_argument("path", nargs="?", default=".")
    restore.add_argument("--yes", action="store_true", help="Confirm file writes")
    restore.add_argument("--delete-extra", action="store_true", help="Delete tracked files not in the snapshot")
    restore.set_defaults(func=cmd_restore)

    sync = sub.add_parser("sync", help="Sync one local workspace folder into another")
    sync.add_argument("source")
    sync.add_argument("target")
    sync.add_argument("--delete", action="store_true", help="Delete target tracked files missing from source")
    sync.add_argument("--force", action="store_true", help="Overwrite target changes instead of keeping conflicts")
    sync.add_argument("--dry-run", action="store_true")
    sync.set_defaults(func=cmd_sync)

    watch = sub.add_parser("watch", help="Poll for changes and keep the local index updated")
    watch.add_argument("path", nargs="?", default=".")
    watch.add_argument("--interval", type=float, default=2.0)
    watch.set_defaults(func=cmd_watch)

    watch_sync = sub.add_parser("watch-sync", help="Continuously sync one workspace folder into another")
    watch_sync.add_argument("source")
    watch_sync.add_argument("target")
    watch_sync.add_argument("--interval", type=float, default=2.0)
    watch_sync.add_argument("--delete", action="store_true", help="Delete target tracked files missing from source")
    watch_sync.add_argument("--force", action="store_true", help="Overwrite target changes instead of keeping conflicts")
    watch_sync.set_defaults(func=cmd_watch_sync)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
