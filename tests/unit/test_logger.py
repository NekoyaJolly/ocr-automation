"""infrastructure/logger.py のユニットテスト。"""

import logging
from pathlib import Path

from app.infrastructure.logger import LogSignalHandler, add_signal_handler, setup_logger


class TestSetupLogger:
    """setup_logger のテスト。"""

    def test_console_only(self) -> None:
        """コンソールハンドラのみのセットアップ。"""
        setup_logger(level="INFO", enable_file=False)
        root = logging.getLogger()
        assert root.level == logging.INFO
        handler_types = [type(h).__name__ for h in root.handlers]
        assert "StreamHandler" in handler_types

    def test_with_file_handler(self, tmp_path: Path) -> None:
        """ファイルハンドラ付きのセットアップ。"""
        setup_logger(level="DEBUG", enable_file=True, log_dir=tmp_path)
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        handler_types = [type(h).__name__ for h in root.handlers]
        assert "RotatingFileHandler" in handler_types

        log_files = list(tmp_path.glob("app_*.log"))
        assert len(log_files) >= 1

    def test_idempotent_setup(self) -> None:
        """複数回呼んでもハンドラが重複しないことを確認。"""
        setup_logger(level="INFO")
        setup_logger(level="INFO")
        root = logging.getLogger()
        stream_handlers = [
            h for h in root.handlers if type(h).__name__ == "StreamHandler"
        ]
        assert len(stream_handlers) == 1


class TestLogSignalHandler:
    """LogSignalHandler のテスト。"""

    def test_callback_called(self) -> None:
        """コールバックが呼ばれることを確認。"""
        messages: list[tuple[str, str]] = []

        def cb(level: str, msg: str) -> None:
            messages.append((level, msg))

        handler = LogSignalHandler(cb)
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="テストメッセージ",
            args=None,
            exc_info=None,
        )
        handler.emit(record)

        assert len(messages) == 1
        assert messages[0][0] == "INFO"
        assert "テストメッセージ" in messages[0][1]


class TestAddSignalHandler:
    """add_signal_handler のテスト。"""

    def test_adds_to_root_logger(self) -> None:
        setup_logger(level="INFO")
        messages: list[tuple[str, str]] = []
        handler = add_signal_handler(lambda l, m: messages.append((l, m)))

        test_logger = logging.getLogger("test.signal")
        test_logger.info("テスト")

        assert len(messages) >= 1

        root = logging.getLogger()
        root.removeHandler(handler)
