"""ライセンス検証のビジネスロジック。"""

from datetime import UTC, datetime

import structlog

from app.core.exceptions import (
    LicenseExpiredError,
    LicenseInvalidError,
    LicenseQuotaExceededError,
)
from app.models.license import LicenseVerifyResponse
from app.repositories.license_repository import LicenseRepository

logger = structlog.get_logger()


class LicenseService:
    """ライセンスの検証とクオータチェックを行う。"""

    def __init__(self, repo: LicenseRepository) -> None:
        self._repo = repo

    async def verify(self, license_key: str) -> LicenseVerifyResponse:
        """ライセンスキーを検証し、情報を返す。

        Raises:
            LicenseInvalidError: キーが存在しないか無効。
            LicenseExpiredError: 有効期限切れ。
        """
        doc = await self._repo.find(license_key)
        if doc is None:
            raise LicenseInvalidError("ライセンスキーが無効です")

        if not doc.is_active:
            raise LicenseInvalidError("ライセンスキーが無効化されています")

        now = datetime.now(UTC)
        if doc.expires_at and doc.expires_at.replace(tzinfo=UTC) < now:
            raise LicenseExpiredError("ライセンスキーの有効期限が切れています")

        return LicenseVerifyResponse(
            is_valid=True,
            company_name=doc.company_name,
            expires_at=doc.expires_at,
            monthly_quota=doc.monthly_quota,
            used_this_month=doc.current_month_usage,
            last_verified_at=now,
        )

    async def check_quota(self, license_key: str) -> None:
        """月間クオータをチェックし、超過していれば例外を投げる。

        Raises:
            LicenseQuotaExceededError: クオータ超過。
        """
        doc = await self._repo.find(license_key)
        if doc is None:
            raise LicenseInvalidError("ライセンスキーが無効です")

        current_period = datetime.now(UTC).strftime("%Y-%m")
        usage = doc.current_month_usage
        if doc.current_month_period != current_period:
            usage = 0

        if usage >= doc.monthly_quota:
            raise LicenseQuotaExceededError(
                f"月間利用上限 ({doc.monthly_quota}) に達しています"
            )

    async def record_usage(self, license_key: str) -> None:
        """利用カウントをインクリメントする。"""
        await self._repo.increment_usage(license_key)
