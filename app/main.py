"""OCR Automation App のメインエントリポイント。"""

import sys

from app.infrastructure.logger import setup_logging


def main() -> None:
    """アプリケーションを起動する。"""
    setup_logging()

    from PySide6.QtWidgets import QApplication

    from app.gui.main_window import MainWindow

    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("OCR Automation")
    qt_app.setApplicationVersion("0.1.0")

    window = MainWindow()
    window.show()

    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
