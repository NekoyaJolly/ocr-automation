"""インフラ層のユニットテスト。"""

from pathlib import Path

from app.infrastructure.paths import get_app_data_dir, get_log_dir
from app.infrastructure.settings_store import SettingsStore
from app.models.settings_model import AppSettings


class TestPaths:
    def test_app_data_dir_exists(self):
        d = get_app_data_dir()
        assert d.exists()

    def test_log_dir_exists(self):
        d = get_log_dir()
        assert d.exists()


class TestSettingsStore:
    def test_load_default(self, tmp_path: Path):
        store = SettingsStore(path=tmp_path / "settings.json")
        settings = store.load()
        assert settings.log_level == "INFO"

    def test_save_and_load(self, tmp_path: Path):
        path = tmp_path / "settings.json"
        store = SettingsStore(path=path)

        settings = AppSettings()
        settings.log_level = "DEBUG"
        store.save(settings)

        loaded = store.load()
        assert loaded.log_level == "DEBUG"

    def test_load_corrupted(self, tmp_path: Path):
        path = tmp_path / "settings.json"
        path.write_text("not valid json{{{", encoding="utf-8")

        store = SettingsStore(path=path)
        settings = store.load()
        assert settings.log_level == "INFO"  # default fallback
