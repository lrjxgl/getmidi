"""程序入口：python -m app.main"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from . import config
from .ui.main_window import MainWindow
from .ui.theme import STYLESHEET


def main() -> int:
    config.apply_hf_env()
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    app.setApplicationName("GetMIDI")
    app.setApplicationDisplayName("GetMIDI")
    app.setOrganizationName("GetMIDI")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
