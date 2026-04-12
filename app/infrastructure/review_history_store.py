"""レビュー履歴の月次 JSON 永続化。"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from app.models.job_model import Job
from app.models.review_history_model import ReviewHistoryEntry

_YM_RE = re.compile(r"^\d{4}-\d{2}$")


def _now() -> datetime:
    return datetime.now()


class ReviewHistoryStore:
    """review_history/<YYYY-MM>/<job_id>.json に履歴を保存する。"""

    def __init__(self, root_dir: Path) -> None:
        self._root = root_dir
        self._root.mkdir(parents=True, exist_ok=True)

    def _entry_path(self, decided_at: datetime, job_id: str) -> Path:
        ym = decided_at.strftime("%Y-%m")
        month_dir = self._root / ym
        month_dir.mkdir(parents=True, exist_ok=True)
        return month_dir / f"{job_id}.json"

    def save_approved(self, job: Job, output_files: list[Path]) -> None:
        decided_at = _now()
        uc = job.user_corrected_result
        entry = ReviewHistoryEntry(
            job_id=job.job_id,
            source_file_path=str(job.source_file),
            template_set_name=job.template_set_name,
            outcome="approved",
            decided_at=decided_at,
            user_corrected_result=uc if uc else None,
            output_files=[str(p) for p in output_files],
            raw_ocr_result=dict(job.raw_ocr_result),
            review_reasons=list(job.review_reasons),
        )
        path = self._entry_path(decided_at, job.job_id)
        path.write_text(entry.model_dump_json(indent=2), encoding="utf-8")

    def save_rejected(self, job: Job, reason: str) -> None:
        decided_at = _now()
        entry = ReviewHistoryEntry(
            job_id=job.job_id,
            source_file_path=str(job.source_file),
            template_set_name=job.template_set_name,
            outcome="rejected",
            decided_at=decided_at,
            rejection_reason=reason.strip() if reason.strip() else None,
            raw_ocr_result=dict(job.raw_ocr_result),
            review_reasons=list(job.review_reasons),
        )
        path = self._entry_path(decided_at, job.job_id)
        path.write_text(entry.model_dump_json(indent=2), encoding="utf-8")

    def list_history(self, year_month: str | None = None) -> list[ReviewHistoryEntry]:
        """year_month が "YYYY-MM" のときその月のみ。None のとき全月。"""
        entries: list[ReviewHistoryEntry] = []
        if year_month is not None:
            if not _YM_RE.match(year_month):
                return []
            dirs = [self._root / year_month] if (self._root / year_month).is_dir() else []
        else:
            dirs = sorted(d for d in self._root.iterdir() if d.is_dir())
        for d in dirs:
            for fp in sorted(d.glob("*.json")):
                try:
                    text = fp.read_text(encoding="utf-8")
                    entries.append(ReviewHistoryEntry.model_validate_json(text))
                except Exception:
                    continue
        entries.sort(key=lambda e: e.decided_at, reverse=True)
        return entries
