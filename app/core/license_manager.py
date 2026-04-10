"""ライセンスキーの保管・検証を担当する。"""

from datetime import datetime

from app.exceptions import (
    LicenseExpiredError,
    LicenseInvalidError,
    LicenseNotConfiguredError,
    LicenseQuotaExceededError,
)
from app.infrastructure.http_client import HttpClient
from app.infrastructure.keyring_store import KeyringStore
from app.infrastructure.logger import get_logger
from app.models.license_model import LicenseInfo

logger = get_logger(__name__)

_LICENSE_KEYRING_KEY = "license_key"


class LicenseManager:
    """ライセンスキーの保管・バックエンド検証を管理する。"""

    def __init__(self, keyring_store: KeyringStore, http_client: HttpClient) -> None:
        self._keyring = keyring_store
        self._http = http_client
        self._cached_info: LicenseInfo | None = None

    def set_key(self, key: str) -> LicenseInfo:
        """新しいキーを設定し、バックエンドで検証する。

        Args:
            key: ライセンスキー文字列。

        Returns:
            検証済みのライセンス情報。

        Raises:
            LicenseInvalidError: キーが無効な場合。
        """
        info = self._verify_with_backend(key)
        if info.is_valid:
            self._keyring.store(_LICENSE_KEYRING_KEY, key)
            self._cached_info = info
            logger.info("ライセンスキーを設定しました: %s...", key[:8])
        else:
            raise LicenseInvalidError("ライセンスキーが無効です")
        return info

    def get_active_key(self) -> str:
        """現在有効なキーを取得する (バックエンド呼び出し時に使用)。

        Raises:
            LicenseNotConfiguredError: キーが未設定の場合。
        """
        key = self._keyring.retrieve(_LICENSE_KEYRING_KEY)
        if not key:
            raise LicenseNotConfiguredError("ライセンスキーが設定されていません")
        return key

    def get_info(self, force_refresh: bool = False) -> LicenseInfo:
        """ライセンス情報を取得する (キャッシュあり)。"""
        if self._cached_info and not force_refresh:
            return self._cached_info
        key = self.get_active_key()
        info = self._verify_with_backend(key)
        self._cached_info = info
        return info

    def validate_or_raise(self) -> LicenseInfo:
        """ライセンスが有効であることを検証し、無効なら例外を投げる。"""
        info = self.get_info(force_refresh=True)
        if not info.is_valid:
            raise LicenseInvalidError("ライセンスキーが無効です")
        if info.expires_at and info.expires_at < datetime.now(info.expires_at.tzinfo):
            raise LicenseExpiredError("ライセンスキーの有効期限が切れています")
        if info.monthly_quota > 0 and info.used_this_month >= info.monthly_quota:
            raise LicenseQuotaExceededError("月間利用上限を超過しています")
        return info

    def has_key(self) -> bool:
        """ライセンスキーが設定済みかどうかを返す。"""
        return self._keyring.retrieve(_LICENSE_KEYRING_KEY) is not None

    def clear_key(self) -> None:
        """ライセンスキーを削除する。"""
        self._keyring.delete(_LICENSE_KEYRING_KEY)
        self._cached_info = None

    def _verify_with_backend(self, key: str) -> LicenseInfo:
        """バックエンドにライセンスキーを検証させる。"""
        try:
            response = self._http.post(
                "/api/v1/license/verify",
                headers={"X-License-Key": key},
            )
            data = response.json()
            return LicenseInfo(**data)
        except Exception:
            logger.exception("ライセンス検証に失敗しました")
            return LicenseInfo(
                company_name="",
                is_valid=False,
            )
