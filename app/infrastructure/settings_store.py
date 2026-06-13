"""設定の JSON 永続化モジュール。"""

import json
import logging
from pathlib import Path

from app.infrastructure.paths import get_settings_path
from app.models.settings_model import AppSettings

logger = logging.getLogger(__name__)


class SettingsStore:
    """AppSettings を JSON ファイルに読み書きする。"""

    def __init__(self, path: Path | None = None) -> None:
        """ストアを初期化する。

        Args:
            path: 設定ファイルのパス。None の場合はデフォルトパスを使用。
        """
        self._path = path or get_settings_path()

    @property
    def path(self) -> Path:
        """設定ファイルのパス。"""
        return self._path

    def load(self) -> AppSettings:
        """設定ファイルを読み込む。

        ファイルが存在しない場合やパースに失敗した場合はデフォルト設定を返す。

        Returns:
            読み込んだ設定、またはデフォルト設定
        """
        if not self._path.exists():
            logger.info("設定ファイルが見つかりません。デフォルト設定を使用します。")
            return AppSettings()

        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
            settings = AppSettings.model_validate(data)
            logger.info(f"設定を読み込みました: {self._path}")
            return settings
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"設定ファイルの読み込みに失敗しました。デフォルト設定を使用します: {e}")
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        """設定をファイルに保存する。

        Args:
            settings: 保存する設定オブジェクト
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = json.loads(settings.model_dump_json())
        raw = json.dumps(data, ensure_ascii=False, indent=2)
        self._path.write_text(raw, encoding="utf-8")
        logger.info(f"設定を保存しました: {self._path}")
