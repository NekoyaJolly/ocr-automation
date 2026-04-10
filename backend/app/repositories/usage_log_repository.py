"""利用ログの Firestore リポジトリ。"""

from datetime import UTC, datetime

from google.cloud.firestore import AsyncClient  # type: ignore[import-untyped]

from app.models.usage import UsageLogEntry


class UsageLogRepository:
    """Firestore の usage_logs コレクションにアクセスする。"""

    COLLECTION = "usage_logs"

    def __init__(self, db: AsyncClient) -> None:
        self._db = db

    async def record(self, entry: UsageLogEntry) -> None:
        """利用ログを記録する。"""
        data = entry.model_dump(mode="json")
        await self._db.collection(self.COLLECTION).add(data)

    async def get_monthly_count(self, license_id: str) -> int:
        """当月の利用回数を取得する。"""
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        query = (
            self._db.collection(self.COLLECTION)
            .where("license_id", "==", license_id)
            .where("timestamp", ">=", month_start)
            .where("status", "==", "success")
        )
        docs = query.stream()
        count = 0
        async for _ in docs:
            count += 1
        return count
