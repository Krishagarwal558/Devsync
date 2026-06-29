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
    QFrame,
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
        self.setMinimumSize(1040, 680)
        self.resize(1120, 720)
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

        card = self._card("AuthCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(34, 32, 34, 32)
        card_layout.setSpacing(16)

        badge = QLabel("PUBLIC BETA")
        badge.setObjectName("Badge")
        title = QLabel("DevSync Cloud")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Keep project folders moving between trusted devices.")
        subtitle.setObjectName("HeroSubtitle")
        subtitle.setWordWrap(True)
        checklist = QLabel("Connect your backend, sign in, choose a workspace, and attach a local folder.")
        checklist.setObjectName("Muted")
        checklist.setWordWrap(True)

        form = QFormLayout()
        form.setSpacing(12)
        self._server_url = QLineEdit("http://127.0.0.1:8000")
        self._server_url.setPlaceholderText("https://your-devsync-backend.example.com")
        self._email = QLineEdit()
        self._email.setPlaceholderText("you@example.com")
        self._password = QLineEdit()
        self._password.setPlaceholderText("Password")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Server URL", self._server_url)
        form.addRow("Email", self._email)
        form.addRow("Password", self._password)

        login = QPushButton("Login")
        login.setObjectName("PrimaryButton")
        login.clicked.connect(self._login)

        card_layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignLeft)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addWidget(checklist)
        card_layout.addSpacing(6)
        card_layout.addLayout(form)
        card_layout.addSpacing(8)
        card_layout.addWidget(login)
        layout.addWidget(card)
        return screen

    def _build_workspace_screen(self) -> QWidget:
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setContentsMargins(42, 36, 42, 36)
        layout.setSpacing(18)

        header = self._hero_header(
            "Connect a workspace",
            "Pick the cloud workspace and the local folder this device should keep in sync.",
            "STEP 2"
        )
        self._workspace_combo = QComboBox()
        self._folder_path = QLineEdit()
        self._folder_path.setPlaceholderText("Choose the local project folder")
        choose = QPushButton("Select Local Folder")
        choose.clicked.connect(self._choose_folder)
        connect = QPushButton("Connect Workspace")
        connect.setObjectName("PrimaryButton")
        connect.clicked.connect(self._connect_workspace)

        setup_card = self._card()
        setup_layout = QVBoxLayout(setup_card)
        setup_layout.setContentsMargins(24, 22, 24, 24)
        setup_layout.setSpacing(12)

        row = QHBoxLayout()
        row.addWidget(self._folder_path, 1)
        row.addWidget(choose)
        setup_layout.addWidget(self._section_label("Workspace"))
        setup_layout.addWidget(self._workspace_combo)
        setup_layout.addWidget(self._section_label("Local folder"))
        setup_layout.addLayout(row)
        setup_layout.addSpacing(8)
        setup_layout.addWidget(connect, 0, Qt.AlignmentFlag.AlignRight)

        layout.addWidget(header)
        layout.addWidget(setup_card)
        layout.addStretch(1)
        return screen

    def _build_dashboard_screen(self) -> QWidget:
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setContentsMargins(34, 30, 34, 28)
        layout.setSpacing(16)

        top = QHBoxLayout()
        title_box = QVBoxLayout()
        self._workspace_name = QLabel("Workspace")
        self._workspace_name.setObjectName("PageTitle")
        self._status = QLabel("Paused")
        self._status.setObjectName("StatusPill")
        title_box.addWidget(self._workspace_name)
        title_box.addWidget(QLabel("Realtime folder sync for this device."))
        top.addLayout(title_box, 1)
        top.addWidget(self._status, 0, Qt.AlignmentFlag.AlignTop)

        self._folder_label = QLabel("Local folder: not selected")
        self._folder_label.setObjectName("Muted")
        self._device_label = QLabel("Device: not selected")
        self._device_label.setObjectName("Muted")
        self._last_sync = QLabel("Last sync: never")
        self._last_sync.setObjectName("Muted")
        self._conflicts = QLabel("Conflicts: none")
        self._conflicts.setObjectName("Muted")
        self._activity = QListWidget()
        self._activity.setObjectName("ActivityList")

        info = self._card()
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(22, 20, 22, 20)
        info_layout.setSpacing(8)
        info_layout.addWidget(self._folder_label)
        info_layout.addWidget(self._device_label)
        info_layout.addWidget(self._last_sync)
        info_layout.addWidget(self._conflicts)

        stats_row = QHBoxLayout()
        self._uploads_value = self._metric_card("Uploaded", "0")
        self._downloads_value = self._metric_card("Downloaded", "0")
        self._pending_value = self._metric_card("Pending", "0")
        stats_row.addWidget(self._uploads_value)
        stats_row.addWidget(self._downloads_value)
        stats_row.addWidget(self._pending_value)

        buttons = QHBoxLayout()
        start = QPushButton("Start sync")
        start.setObjectName("PrimaryButton")
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
        buttons.addStretch(1)

        activity_header = QHBoxLayout()
        activity_title = self._section_label("Recent activity")
        activity_hint = QLabel("Uploads, reconnects, retries, and conflicts")
        activity_hint.setObjectName("Muted")
        activity_header.addWidget(activity_title)
        activity_header.addWidget(activity_hint, 1, Qt.AlignmentFlag.AlignRight)

        layout.addLayout(top)
        layout.addWidget(info)
        layout.addLayout(stats_row)
        layout.addLayout(buttons)
        layout.addLayout(activity_header)
        layout.addWidget(self._activity, 1)
        return screen

    def _card(self, object_name: str = "Card") -> QFrame:
        frame = QFrame()
        frame.setObjectName(object_name)
        return frame

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SectionTitle")
        return label

    def _hero_header(self, title: str, subtitle: str, badge_text: str) -> QFrame:
        header = self._card("HeroCard")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(8)
        badge = QLabel(badge_text)
        badge.setObjectName("Badge")
        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("HeroSubtitle")
        subtitle_label.setWordWrap(True)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        return header

    def _metric_card(self, title: str, value: str) -> QFrame:
        card = self._card("MetricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("Muted")
        value_label = QLabel(value)
        value_label.setObjectName("MetricValue")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        card._value_label = value_label  # type: ignore[attr-defined]
        return card

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
        self._status.setText("Live")
        self._status.setProperty("state", "live")
        self._status.style().unpolish(self._status)
        self._status.style().polish(self._status)
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
        self._status.setText("Paused")
        self._status.setProperty("state", "paused")
        self._status.style().unpolish(self._status)
        self._status.style().polish(self._status)
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
        self._uploads_value._value_label.setText(str(self._uploads))  # type: ignore[attr-defined]
        self._downloads_value._value_label.setText(str(self._downloads))  # type: ignore[attr-defined]
        self._pending_value._value_label.setText(str(self._pending))  # type: ignore[attr-defined]
