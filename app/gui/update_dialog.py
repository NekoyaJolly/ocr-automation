"""新しいバージョンのアップデート通知を表示するGUIダイアログ。"""

import webbrowser
from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QTextBrowser,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
)
from app import __version__


class UpdateDialog(QDialog):
    """アップデート通知ダイアログ。"""

    def __init__(self, update_info: dict, parent=None) -> None:
        super().__init__(parent)
        self.update_info = update_info
        self.setWindowTitle("アップデートのご案内")
        self.setFixedSize(500, 300)

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        title_label = QLabel(
            f"<b>新しいバージョンが利用可能です！</b><br>"
            f"現在のバージョン: {__version__} → 最新バージョン: {self.update_info['version']}",
            self
        )
        layout.addWidget(title_label)

        notes_label = QLabel("<b>アップデート内容 (リリースノート):</b>", self)
        layout.addWidget(notes_label)

        # リリースノートを表示するスクロール可能なテキストエリア
        self.notes_browser = QTextBrowser(self)
        self.notes_browser.setPlainText(self.update_info.get("body", "リリースノートはありません。"))
        layout.addWidget(self.notes_browser)

        button_layout = QHBoxLayout()

        self.browser_button = QPushButton("ダウンロードページを開く (ブラウザ)", self)
        self.browser_button.clicked.connect(self._on_open_browser)
        button_layout.addWidget(self.browser_button)

        self.close_button = QPushButton("後で", self)
        self.close_button.clicked.connect(self.reject)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    @Slot()
    def _on_open_browser(self) -> None:
        url = self.update_info.get("html_url") or self.update_info.get("download_url")
        if url:
            webbrowser.open(url)
        self.accept()
