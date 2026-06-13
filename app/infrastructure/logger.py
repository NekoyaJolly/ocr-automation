"""ロガー初期化モジュール。

コンソール出力に加えて、ファイルへの日次ローテーションログを提供する。
また GUI のログ表示ウィジェットへログを転送するためのシグナルハンドラを提供する。
"""

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.infrastructure.paths import get_log_dir


_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_BACKUP_COUNT = 7


class LogSignalHandler(logging.Handler):
    """ログレコードを任意のコールバックに転送するハンドラ。

    GUI の log_viewer にログを表示するために使用する。
    コールバックは (level: str, message: str) のシグネチャで呼ばれる。
    """

    def __init__(self, callback: "Callable[[str, str], None]") -> None:  # noqa: F821
        super().__init__()
        self._callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._callback(record.levelname, msg)
        except Exception:
            self.handleError(record)


def setup_logger(
    level: str = "INFO",
    *,
    enable_file: bool = False,
    log_dir: Path | None = None,
) -> None:
    """アプリケーション全体のロガーを初期化する。

    Args:
        level: ログレベル文字列 (DEBUG / INFO / WARNING / ERROR)
        enable_file: True の場合、ファイルハンドラも追加する
        log_dir: ログファイルの出力先ディレクトリ。None の場合はデフォルトパスを使用。
    """
    root = logging.getLogger()
    log_level = getattr(logging, level.upper(), logging.INFO)
    root.setLevel(log_level)

    # 既存ハンドラをクリア（複数回呼ばれた場合の対策）
    root.handlers.clear()

    formatter = logging.Formatter(_LOG_FORMAT)

    # コンソールハンドラ
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # ファイルハンドラ
    if enable_file:
        target_dir = log_dir or get_log_dir()
        target_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        log_file = target_dir / f"app_{today}.log"

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)


def add_signal_handler(callback: "Callable[[str, str], None]") -> LogSignalHandler:  # noqa: F821
    """ログをコールバックに転送するハンドラをルートロガーに追加する。

    Args:
        callback: (level, message) を受け取るコールバック関数

    Returns:
        追加されたハンドラ（後で除去する場合に使用）
    """
    root = logging.getLogger()
    handler = LogSignalHandler(callback)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root.addHandler(handler)
    return handler
