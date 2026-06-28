"""Main DevSync desktop window."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from desktop.app.services.paths import default_demo_source, default_demo_target
from desktop.app.viewmodels.dashboard import DashboardState, DashboardViewModel


class MainWindow(QMainWindow):
    """Modern desktop shell for DevSync."""

    def __init__(self, project_root: Path) -> None:
        """Create the main window."""
        super().__init__()
        self._project_root = project_root
        self._dashboard = DashboardViewModel()
        self._watch_process: QProcess | None = None

        self.setWindowTitle("DevSync")
        self.setMinimumSize(1060, 680)
        self.resize(1180, 760)

        self._stack = QStackedWidget()
        self._status_label = QLabel("Ready")
        self._workspace_title = QLabel("Home")
        self._workspace_title.setObjectName("PageTitle")
        self._workspace_subtitle = QLabel("Your files stay together, wherever you work.")
        self._workspace_subtitle.setObjectName("Muted")

        self._home_screen = self._build_home_screen()
        self._dashboard_screen = self._build_dashboard_screen()
        self._activity_screen = self._build_placeholder_screen(
            "Activity",
            "Recent file updates and device changes will appear here.",
        )
        self._devices_screen = self._build_placeholder_screen(
            "Devices",
            "Connected computers will appear here when cloud sync is added.",
        )
        self._settings_screen = self._build_placeholder_screen(
            "Settings",
            "Preferences for startup, notifications, and syncing will live here.",
        )

        self._stack.addWidget(self._home_screen)
        self._stack.addWidget(self._dashboard_screen)
        self._stack.addWidget(self._devices_screen)
        self._stack.addWidget(self._activity_screen)
        self._stack.addWidget(self._settings_screen)

        self.setCentralWidget(self._build_shell())
        self._load_default_workspace_if_available()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_current_workspace)
        self._refresh_timer.start(5000)

    def closeEvent(self, event) -> None:  # noqa: N802
        """Stop background watch-sync before closing."""
        if self._watch_process is not None and self._watch_process.state() != QProcess.NotRunning:
            self._watch_process.kill()
            self._watch_process.waitForFinished(1500)
        super().closeEvent(event)

    def _build_shell(self) -> QWidget:
        """Build the main app shell."""
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self._build_sidebar())

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self._build_topbar())
        content_layout.addWidget(self._stack, 1)
        body_layout.addWidget(content, 1)

        root_layout.addWidget(body, 1)
        root_layout.addWidget(self._build_statusbar())
        return root

    def _build_sidebar(self) -> QWidget:
        """Build sidebar navigation."""
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(230)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)

        title = QLabel("DevSync")
        title.setObjectName("AppTitle")
        subtitle = QLabel("Files together")
        subtitle.setObjectName("Muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(20)

        layout.addWidget(self._sidebar_button("Home", lambda: self._show_page(0, "Home")))
        layout.addWidget(self._sidebar_button("Workspaces", self._show_dashboard))
        layout.addWidget(self._sidebar_button("Devices", lambda: self._show_page(2, "Devices")))
        layout.addWidget(self._sidebar_button("Activity", lambda: self._show_page(3, "Activity")))
        layout.addWidget(self._sidebar_button("Settings", lambda: self._show_page(4, "Settings")))
        layout.addStretch(1)

        version = QLabel("Local preview")
        version.setObjectName("Muted")
        layout.addWidget(version)
        return sidebar

    def _sidebar_button(self, text: str, callback) -> QPushButton:
        """Create a sidebar button."""
        button = QPushButton(text)
        button.setObjectName("SidebarButton")
        button.clicked.connect(callback)
        return button

    def _build_topbar(self) -> QWidget:
        """Build the top bar."""
        topbar = QWidget()
        topbar.setObjectName("TopBar")
        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(16)

        text_box = QWidget()
        text_layout = QVBoxLayout(text_box)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        text_layout.addWidget(self._workspace_title)
        text_layout.addWidget(self._workspace_subtitle)

        sync_button = QPushButton("Sync Now")
        sync_button.clicked.connect(self._sync_now)
        pause_button = QPushButton("Start Auto Sync")
        pause_button.setObjectName("PrimaryButton")
        pause_button.clicked.connect(self._toggle_watch_sync)
        self._auto_sync_button = pause_button

        layout.addWidget(text_box, 1)
        layout.addWidget(sync_button)
        layout.addWidget(pause_button)
        return topbar

    def _build_statusbar(self) -> QWidget:
        """Build status bar."""
        bar = QWidget()
        bar.setObjectName("StatusBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.addWidget(self._status_label)
        layout.addStretch(1)
        layout.addWidget(QLabel("Network: local preview"))
        layout.addWidget(QLabel("Storage: healthy"))
        return bar

    def _build_home_screen(self) -> QWidget:
        """Build home screen."""
        screen = self._scroll_content()
        layout = screen._content_layout  # type: ignore[attr-defined]

        hero = self._card("HeroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(24, 24, 24, 24)
        hero_layout.setSpacing(14)

        title = QLabel("Start syncing a folder")
        title.setObjectName("PageTitle")
        body = QLabel("Choose a folder, name it, and DevSync will keep another folder updated.")
        body.setObjectName("Muted")
        body.setWordWrap(True)

        actions = QWidget()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        create = QPushButton("Create Workspace")
        create.setObjectName("PrimaryButton")
        create.clicked.connect(self._create_workspace)
        open_existing = QPushButton("Open Workspace")
        open_existing.clicked.connect(self._open_workspace)
        quick = QPushButton("Open Desktop Test")
        quick.clicked.connect(self._open_desktop_test)
        actions_layout.addWidget(create)
        actions_layout.addWidget(open_existing)
        actions_layout.addWidget(quick)
        actions_layout.addStretch(1)

        hero_layout.addWidget(title)
        hero_layout.addWidget(body)
        hero_layout.addWidget(actions)
        layout.addWidget(hero)

        layout.addWidget(self._section_label("Recent Workspaces"))
        layout.addWidget(
            self._info_card(
                "Desktop test",
                "C:\\Users\\shrey\\OneDrive\\Desktop\\test",
                "Use this to try Person A -> Person B local syncing.",
            )
        )
        layout.addStretch(1)
        return screen

    def _build_dashboard_screen(self) -> QWidget:
        """Build workspace dashboard screen."""
        screen = self._scroll_content()
        layout = screen._content_layout  # type: ignore[attr-defined]

        self._status_card = self._info_card(
            "No workspace open",
            "Choose a workspace from Home.",
            "Create or open a folder to see sync status.",
        )
        layout.addWidget(self._status_card)

        cards = QWidget()
        cards_layout = QHBoxLayout(cards)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(14)
        self._files_card = self._metric_card("Files", "0", "Tracked in this workspace")
        self._storage_card = self._metric_card("Storage", "0 KB", "Current tracked size")
        self._snapshots_card = self._metric_card("Snapshots", "0", "Restore points")
        cards_layout.addWidget(self._files_card)
        cards_layout.addWidget(self._storage_card)
        cards_layout.addWidget(self._snapshots_card)
        layout.addWidget(cards)

        target = self._card()
        target_layout = QVBoxLayout(target)
        target_layout.setContentsMargins(18, 18, 18, 18)
        target_layout.setSpacing(10)
        target_layout.addWidget(self._section_label("Local Device B folder"))
        self._target_input = QLineEdit(str(default_demo_target()))
        choose_target = QPushButton("Choose Folder")
        choose_target.clicked.connect(self._choose_target)
        target_row = QWidget()
        target_row_layout = QHBoxLayout(target_row)
        target_row_layout.setContentsMargins(0, 0, 0, 0)
        target_row_layout.addWidget(self._target_input, 1)
        target_row_layout.addWidget(choose_target)
        target_layout.addWidget(target_row)
        layout.addWidget(target)

        layout.addWidget(self._section_label("Recent Activity"))
        self._activity_label = QLabel("No activity yet.")
        self._activity_label.setObjectName("Muted")
        layout.addWidget(self._activity_label)
        layout.addStretch(1)
        return screen

    def _build_placeholder_screen(self, title: str, message: str) -> QWidget:
        """Build a friendly placeholder screen."""
        screen = self._scroll_content()
        layout = screen._content_layout  # type: ignore[attr-defined]
        layout.addWidget(self._info_card(title, message, "This screen will grow as cloud sync is added."))
        layout.addStretch(1)
        return screen

    def _scroll_content(self) -> QWidget:
        """Create a padded scroll area content widget."""
        outer = QScrollArea()
        outer.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        outer.setWidget(content)
        outer._content_layout = layout  # type: ignore[attr-defined]
        return outer

    def _card(self, object_name: str = "Card") -> QFrame:
        """Create a styled card."""
        frame = QFrame()
        frame.setObjectName(object_name)
        return frame

    def _section_label(self, text: str) -> QLabel:
        """Create a section label."""
        label = QLabel(text)
        label.setObjectName("SectionTitle")
        return label

    def _info_card(self, title: str, subtitle: str, detail: str) -> QFrame:
        """Create an information card."""
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setWordWrap(True)
        detail_label = QLabel(detail)
        detail_label.setObjectName("Muted")
        detail_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addWidget(detail_label)
        return card

    def _metric_card(self, title: str, value: str, detail: str) -> QFrame:
        """Create a dashboard metric card."""
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("Muted")
        value_label = QLabel(value)
        value_label.setObjectName("PageTitle")
        detail_label = QLabel(detail)
        detail_label.setObjectName("Muted")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(detail_label)
        card._value_label = value_label  # type: ignore[attr-defined]
        return card

    def _show_page(self, index: int, title: str) -> None:
        """Show a top-level page."""
        self._stack.setCurrentIndex(index)
        self._workspace_title.setText(title)
        self._workspace_subtitle.setText("Your files stay together, wherever you work.")

    def _show_dashboard(self) -> None:
        """Show the workspace dashboard."""
        self._stack.setCurrentIndex(1)
        state = self._dashboard.state
        if state.workspace_path:
            self._workspace_title.setText(state.workspace_path.name)
            self._workspace_subtitle.setText("Everything is up to date")
        else:
            self._workspace_title.setText("Workspaces")
            self._workspace_subtitle.setText("Open or create a workspace to begin.")

    def _create_workspace(self) -> None:
        """Create a workspace from a chosen folder."""
        folder = QFileDialog.getExistingDirectory(self, "Choose a folder to sync")
        if not folder:
            return
        default_name = Path(folder).name or "Workspace"
        name, accepted = QInputDialog.getText(self, "Name workspace", "Workspace name:", text=default_name)
        if not accepted or not name.strip():
            return
        try:
            state = self._dashboard.create_workspace(Path(folder), name.strip())
            self._set_default_target_if_empty()
            self._render_dashboard(state)
            self._show_dashboard()
            self._status_label.setText("Workspace created.")
        except Exception as exc:  # noqa: BLE001
            self._show_error("Could not create workspace", str(exc))

    def _open_workspace(self) -> None:
        """Open an existing workspace folder."""
        folder = QFileDialog.getExistingDirectory(self, "Open a DevSync workspace")
        if not folder:
            return
        self._open_workspace_path(Path(folder))

    def _open_desktop_test(self) -> None:
        """Open the user's Desktop test workspace."""
        source = default_demo_source()
        target = default_demo_target()
        if not source.exists():
            self._show_error("Folder not found", f"We could not find {source}.")
            return
        self._target_input.setText(str(target))
        self._open_workspace_path(source)

    def _open_workspace_path(self, path: Path) -> None:
        """Open a workspace by path."""
        try:
            state = self._dashboard.open_workspace(path)
            self._dashboard.set_target(Path(self._target_input.text()))
            self._render_dashboard(state)
            self._show_dashboard()
            self._status_label.setText("Workspace opened.")
        except Exception as exc:  # noqa: BLE001
            self._show_error("Could not open workspace", str(exc))

    def _choose_target(self) -> None:
        """Choose the local target folder."""
        folder = QFileDialog.getExistingDirectory(self, "Choose Device B folder")
        if folder:
            self._target_input.setText(folder)
            self._dashboard.set_target(Path(folder))
            self._status_label.setText("Device B folder selected.")

    def _sync_now(self) -> None:
        """Run a one-time sync."""
        self._dashboard.set_target(Path(self._target_input.text()))
        try:
            summary = self._dashboard.sync_now()
            if summary is None:
                self._show_error("No workspace selected", "Open a workspace and choose a Device B folder first.")
                return
            self._activity_label.setText(
                f"Synced now. Copied {summary.copied}, skipped {summary.skipped}, conflicts {summary.conflicts}."
            )
            self._status_label.setText("Sync complete.")
        except Exception as exc:  # noqa: BLE001
            self._show_error("Sync failed", str(exc))

    def _toggle_watch_sync(self) -> None:
        """Start or stop local automatic sync."""
        if self._watch_process is not None and self._watch_process.state() != QProcess.NotRunning:
            self._watch_process.kill()
            self._watch_process = None
            self._auto_sync_button.setText("Start Auto Sync")
            self._status_label.setText("Auto sync stopped.")
            return

        source = self._dashboard.state.workspace_path
        target = Path(self._target_input.text())
        if source is None:
            self._show_error("No workspace selected", "Open a workspace first.")
            return
        target.mkdir(parents=True, exist_ok=True)
        self._dashboard.set_target(target)

        process = QProcess(self)
        process.setWorkingDirectory(str(self._project_root))
        process.setProgram(sys.executable)
        process.setArguments(["-m", "devsync", "watch-sync", str(source), str(target), "--interval", "2"])
        process.readyReadStandardOutput.connect(self._read_watch_output)
        process.readyReadStandardError.connect(self._read_watch_error)
        process.start()
        if not process.waitForStarted(3000):
            self._show_error("Auto sync could not start", "Please try again.")
            return

        self._watch_process = process
        self._auto_sync_button.setText("Stop Auto Sync")
        self._status_label.setText("Auto sync is running.")

    def _read_watch_output(self) -> None:
        """Read auto-sync output."""
        if self._watch_process is None:
            return
        output = bytes(self._watch_process.readAllStandardOutput()).decode("utf-8", errors="replace").strip()
        if output:
            self._activity_label.setText(output.splitlines()[-1])
            self._status_label.setText("Auto sync updated files.")

    def _read_watch_error(self) -> None:
        """Read auto-sync errors."""
        if self._watch_process is None:
            return
        output = bytes(self._watch_process.readAllStandardError()).decode("utf-8", errors="replace").strip()
        if output:
            self._status_label.setText("Auto sync needs attention.")
            self._activity_label.setText(output.splitlines()[-1])

    def _refresh_current_workspace(self) -> None:
        """Refresh dashboard metrics if a workspace is open."""
        state = self._dashboard.state
        if self._stack.currentIndex() == 1 and state.workspace_path:
            try:
                self._render_dashboard(self._dashboard.open_workspace(state.workspace_path))
            except Exception:
                return

    def _load_default_workspace_if_available(self) -> None:
        """Open the Desktop test folder when it is already a workspace."""
        source = default_demo_source()
        if source.exists() and (source / ".devsync" / "devsync.sqlite").exists():
            self._target_input.setText(str(default_demo_target()))
            self._open_workspace_path(source)
        else:
            self._show_page(0, "Home")

    def _set_default_target_if_empty(self) -> None:
        """Set a default target folder when the target input is empty."""
        if not self._target_input.text().strip():
            self._target_input.setText(str(default_demo_target()))

    def _render_dashboard(self, state: DashboardState) -> None:
        """Render dashboard state."""
        self._workspace_title.setText(state.workspace_path.name if state.workspace_path else "Workspace")
        self._workspace_subtitle.setText("Everything is up to date")
        self._replace_card_text(
            self._status_card,
            state.workspace_path.name if state.workspace_path else "No workspace open",
            str(state.workspace_path) if state.workspace_path else "Choose a workspace from Home.",
            "Local preview sync is ready.",
        )
        self._files_card._value_label.setText(str(state.active_files))  # type: ignore[attr-defined]
        self._storage_card._value_label.setText(self._format_bytes(state.tracked_bytes))  # type: ignore[attr-defined]
        self._snapshots_card._value_label.setText(str(state.snapshots))  # type: ignore[attr-defined]

    def _replace_card_text(self, card: QFrame, title: str, subtitle: str, detail: str) -> None:
        """Replace labels inside an info card."""
        labels = card.findChildren(QLabel)
        if len(labels) >= 3:
            labels[0].setText(title)
            labels[1].setText(subtitle)
            labels[2].setText(detail)

    def _format_bytes(self, value: int) -> str:
        """Format byte counts for people."""
        if value < 1024:
            return f"{value} B"
        if value < 1024 * 1024:
            return f"{value / 1024:.1f} KB"
        return f"{value / (1024 * 1024):.1f} MB"

    def _show_error(self, title: str, message: str) -> None:
        """Show a friendly error dialog."""
        QMessageBox.warning(self, title, message)
