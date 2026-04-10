"""ユーティリティ関数。"""

import uuid
from datetime import datetime


def generate_job_id() -> str:
    """一意なジョブ ID を生成する。"""
    return f"job-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
