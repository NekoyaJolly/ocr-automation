"""ジョブ管理のデータモデル。"""

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from app.models.template_model import TemplateApplicationResult


class JobStatus(StrEnum):
    """ジョブの処理状態。"""

    PENDING = "pending"
    PROCESSING = "processing"
    PARTIAL_SUCCESS = "partial_success"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(BaseModel):
    """1 枚の画像に対する処理ジョブ。"""

    job_id: str
    source_file: Path
    template_set_name: str
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None
    template_results: list[TemplateApplicationResult] = Field(default_factory=list)
