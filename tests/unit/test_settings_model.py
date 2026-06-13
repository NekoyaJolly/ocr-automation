"""models/settings_model.py のユニットテスト。"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.settings_model import (
    AppSettings,
    FolderSettings,
    PrinterSettings,
    RetrySettings,
)


class TestFolderSettings:
    """FolderSettings のテスト。"""

    def test_defaults(self) -> None:
        s = FolderSettings()
        assert s.input_root is None
        assert s.output_root is None
        assert s.failed_folder is None
        assert s.subfolder_to_set == {}

    def test_with_paths(self) -> None:
        s = FolderSettings(
            input_root=Path("/input"),
            output_root=Path("/output"),
            failed_folder=Path("/failed"),
        )
        assert s.input_root == Path("/input")
        assert s.output_root == Path("/output")

    def test_subfolder_to_set(self) -> None:
        s = FolderSettings(subfolder_to_set={"納品書": "delivery_set"})
        assert s.subfolder_to_set["納品書"] == "delivery_set"


class TestPrinterSettings:
    """PrinterSettings のテスト。"""

    def test_defaults(self) -> None:
        s = PrinterSettings()
        assert s.default_printer is None
        assert s.copies == 1

    def test_invalid_copies(self) -> None:
        with pytest.raises(ValidationError):
            PrinterSettings(copies=0)


class TestRetrySettings:
    """RetrySettings のテスト。"""

    def test_defaults(self) -> None:
        s = RetrySettings()
        assert s.max_retries == 2
        assert s.initial_backoff_seconds == 1.0
        assert s.backoff_multiplier == 3.0

    def test_invalid_backoff(self) -> None:
        with pytest.raises(ValidationError):
            RetrySettings(initial_backoff_seconds=0)

    def test_invalid_multiplier(self) -> None:
        with pytest.raises(ValidationError):
            RetrySettings(backoff_multiplier=0.5)


class TestAppSettings:
    """AppSettings のテスト。"""

    def test_defaults(self) -> None:
        s = AppSettings()
        assert isinstance(s.folders, FolderSettings)
        assert isinstance(s.printer, PrinterSettings)
        assert isinstance(s.retry, RetrySettings)
        assert s.log_level == "INFO"

    def test_json_roundtrip(self) -> None:
        s = AppSettings(
            folders=FolderSettings(input_root=Path("/input")),
            log_level="DEBUG",
        )
        json_str = s.model_dump_json()
        restored = AppSettings.model_validate_json(json_str)
        assert restored.log_level == "DEBUG"
        assert restored.folders.input_root == Path("/input")

    def test_invalid_log_level(self) -> None:
        with pytest.raises(ValidationError):
            AppSettings(log_level="VERBOSE")  # type: ignore[arg-type]
