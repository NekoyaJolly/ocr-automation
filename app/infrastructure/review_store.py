"""レビュー待ちジョブの永続化。"""

from __future__ import annotations

import json
from pathlib import Path

from app.infrastructure.logger import get_logger
from app.models.job_model import Job

logger = get_logger(__name__)


class ReviewStore:
    """ユーザーデータ配下の review_jobs に Job を JSON 保存する。"""

    def __init__(self, base_dir: Path) -> None:
        self._dir = base_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def save_job(self, job: Job) -> None:
        path = self._dir / f"{job.job_id}.json"
        path.write_text(job.model_dump_json(indent=2), encoding="utf-8")

    def load_all_review_jobs(self) -> list[Job]:
        jobs: list[Job] = []
        for file_path in sorted(self._dir.glob("*.json")):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                jobs.append(Job.model_validate(data))
            except Exception as e:
                logger.warning(
                    "レビュー待ちジョブ JSON の読み込みをスキップしました: %s — %s",
                    file_path,
                    e,
                )
                continue
        return jobs

    def delete_job(self, job_id: str) -> None:
        path = self._dir / f"{job_id}.json"
        if path.exists():
            path.unlink()
