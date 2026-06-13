"""infrastructure/settings_store.py のユニットテスト。"""

import json
from pathlib import Path

from app.infrastructure.settings_store import SettingsStore
from app.models.settings_model import AppSettings, FolderSettings


class TestSettingsStore:
    """SettingsStore のテスト。"""

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        """保存して読み込むと同じ設定が復元されることを確認。"""
        settings_file = tmp_path / "settings.json"
        store = SettingsStore(path=settings_file)

        original = AppSettings(
            folders=FolderSettings(
                input_root=Path("/test/input"),
                output_root=Path("/test/output"),
                failed_folder=Path("/test/failed"),
                subfolder_to_set={"納品書": "delivery_set"},
            ),
            log_level="DEBUG",
        )
        store.save(original)

        assert settings_file.exists()

        loaded = store.load()
        assert loaded.log_level == "DEBUG"
        assert loaded.folders.input_root == Path("/test/input")
        assert loaded.folders.output_root == Path("/test/output")
        assert loaded.folders.failed_folder == Path("/test/failed")
        assert loaded.folders.subfolder_to_set == {"納品書": "delivery_set"}

    def test_load_nonexistent_returns_default(self, tmp_path: Path) -> None:
        """設定ファイルが存在しない場合はデフォルトを返すことを確認。"""
        store = SettingsStore(path=tmp_path / "nonexistent.json")
        settings = store.load()
        assert settings == AppSettings()

    def test_load_corrupted_returns_default(self, tmp_path: Path) -> None:
        """壊れた JSON の場合はデフォルトを返すことを確認。"""
        settings_file = tmp_path / "settings.json"
        settings_file.write_text("{ invalid json", encoding="utf-8")

        store = SettingsStore(path=settings_file)
        settings = store.load()
        assert settings == AppSettings()

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        """親ディレクトリが無い場合でも保存できることを確認。"""
        settings_file = tmp_path / "sub" / "dir" / "settings.json"
        store = SettingsStore(path=settings_file)
        store.save(AppSettings())
        assert settings_file.exists()

    def test_saved_json_is_readable(self, tmp_path: Path) -> None:
        """保存された JSON が人間が読める形式であることを確認。"""
        settings_file = tmp_path / "settings.json"
        store = SettingsStore(path=settings_file)
        store.save(AppSettings())

        raw = settings_file.read_text(encoding="utf-8")
        data = json.loads(raw)
        assert "folders" in data
        assert "log_level" in data
