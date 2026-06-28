"""PySide6 desktop entry point."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def main() -> int:
    """Launch the desktop application when PySide6 is installed."""
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        raise RuntimeError("PySide6 is not installed. Install project dependencies to run the desktop app.") from exc

    from desktop.app.ui.windows.main_window import MainWindow

    logging.basicConfig(level=logging.INFO)
    app = QApplication(sys.argv)
    project_root = Path(__file__).resolve().parents[2]
    theme_path = project_root / "desktop" / "app" / "themes" / "dark.qss"
    app.setStyleSheet(theme_path.read_text(encoding="utf-8"))
    window = MainWindow(project_root)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
