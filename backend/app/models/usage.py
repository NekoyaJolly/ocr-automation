"""利用ログのデータモデル。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class UsageLogEntry(BaseModel):
    """利用ログエントリ。"""

    license_id: str
    timestamp: datetime
    endpoint: str
    status: Literal["success", "failure"]
    processing_time_ms: int = 0
    gemini_input_tokens: int = 0
    gemini_output_tokens: int = 0
    error_type: str | None = None
