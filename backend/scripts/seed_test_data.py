"""テストデータ投入スクリプト。"""

import asyncio
import os
from datetime import datetime, timezone

from google.cloud.firestore import AsyncClient  # type: ignore[import-untyped]


async def seed() -> None:
    project_id = os.environ.get("BACKEND_PROJECT_ID", "ocr-automation-dev")
    db = AsyncClient(project=project_id)

    test_license = {
        "company_name": "テスト株式会社",
        "contact_email": "test@example.com",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime(2027, 12, 31, tzinfo=timezone.utc),
        "monthly_quota": 1000,
        "current_month_usage": 0,
        "current_month_period": datetime.now(timezone.utc).strftime("%Y-%m"),
        "notes": "テスト用ライセンス",
    }

    key = "OCRA-TEST-0001-AAAA-BBBB"
    await db.collection("licenses").document(key).set(test_license)
    print(f"テストライセンスを作成しました: {key}")

    db.close()


if __name__ == "__main__":
    asyncio.run(seed())
