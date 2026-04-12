"""ジョブ管理のデータモデル。"""

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.models.template_model import TemplateApplicationResult


class JobStatus(StrEnum):
    """ジョブの処理状態。"""

    PENDING = "pending"
    PROCESSING = "processing"
    PARTIAL_SUCCESS = "partial_success"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewStatus(StrEnum):
    """手修正レビューに関する状態。"""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class Job(BaseModel):
    """1 枚の画像に対する処理ジョブ。"""

    job_id: str
    source_file: Path
    template_set_name: str
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None
    template_results: list[TemplateApplicationResult] = Field(default_factory=list)

    # 手修正 UI 向け: テンプレートキーごとの抽出・整形結果はネスト dict で保持
    review_status: ReviewStatus = ReviewStatus.NOT_REQUIRED
    review_required: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    raw_ocr_result: dict[str, Any] = Field(default_factory=dict)
    normalized_result: dict[str, Any] = Field(default_factory=dict)
    user_corrected_result: dict[str, Any] = Field(default_factory=dict)
    reviewed_at: datetime | None = None
