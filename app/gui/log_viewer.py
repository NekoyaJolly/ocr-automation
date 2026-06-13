"""ログ表示ウィジェット。

リアルタイムでログメッセージを表示する QTextEdit ベースのウィジェット。
ログレベルに応じた色分けと最大表示件数の制限を持つ。
"""

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget

_MAX_LOG_LINES = 500

_LEVEL_COLORS: dict[str, QColor] = {
    "DEBUG": QColor(128, 128, 128),
    "INFO": QColor(0, 0, 0),
    "WARNING": QColor(200, 140, 0),
    "ERROR": QColor(200, 0, 0),
    "CRITICAL": QColor(200, 0, 0),
}


class LogViewer(QWidget):
    """ログ表示ウィジェット。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._line_count = 0

        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._text_edit)

    @Slot(str, str)
    def append_log(self, level: str, message: str) -> None:
        """ログメッセージを追加する。

        Args:
            level: ログレベル (DEBUG / INFO / WARNING / ERROR)
            message: ログメッセージ
        """
        if self._line_count >= _MAX_LOG_LINES:
            self._trim_old_lines()

        color = _LEVEL_COLORS.get(level.upper(), QColor(0, 0, 0))
        fmt = QTextCharFormat()
        fmt.setForeground(color)

        cursor = self._text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(message + "\n", fmt)

        self._text_edit.setTextCursor(cursor)
        self._text_edit.ensureCursorVisible()
        self._line_count += 1

    def clear_log(self) -> None:
        """ログを全てクリアする。"""
        self._text_edit.clear()
        self._line_count = 0

    def _trim_old_lines(self) -> None:
        """古いログ行を削除して最大件数を維持する。"""
        lines_to_remove = self._line_count - _MAX_LOG_LINES + 100
        if lines_to_remove <= 0:
            return

        cursor = self._text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        for _ in range(lines_to_remove):
            cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.deleteChar()  # 残った改行を削除
        self._line_count -= lines_to_remove
