"""OCR 関連のリクエスト/レスポンスモデル。"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class OCRExtractRequest(BaseModel):
    """OCR 抽出リクエスト。"""

    image_base64: str
    image_mime_type: Literal[
        "image/jpeg", "image/png", "image/webp", "image/tiff", "application/pdf"
    ]
    extraction_prompt: str = Field(..., max_length=5000)
    response_schema: dict[str, Any]


class OCRExtractResponse(BaseModel):
    """OCR 抽出レスポンス。"""

    data: dict[str, Any]
    processing_time_ms: int
    model_used: str
