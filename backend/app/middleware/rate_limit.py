"""メモリベースのレート制限ミドルウェア。"""

import time
from collections import defaultdict

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings

logger = structlog.get_logger()

EXEMPT_PATHS = {"/health"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """ライセンスキーごとのレート制限を行うミドルウェア。

    メモリベースのため、インスタンスごとに独立して動作する。
    """

    def __init__(self, app):  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        license_key = request.headers.get("X-License-Key", "anonymous")
        settings = get_settings()
        now = time.time()

        timestamps = self._requests[license_key]
        timestamps[:] = [t for t in timestamps if now - t < 60]

        per_minute = settings.rate_limit_per_minute
        per_second = settings.rate_limit_per_second

        recent_second = sum(1 for t in timestamps if now - t < 1)
        if recent_second >= per_second or len(timestamps) >= per_minute:
            logger.warning(
                "レート制限超過",
                license_key=license_key[:8],
                requests_last_minute=len(timestamps),
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Rate limit exceeded. Please try again later.",
                },
            )

        timestamps.append(now)
        return await call_next(request)
