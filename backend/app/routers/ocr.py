"""OCR 抽出エンドポイント。"""

import structlog
from fastapi import APIRouter, HTTPException, Request

from app.core.exceptions import GeminiError, LicenseQuotaExceededError
from app.models.ocr import OCRExtractRequest, OCRExtractResponse
from app.repositories.license_repository import LicenseRepository
from app.services.license_service import LicenseService

logger = structlog.get_logger()

router = APIRouter()


@router.post("/extract", response_model=OCRExtractResponse)
async def extract_ocr(
    request: Request,
    body: OCRExtractRequest,
) -> OCRExtractResponse:
    """画像から構造化データを抽出する。

    ライセンス認証はミドルウェアで実施済み。
    """
    license_key = getattr(request.state, "license_key", "unknown")

    db = request.app.state.db
    repo = LicenseRepository(db)
    license_service = LicenseService(repo)

    try:
        await license_service.check_quota(license_key)
    except LicenseQuotaExceededError:
        raise HTTPException(
            status_code=403,
            detail={"error": "quota_exceeded", "message": "月間利用上限に達しています"},
        ) from None

    gemini_service = request.app.state.gemini_service
    try:
        result = await gemini_service.extract(
            image_base64=body.image_base64,
            image_mime_type=body.image_mime_type,
            extraction_prompt=body.extraction_prompt,
            response_schema=body.response_schema,
        )
    except GeminiError as e:
        logger.error("Gemini 呼び出し失敗", error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "error": "gemini_error",
                "message": "OCR 処理中にエラーが発生しました",
            },
        ) from None

    await license_service.record_usage(license_key)

    return OCRExtractResponse(
        data=result.data,
        processing_time_ms=result.processing_time_ms,
        model_used=result.model_used,
    )
