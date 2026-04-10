"""ヘルスチェックエンドポイント。"""

from datetime import UTC, datetime

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """ヘルスチェック。認証不要。"""
    return {
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
    }
