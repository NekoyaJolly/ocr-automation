"""レビュー承認・却下の履歴エントリ。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ReviewHistoryEntry(BaseModel):
    """1 件のレビュー判断履歴 (JSON 永続化用)。"""

    job_id: str
    source_file_path: str
    template_set_name: str
    outcome: Literal["approved", "rejected"]
    decided_at: datetime

    user_corrected_result: dict[str, Any] | None = None
    output_files: list[str] = Field(default_factory=list)

    rejection_reason: str | None = None

    raw_ocr_result: dict[str, Any] = Field(default_factory=dict)
    review_reasons: list[str] = Field(default_factory=list)
