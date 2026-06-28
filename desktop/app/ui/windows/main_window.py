"""Phase 8 desktop sync client MVP window."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from desktop.app.core.auth_client import AuthClient, AuthorizedClient
from desktop.app.core.device_client import DeviceClient
from desktop.app.core.file_client import FileClient
from desktop.app.core.ignore_rules import IgnoreRules
from desktop.app.core.local_state import LocalStateStore
from desktop.app.core.watcher import LocalFolderWatcher
from desktop.app.models.settings import ClientSettings
from desktop.app.services.device_service import DesktopDeviceService
from desktop.app.services.sync_service import DesktopSyncService
from desktop.app.services.workspace_service import DesktopWorkspaceService


class MainWindow(QMainWindow):
    """Simple but usable desktop sync MVP."""

    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self._project_root = project_root
        self._settings = ClientSettings()
        self._settings.user_data_dir.mkdir(parents=True, exist_ok=True)
        self._settings.logs_dir.mkdir(parents=True, exist_ok=True)
        self._state = LocalStateStore(self._settings.state_path)
        self._authorized: AuthorizedClient | None = None
        self._sync_service: DesktopSyncService | None = None
        self._watcher: LocalFolderWatcher | None = None
        self._realtime_thread: threading.Thread | None = None
        self._workspaces: list[dict[str, object]] = []
        self._uploads = 0
        self._downloads = 0
        self._pending = 0

        self.setWindowTitle("DevSync Cloud Desktop")
        self.setMinimumSize(920, 620)
        self._stack = QStackedWidget()
        self._login_screen = self._build_login_screen()
        self._workspace_screen = self._build_workspace_screen()
        self._dashboard_screen = self._build_dashboard_screen()
        self._stack.addWidget(self._login_screen)
        self._stack.addWidget(self._workspace_screen)
        self._stack.addWidget(self._dashboard_screen)
        self.setCentralWidget(self._stack)
        self._load_saved_settings()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._watcher is not None:
            self._watcher.stop()
        if self._sync_service is not None:
            try:
                asyncio.run(self._sync_service.stop_realtime())
            except Exception:
                pass
        super().closeEvent(event)

    def _build_login_screen(self) -> QWidget:
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("Login to DevSync Cloud")
        title.setObjectName("PageTitle")
        checklist = QLabel("First run: start backend -> create account/workspace -> login -> choose workspace -> choose folder -> start sync")
        checklist.setWordWrap(True)
        form = QFormLayout()
        self._server_url = QLineEdit("http://127.0.0.1:8000")
        self._email = QLineEdit()
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Server URL", self._server_url)
        form.addRow("Email", self._email)
        form.addRow("Password", self._password)
        login = QPushButton("Login")
        login.setObjectName("PrimaryButton")
        login.clicked.connect(self._login)
        layout.addWidget(title)
        layout.addWidget(checklist)
        layout.addLayout(form)
        layout.addWidget(login)
        return screen

    def _build_workspace_screen(self) -> QWidget:
        screen = QWidget()
        layout = QVBoxLayout(screen)
        title = QLabel("Connect a Workspace")
        title.setObjectName("PageTitle")
        self._workspace_combo = QComboBox()
        self._folder_path = QLineEdit()
        choose = QPushButton("Select Local Folder")
        choose.clicked.connect(self._choose_folder)
        connect = QPushButton("Connect Workspace")
        connect.setObjectName("PrimaryButton")
        connect.clicked.connect(self._connect_workspace)
        row = QHBoxLayout()
        row.addWidget(self._folder_path, 1)
        row.addWidget(choose)
        layout.addWidget(title)
        layout.addWidget(QLabel("Workspace"))
        layout.addWidget(self._workspace_combo)
        layout.addWidget(QLabel("Local folder"))
        layout.addLayout(row)
        layout.addWidget(connect)
        layout.addStretch(1)
        return screen

    def _build_dashboard_screen(self) -> QWidget:
        screen = QWidget()
        layout = QVBoxLayout(screen)
        self._workspace_name = QLabel("Workspace")
        self._workspace_name.setObjectName("PageTitle")
        self._status = QLabel("Connection status: paused")
        self._folder_label = QLabel("Local folder: not selected")
        self._device_label = QLabel("Device: not selected")
        self._last_sync = QLabel("Last sync: never")
        self._stats = QLabel("Uploaded 0 | Downloaded 0 | Pending 0")
        self._conflicts = QLabel("Conflicts: none")
        self._conflicts.setObjectName("Muted")
        self._activity = QListWidget()
        buttons = QHBoxLayout()
        start = QPushButton("Start sync")
        start.clicked.connect(self._start_sync)
        pause = QPushButton("Pause sync")
        pause.clicked.connect(self._pause_sync)
        sync_now = QPushButton("Sync now")
        sync_now.clicked.connect(self._sync_now)
        retry = QPushButton("Retry queued")
        retry.clicked.connect(self._retry_queued)
        open_folder = QPushButton("Open folder")
        open_folder.clicked.connect(self._open_folder)
        export_logs = QPushButton("Export logs")
        export_logs.clicked.connect(self._export_logs)
        settings = QPushButton("Settings")
        settings.clicked.connect(self._show_settings)
        for button in (start, pause, sync_now, retry, open_folder, export_logs, settings):
            buttons.addWidget(button)
        layout.addWidget(self._workspace_name)
        layout.addWidget(self._status)
        layout.addWidget(self._folder_label)
        layout.addWidget(self._device_label)
        layout.addWidget(self._last_sync)
        layout.addWidget(self._stats)
        layout.addWidget(self._conflicts)
        layout.addLayout(buttons)
        layout.addWidget(QLabel("Recent activity"))
        layout.addWidget(self._activity, 1)
        return screen

    def _load_saved_settings(self) -> None:
        server_url = self._state.get_setting("server_url")
        if server_url:
            self._server_url.setText(server_url)

    def _login(self) -> None:
        try:
            payload = asyncio.run(AuthClient(self._server_url.text()).login(self._email.text(), self._password.text()))
            self._state.save_setting("server_url", self._server_url.text())
            self._state.save_setting("access_token", str(payload["access_token"]))
            self._state.save_setting("refresh_token", str(payload["refresh_token"]))
            self._state.save_json_setting("user_profile", dict(payload["user"]))  # type: ignore[arg-type]
            self._authorized = AuthorizedClient(self._server_url.text(), str(payload["access_token"]))
            asyncio.run(self._load_workspaces_and_device())
            self._stack.setCurrentWidget(self._workspace_screen)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Login failed", str(exc))

    async def _load_workspaces_and_device(self) -> None:
        if self._authorized is None:
            return
        from desktop.app.core.workspace_client import WorkspaceClient

        self._workspaces = await WorkspaceClient(self._authorized).list_workspaces()
        self._workspace_combo.clear()
        for workspace in self._workspaces:
            self._workspace_combo.addItem(str(workspace["name"]), userData=workspace)
        device = await DesktopDeviceService(self._state, DeviceClient(self._authorized)).ensure_device()
        self._device_label.setText(f"Device: {device['name']}")

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select local sync folder")
        if folder:
            self._folder_path.setText(folder)

    def _connect_workspace(self) -> None:
        workspace = self._workspace_combo.currentData()
        folder = self._folder_path.text().strip()
        if not workspace or not folder:
            QMessageBox.warning(self, "Missing setup", "Select a workspace and local folder.")
            return
        DesktopWorkspaceService(self._state).bind_workspace(str(workspace["id"]), str(workspace["name"]), Path(folder))
        self._workspace_name.setText(str(workspace["name"]))
        self._folder_label.setText(f"Local folder: {folder}")
        self._build_sync_service()
        self._refresh_activity()
        self._stack.setCurrentWidget(self._dashboard_screen)

    def _build_sync_service(self) -> None:
        access_token = self._state.get_setting("access_token")
        server_url = self._state.get_setting("server_url")
        if not access_token or not server_url:
            raise RuntimeError("Login first")
        authorized = AuthorizedClient(server_url, access_token)
        self._sync_service = DesktopSyncService(
            self._state,
            FileClient(authorized),
            server_url,
            access_token,
            IgnoreRules(),
        )

    def _start_sync(self) -> None:
        if self._sync_service is None:
            self._build_sync_service()
        local_folder = self._state.get_setting("local_folder_path")
        if not local_folder or self._sync_service is None:
            return
        root = Path(local_folder)
        self._watcher = LocalFolderWatcher(root, IgnoreRules(), 1.0, self._watcher_changed)
        self._watcher.start()
        if self._realtime_thread is None or not self._realtime_thread.is_alive():
            self._realtime_thread = threading.Thread(target=self._run_realtime_loop, daemon=True)
            self._realtime_thread.start()
        self._status.setText("Connection status: watching local folder and realtime cloud")
        self._add_activity("Started local watcher and realtime connection.")

    def _pause_sync(self) -> None:
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None
        if self._sync_service is not None:
            try:
                asyncio.run(self._sync_service.stop_realtime())
            except Exception:
                pass
        self._status.setText("Connection status: paused")
        self._add_activity("Paused sync.")

    def _run_realtime_loop(self) -> None:
        if self._sync_service is None:
            return
        try:
            asyncio.run(self._sync_service.start_realtime())
        except Exception as exc:  # noqa: BLE001
            QTimer.singleShot(0, lambda: self._add_activity(f"Realtime disconnected: {exc}"))

    def _watcher_changed(self, path: Path) -> None:
        self._pending += 1
        QTimer.singleShot(0, lambda: self._sync_path_change(path))

    def _sync_path_change(self, path: Path) -> None:
        if path.exists():
            self._upload_path(path)
            return
        if self._sync_service is None:
            return
        try:
            asyncio.run(self._sync_service.handle_local_deleted_file(path))
            self._add_activity(f"Deleted {path.name}.")
        except Exception as exc:  # noqa: BLE001
            self._add_activity(f"Delete sync failed for {path.name}: {exc}")
        finally:
            self._pending = max(self._pending - 1, 0)
            self._refresh_stats()

    def _upload_path(self, path: Path) -> None:
        if self._sync_service is None:
            return
        try:
            response = asyncio.run(self._sync_service.upload_changed_file(path))
            if response:
                self._uploads += 1
                self._add_activity(f"Uploaded {path.name}.")
        except Exception as exc:  # noqa: BLE001
            self._add_activity(f"Upload failed for {path.name}: {exc}")
        finally:
            self._pending = max(self._pending - 1, 0)
            self._refresh_stats()

    def _sync_now(self) -> None:
        local_folder = self._state.get_setting("local_folder_path")
        if not local_folder or self._sync_service is None:
            return
        for path in Path(local_folder).rglob("*"):
            if path.is_file():
                self._upload_path(path)
        self._last_sync.setText("Last sync: just now")

    def _retry_queued(self) -> None:
        if self._sync_service is None:
            return
        try:
            uploads, downloads = asyncio.run(self._sync_service.retry_pending())
            self._add_activity(f"Retried queued work: {uploads} uploads, {downloads} downloads.")
        except Exception as exc:  # noqa: BLE001
            self._add_activity(f"Retry failed: {exc}")

    def _open_folder(self) -> None:
        folder = self._state.get_setting("local_folder_path")
        if folder:
            import os

            os.startfile(folder)  # type: ignore[attr-defined]

    def _export_logs(self) -> None:
        target, _ = QFileDialog.getSaveFileName(self, "Export DevSync debug logs", "devsync-debug-log.txt", "Text files (*.txt)")
        if not target:
            return
        lines = [
            "DevSync Desktop Debug Log",
            f"Server: {self._state.get_setting('server_url')}",
            f"Workspace: {self._state.get_setting('workspace_id')}",
            f"Device: {self._state.get_setting('device_id')}",
            f"Local folder: {self._state.get_setting('local_folder_path')}",
            "",
            "Recent activity:",
            *self._state.recent_activity(100),
        ]
        Path(target).write_text("\n".join(lines), encoding="utf-8")
        default_log = self._settings.logs_dir / "last-debug-export.txt"
        default_log.write_text("\n".join(lines), encoding="utf-8")
        self._add_activity(f"Exported debug log to {target}.")

    def _show_settings(self) -> None:
        choice = QMessageBox.question(
            self,
            "Settings",
            f"Local state: {self._settings.state_path}\nLogs: {self._settings.logs_dir}\n\nReset local config?",
        )
        if choice == QMessageBox.StandardButton.Yes:
            self._pause_sync()
            self._state.reset()
            self._activity.clear()
            self._server_url.setText(ClientSettings().server_url)
            self._stack.setCurrentWidget(self._login_screen)

    def _add_activity(self, message: str) -> None:
        self._state.add_activity(message)
        self._activity.insertItem(0, message)
        if "Conflict detected" in message:
            self._conflicts.setText(f"Conflict warning: {message}")
        self._refresh_stats()

    def _refresh_activity(self) -> None:
        self._activity.clear()
        for message in self._state.recent_activity():
            self._activity.addItem(message)
        self._refresh_stats()

    def _refresh_stats(self) -> None:
        self._stats.setText(f"Uploaded {self._uploads} | Downloaded {self._downloads} | Pending {self._pending}")
