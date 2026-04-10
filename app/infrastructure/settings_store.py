"""JSON 設定ファイルの読み書き。"""

import json
from pathlib import Path

from app.infrastructure.logger import get_logger
from app.infrastructure.paths import get_settings_path
from app.models.settings_model import AppSettings

logger = get_logger(__name__)


class SettingsStore:
    """ユーザー設定の永続化を担当する。"""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or get_settings_path()

    def load(self) -> AppSettings:
        """設定ファイルを読み込む。ファイルがなければデフォルト値を返す。"""
        if not self._path.exists():
            logger.info("設定ファイルが見つかりません。デフォルト設定を使用します: %s", self._path)
            return AppSettings()

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return AppSettings.model_validate(raw)
        except Exception:
            logger.exception("設定ファイルの読み込みに失敗しました: %s", self._path)
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        """設定をファイルに保存する。"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = settings.model_dump(mode="json")
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("設定を保存しました: %s", self._path)
