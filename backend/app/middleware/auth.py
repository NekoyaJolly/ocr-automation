"""ライセンスキー認証ミドルウェア。"""

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import LicenseExpiredError, LicenseInvalidError
from app.repositories.license_repository import LicenseRepository
from app.services.license_service import LicenseService

logger = structlog.get_logger()

EXEMPT_PATHS = {"/health", "/api/v1/license/verify"}


class LicenseAuthMiddleware(BaseHTTPMiddleware):
    """全リクエスト (除外パス以外) でライセンスキーを検証するミドルウェア。"""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        license_key = request.headers.get("X-License-Key")
        if not license_key:
            return JSONResponse(
                status_code=401,
                content={"error": "missing_license_key", "message": "X-License-Key header missing"},
            )

        db = request.app.state.db
        repo = LicenseRepository(db)
        service = LicenseService(repo)

        try:
            license_info = await service.verify(license_key)
            request.state.license_info = license_info
            request.state.license_key = license_key
        except LicenseInvalidError:
            return JSONResponse(
                status_code=401,
                content={"error": "license_invalid", "message": "License key is invalid"},
            )
        except LicenseExpiredError:
            return JSONResponse(
                status_code=403,
                content={"error": "license_expired", "message": "License key has expired"},
            )

        return await call_next(request)
