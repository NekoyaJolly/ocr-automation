"""OS のキーチェーンを使った機密情報の安全な保存。"""

import keyring

from app.infrastructure.logger import get_logger

logger = get_logger(__name__)

SERVICE_NAME = "OCRAutomation"


class KeyringStore:
    """OS キーチェーン経由で機密情報を管理する。

    macOS: Keychain Access
    Windows: Credential Manager
    Linux: Secret Service (GNOME Keyring 等)
    """

    def __init__(self, service_name: str = SERVICE_NAME) -> None:
        self._service = service_name

    def store(self, key: str, value: str) -> None:
        """キーチェーンに値を保存する。"""
        keyring.set_password(self._service, key, value)
        logger.info("キーチェーンに保存しました: key=%s", key)

    def retrieve(self, key: str) -> str | None:
        """キーチェーンから値を取得する。"""
        return keyring.get_password(self._service, key)

    def delete(self, key: str) -> None:
        """キーチェーンから値を削除する。"""
        try:
            keyring.delete_password(self._service, key)
            logger.info("キーチェーンから削除しました: key=%s", key)
        except keyring.errors.PasswordDeleteError:
            logger.warning("キーチェーンにキーが存在しません: key=%s", key)
