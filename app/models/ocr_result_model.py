"""OCR 結果のデータモデル (v2: Gemini 構造化出力)。"""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class FieldConfidence(BaseModel):
    """フィールド単位の信頼度 (Gemini または後方互換デフォルト)。"""

    value: Any = None
    confidence: Literal["certain", "inferred", "uncertain"] = "certain"
    inference_reason: str | None = None


class OCRResult(BaseModel):
    """Gemini が返す構造化データを保持する。

    extracted_data はプレーン値 (平坦化後) の dict。
    field_confidences はトップレベル source_key ごとのメタデータ。
    """

    source_image: Path
    extracted_data: dict[str, Any]
    field_confidences: dict[str, FieldConfidence] = Field(default_factory=dict)
    raw_response: dict[str, Any] | None = None
    processing_time_ms: int = 0
