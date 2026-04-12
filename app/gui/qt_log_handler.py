"""logging.Handler から LogViewer へメッセージを転送する。"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from app.gui.log_viewer import LogViewer


class _LogEmitter(QObject):
    """メインスレッド上のシグナルでプレーンテキストを渡す。"""

    message = Signal(str)


class QtPlainTextLogHandler(logging.Handler):
    """フォーマット済みメッセージを Qt シグナルへ送る Handler。"""

    def __init__(self, emitter: _LogEmitter) -> None:
        super().__init__()
        self._emitter = emitter
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._emitter.message.emit(msg)
        except Exception:
            self.handleError(record)


def attach_controller_logs_to_viewer(
    parent: QObject,
    log_viewer: LogViewer,
    *,
    logger_name: str = "app.controllers.app_controller",
) -> _LogEmitter:
    """指定ロガーの INFO 以上を LogViewer に表示する。

    parent に MainWindow などを渡し、Emitter の寿命を GUI と揃える。
    """
    emitter = _LogEmitter(parent)
    emitter.message.connect(log_viewer.append_log)
    log = logging.getLogger(logger_name)
    handler = QtPlainTextLogHandler(emitter)
    handler.setLevel(logging.INFO)
    log.addHandler(handler)
    log.propagate = True
    return emitter
