"""利用量記録サービス。"""

from datetime import UTC, datetime

from app.models.usage import UsageLogEntry
from app.repositories.usage_log_repository import UsageLogRepository


class UsageService:
    """利用量の記録と集計を行うサービス。"""

    def __init__(self, repo: UsageLogRepository) -> None:
        self._repo = repo

    async def record(
        self,
        license_id: str,
        endpoint: str,
        status: str,
        processing_time_ms: int = 0,
        gemini_input_tokens: int = 0,
        gemini_output_tokens: int = 0,
        error_type: str | None = None,
    ) -> None:
        """利用ログを記録する。"""
        entry = UsageLogEntry(
            license_id=license_id,
            timestamp=datetime.now(UTC),
            endpoint=endpoint,
            status=status,  # type: ignore[arg-type]
            processing_time_ms=processing_time_ms,
            gemini_input_tokens=gemini_input_tokens,
            gemini_output_tokens=gemini_output_tokens,
            error_type=error_type,
        )
        await self._repo.record(entry)

    async def get_monthly_count(self, license_id: str) -> int:
        """当月の利用回数を取得する。"""
        return await self._repo.get_monthly_count(license_id)
