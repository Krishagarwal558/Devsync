"""Watchdog-based local file watcher."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from threading import Lock, Timer

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from desktop.app.core.ignore_rules import IgnoreRules

ChangeCallback = Callable[[Path], None]


class DebouncedFileEventHandler(FileSystemEventHandler):
    """Debounces file events before invoking callback."""

    def __init__(self, root: Path, ignore_rules: IgnoreRules, debounce_seconds: float, callback: ChangeCallback) -> None:
        self._root = root
        self._ignore_rules = ignore_rules
        self._debounce_seconds = debounce_seconds
        self._callback = callback
        self._timers: dict[Path, Timer] = {}
        self._lock = Lock()

    def on_created(self, event: FileSystemEvent) -> None:
        self._schedule(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._schedule(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule_path(Path(event.dest_path))

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._callback(Path(event.src_path))

    def _schedule(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._schedule_path(Path(event.src_path))

    def _schedule_path(self, path: Path) -> None:
        if self._ignore_rules.is_ignored_local_path(self._root, path):
            return
        with self._lock:
            existing = self._timers.pop(path, None)
            if existing is not None:
                existing.cancel()
            timer = Timer(self._debounce_seconds, self._fire, args=(path,))
            self._timers[path] = timer
            timer.start()

    def _fire(self, path: Path) -> None:
        with self._lock:
            self._timers.pop(path, None)
        if path.exists():
            self._callback(path)


class LocalFolderWatcher:
    """Watches a local folder for file changes."""

    def __init__(self, root: Path, ignore_rules: IgnoreRules, debounce_seconds: float, callback: ChangeCallback) -> None:
        self._root = root
        self._handler = DebouncedFileEventHandler(root, ignore_rules, debounce_seconds, callback)
        self._observer = Observer()
        self._started_at: float | None = None

    def start(self) -> None:
        """Start watching."""
        self._root.mkdir(parents=True, exist_ok=True)
        self._observer.schedule(self._handler, str(self._root), recursive=True)
        self._observer.start()
        self._started_at = time.time()

    def stop(self) -> None:
        """Stop watching."""
        self._observer.stop()
        self._observer.join(timeout=5)
