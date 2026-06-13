"""処理ジョブのデータモデル定義。"""

from datetime import datetime
from enum import Enum
from pathlib import Path

from typing import Literal

from pydantic import BaseModel, Field


class TemplateApplicationResult(BaseModel):
    """セット内の 1 テンプレートに対する適用結果。"""

    template_name: str = Field(description="適用されたテンプレート名")
    status: Literal["success", "failed"] = Field(description="実行結果ステータス。'success' または 'failed'")
    output_file: Path | None = Field(default=None, description="出力されたファイルパス。成功時のみ")
    error_message: str | None = Field(default=None, description="エラー発生時のメッセージ。失敗時のみ")
    retry_count: int = Field(default=0, description="このテンプレートでのリトライ試行回数")


class JobStatus(str, Enum):
    """ジョブ全体のステータス。"""

    PENDING = "pending"
    PROCESSING = "processing"
    PARTIAL_SUCCESS = "partial_success"  # 一部のテンプレートのみ成功
    COMPLETED = "completed"              # すべて成功
    FAILED = "failed"                    # すべて失敗


class Job(BaseModel):
    """1つの画像ファイルに対する処理全体のジョブ情報。"""

    job_id: str = Field(description="ジョブの一意なUUID")
    source_file: Path = Field(description="処理対象の元画像ファイルパス")
    template_set_name: str = Field(description="適用するテンプレートセット名")
    status: JobStatus = Field(default=JobStatus.PENDING, description="現在のステータス")
    created_at: datetime = Field(default_factory=datetime.now, description="ジョブ作成日時")
    completed_at: datetime | None = Field(default=None, description="ジョブ完了日時")
    template_results: list[TemplateApplicationResult] = Field(
        default_factory=list, description="適用した各テンプレートの結果リスト"
    )
