"""ライセンス検証エンドポイント。"""

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.exceptions import LicenseExpiredError, LicenseInvalidError
from app.models.license import LicenseVerifyResponse
from app.repositories.license_repository import LicenseRepository
from app.services.license_service import LicenseService

router = APIRouter()


def _get_license_service(request: Request) -> LicenseService:
    db = request.app.state.db
    repo = LicenseRepository(db)
    return LicenseService(repo)


@router.post("/verify", response_model=LicenseVerifyResponse)
async def verify_license(
    request: Request,
    x_license_key: str = Header(..., alias="X-License-Key"),
) -> LicenseVerifyResponse:
    """ライセンスキーを検証する。"""
    service = _get_license_service(request)
    try:
        return await service.verify(x_license_key)
    except LicenseInvalidError:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "license_invalid",
                "message": "ライセンスキーが無効です",
            },
        ) from None
    except LicenseExpiredError:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "license_expired",
                "message": "ライセンスキーの有効期限が切れています",
            },
        ) from None
