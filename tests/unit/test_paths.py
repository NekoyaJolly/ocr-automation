"""infrastructure/paths.py のユニットテスト。"""

import sys
from pathlib import Path
from unittest.mock import patch

from app.infrastructure.paths import (
    APP_NAME,
    ensure_app_dirs,
    get_app_data_dir,
    get_log_dir,
    get_settings_path,
    get_user_template_sets_dir,
    get_user_templates_dir,
)


class TestGetAppDataDir:
    """get_app_data_dir のテスト。"""

    def test_macos(self) -> None:
        with patch.object(sys, "platform", "darwin"):
            result = get_app_data_dir()
            assert result == Path.home() / "Library" / "Application Support" / APP_NAME

    def test_windows_with_appdata(self) -> None:
        with (
            patch.object(sys, "platform", "win32"),
            patch.dict("os.environ", {"APPDATA": "C:\\Users\\test\\AppData\\Roaming"}),
        ):
            result = get_app_data_dir()
            assert result == Path("C:\\Users\\test\\AppData\\Roaming") / APP_NAME

    def test_windows_without_appdata(self) -> None:
        with (
            patch.object(sys, "platform", "win32"),
            patch.dict("os.environ", {}, clear=True),
        ):
            result = get_app_data_dir()
            assert APP_NAME in str(result)

    def test_linux_fallback(self) -> None:
        with patch.object(sys, "platform", "linux"):
            result = get_app_data_dir()
            assert result == Path.home() / f".{APP_NAME.lower()}"


class TestDerivedPaths:
    """派生パス関数のテスト。"""

    def test_settings_path(self) -> None:
        result = get_settings_path()
        assert result.name == "settings.json"

    def test_log_dir(self) -> None:
        result = get_log_dir()
        assert result.name == "logs"

    def test_user_templates_dir(self) -> None:
        result = get_user_templates_dir()
        assert result.name == "templates"

    def test_user_template_sets_dir(self) -> None:
        result = get_user_template_sets_dir()
        assert result.name == "template_sets"


class TestEnsureAppDirs:
    """ensure_app_dirs のテスト。"""

    def test_creates_directories(self, tmp_path: Path) -> None:
        with patch(
            "app.infrastructure.paths.get_app_data_dir",
            return_value=tmp_path / "test_app",
        ), patch(
            "app.infrastructure.paths.get_log_dir",
            return_value=tmp_path / "test_app" / "logs",
        ), patch(
            "app.infrastructure.paths.get_user_templates_dir",
            return_value=tmp_path / "test_app" / "templates",
        ), patch(
            "app.infrastructure.paths.get_user_template_sets_dir",
            return_value=tmp_path / "test_app" / "template_sets",
        ):
            ensure_app_dirs()
            assert (tmp_path / "test_app").exists()
            assert (tmp_path / "test_app" / "logs").exists()
            assert (tmp_path / "test_app" / "templates").exists()
            assert (tmp_path / "test_app" / "template_sets").exists()
