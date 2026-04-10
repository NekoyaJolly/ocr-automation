"""リアルタイム処理ログ表示ウィジェット。"""

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget

_MAX_LOG_LINES = 500


class LogViewer(QWidget):
    """直近のログメッセージをスクロール表示するウィジェット。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(_MAX_LOG_LINES)
        self._text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self._text)

    @Slot(str)
    def append_log(self, message: str) -> None:
        """ログメッセージを追加する。"""
        self._text.appendPlainText(message)
        scrollbar = self._text.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    def clear(self) -> None:
        """ログをクリアする。"""
        self._text.clear()
