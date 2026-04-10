"""OCR 結果のデータモデル (v2: Gemini 構造化出力)。"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel


class OCRResult(BaseModel):
    """Gemini が返す構造化データを保持する。

    v1 の OCRBlock (テキスト + bbox + 信頼度) は廃止。
    v2 では Gemini が直接構造化 JSON を返すため、ブロック単位の
    テキスト情報は中間表現として持たない。
    """

    source_image: Path
    extracted_data: dict[str, Any]
    raw_response: dict[str, Any] | None = None
    processing_time_ms: int = 0
