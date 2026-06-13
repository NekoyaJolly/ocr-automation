"""OCR 処理結果のデータモデル定義。"""

from pathlib import Path

from pydantic import BaseModel, Field


class OCRBlock(BaseModel):
    """OCR で検出された 1 ブロック（行）の情報。"""

    text: str
    bbox: tuple[int, int, int, int] = Field(description="x, y, width, height")
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class OCRResult(BaseModel):
    """1 枚の画像に対する OCR 処理結果。"""

    source_image: Path
    blocks: list[OCRBlock] = Field(default_factory=list)
    raw_text: str = ""
    processing_time_ms: int = 0
