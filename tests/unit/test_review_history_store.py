"""ReviewHistoryStore の単体テスト。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.infrastructure import review_history_store as rhs
from app.infrastructure.review_history_store import ReviewHistoryStore
from app.models.job_model import Job, ReviewStatus


def _job(job_id: str, tmp: Path) -> Job:
    img = tmp / f"{job_id}.jpg"
    img.write_bytes(b"x")
    return Job(
        job_id=job_id,
        source_file=img,
        template_set_name="test_set",
        review_status=ReviewStatus.PENDING,
        review_required=True,
        review_reasons=["needs check"],
        raw_ocr_result={"k": 1},
        user_corrected_result={"t": {"__raw__": {"a": 1}}},
    )


def test_save_approved_creates_monthly_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fixed = datetime(2026, 4, 15, 12, 0, 0)
    monkeypatch.setattr(rhs, "_now", lambda: fixed)
    store = ReviewHistoryStore(tmp_path)
    job = _job("j1", tmp_path)
    out = tmp_path / "export" / "a.txt"
    out.parent.mkdir(parents=True)
    out.write_text("x")
    store.save_approved(job, [out])

    month_dir = tmp_path / "2026-04"
    assert month_dir.is_dir()
    fp = month_dir / "j1.json"
    assert fp.exists()
    entries = store.list_history("2026-04")
    assert len(entries) == 1
    assert entries[0].outcome == "approved"
    assert entries[0].job_id == "j1"
    assert str(out) in entries[0].output_files


def test_save_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(rhs, "_now", lambda: datetime(2026, 4, 1))
    store = ReviewHistoryStore(tmp_path)
    job = _job("j2", tmp_path)
    store.save_rejected(job, "品質不足")

    fp = tmp_path / "2026-04" / "j2.json"
    assert fp.exists()
    e = store.list_history("2026-04")[0]
    assert e.outcome == "rejected"
    assert e.rejection_reason == "品質不足"
    assert e.output_files == []


def test_multiple_same_month(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(rhs, "_now", lambda: datetime(2026, 4, 10))
    store = ReviewHistoryStore(tmp_path)
    store.save_approved(_job("a", tmp_path), [tmp_path / "o1.txt"])
    store.save_approved(_job("b", tmp_path), [tmp_path / "o2.txt"])
    assert len(store.list_history("2026-04")) == 2


def test_different_months_separate_folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = ReviewHistoryStore(tmp_path)
    monkeypatch.setattr(rhs, "_now", lambda: datetime(2026, 4, 28))
    store.save_approved(_job("apr", tmp_path), [tmp_path / "x.txt"])
    monkeypatch.setattr(rhs, "_now", lambda: datetime(2026, 5, 2))
    store.save_approved(_job("may", tmp_path), [tmp_path / "y.txt"])

    assert (tmp_path / "2026-04" / "apr.json").exists()
    assert (tmp_path / "2026-05" / "may.json").exists()
    assert len(store.list_history("2026-04")) == 1
    assert len(store.list_history("2026-05")) == 1


def test_list_history_none_all_months(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = ReviewHistoryStore(tmp_path)
    monkeypatch.setattr(rhs, "_now", lambda: datetime(2026, 4, 1))
    store.save_approved(_job("x", tmp_path), [tmp_path / "p.txt"])
    monkeypatch.setattr(rhs, "_now", lambda: datetime(2026, 5, 1))
    store.save_approved(_job("y", tmp_path), [tmp_path / "q.txt"])
    all_e = store.list_history(None)
    assert len(all_e) == 2
    assert {e.job_id for e in all_e} == {"x", "y"}


def test_list_history_invalid_month_returns_empty(tmp_path: Path):
    store = ReviewHistoryStore(tmp_path)
    assert store.list_history("not-a-month") == []
    assert store.list_history("2026-13") == []
