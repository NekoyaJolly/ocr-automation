"""レビュー待ち・承認まわりの統合テスト。"""

import logging
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from app.controllers.app_controller import AppController
from app.core.ocr_engine import OCREngine
from app.infrastructure.settings_store import SettingsStore
from app.models.job_model import Job, JobStatus, ReviewStatus
from app.models.ocr_result_model import OCRResult
from app.models.settings_model import AppSettings


class _FixedOCR(OCREngine):
    def process(
        self,
        image_path: Path,
        extraction_prompt: str,
        response_schema: dict[str, Any],
        license_key: str,
    ) -> OCRResult:
        return OCRResult(
            source_image=image_path,
            extracted_data={},
            processing_time_ms=1,
        )


class _LicenseStub:
    def get_active_key(self) -> str:
        return "test-key"


@pytest.fixture(scope="module")
def qapp():
    """AppController が QObject を継承するため QApplication が必要。"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def review_tmp_dirs(tmp_path: Path) -> Path:
    (tmp_path / "in").mkdir()
    (tmp_path / "out").mkdir()
    (tmp_path / "proc").mkdir()
    (tmp_path / "fail").mkdir()
    return tmp_path


_MINIMAL_TMPL_YAML = """
name: "minimal"
description: ""
output_format: "txt"
output_filename_pattern: "out.txt"
base_template_file: null
industry_preset: "general"
custom_extraction_instructions: "t"
response_schema:
  type: object
  required: []
  properties:
    note:
      type: object
      required: [value, confidence]
      properties:
        value:
          type: string
          nullable: true
        confidence:
          type: string
          enum: [certain, inferred, uncertain]
        inference_reason:
          type: string
          nullable: true
field_placements:
  - source_key: "note"
    target: "x"
    required_for_review: false
"""

_MINIMAL_SET_YAML = """
name: "minimal set"
description: ""
entries:
  - template_name: "minimal_tmpl"
    enabled: true
    output_subfolder: "done"
    auto_print: false
    printer_name: null
"""


def _make_controller(review_tmp_dirs: Path, monkeypatch: pytest.MonkeyPatch) -> AppController:
    monkeypatch.setattr(
        "app.controllers.app_controller.get_review_jobs_dir",
        lambda: review_tmp_dirs / "review_jobs",
    )
    monkeypatch.setattr(
        "app.controllers.app_controller.get_review_history_dir",
        lambda: review_tmp_dirs / "review_history",
    )
    cfg = review_tmp_dirs / "settings.json"
    store = SettingsStore(cfg)
    s = AppSettings()
    s.folders.input_root = review_tmp_dirs / "in"
    s.folders.output_root = review_tmp_dirs / "out"
    s.folders.processed_folder = review_tmp_dirs / "proc"
    s.folders.failed_folder = review_tmp_dirs / "fail"
    store.save(s)
    return AppController(
        settings_store=store,
        ocr_engine=_FixedOCR(),
        license_manager=_LicenseStub(),  # type: ignore[arg-type]
    )


def _write_minimal_user_templates(base: Path) -> None:
    ut = base / "user_templates"
    us = base / "user_sets"
    ut.mkdir(parents=True)
    us.mkdir(parents=True)
    (ut / "minimal_tmpl.yaml").write_text(_MINIMAL_TMPL_YAML.strip(), encoding="utf-8")
    (us / "minimal_set.yaml").write_text(_MINIMAL_SET_YAML.strip(), encoding="utf-8")


def _make_controller_with_minimal_export_template(
    review_tmp_dirs: Path, monkeypatch: pytest.MonkeyPatch
) -> AppController:
    _write_minimal_user_templates(review_tmp_dirs)
    monkeypatch.setattr(
        "app.controllers.app_controller.get_user_templates_dir",
        lambda: review_tmp_dirs / "user_templates",
    )
    monkeypatch.setattr(
        "app.controllers.app_controller.get_user_template_sets_dir",
        lambda: review_tmp_dirs / "user_sets",
    )
    return _make_controller(review_tmp_dirs, monkeypatch)


def test_review_job_not_moved_to_processed(
    qapp,
    review_tmp_dirs: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    ctrl = _make_controller(review_tmp_dirs, monkeypatch)
    img = review_tmp_dirs / "in" / "doc.jpg"
    img.write_bytes(b"\xff\xd8\xff")

    job = Job(
        job_id="rv1",
        source_file=img,
        template_set_name="noop",
        status=JobStatus.COMPLETED,
        review_required=True,
        review_status=ReviewStatus.PENDING,
    )
    ctrl._on_job_completed(job)

    assert "rv1" in ctrl._review_jobs
    assert img.exists()


def test_reject_moves_to_failed(qapp, review_tmp_dirs: Path, monkeypatch: pytest.MonkeyPatch):
    ctrl = _make_controller(review_tmp_dirs, monkeypatch)
    img = review_tmp_dirs / "in" / "doc2.jpg"
    img.write_bytes(b"\xff\xd8\xff")

    job = Job(
        job_id="rv2",
        source_file=img,
        template_set_name="noop",
        review_required=True,
        review_status=ReviewStatus.PENDING,
    )
    ctrl._review_jobs[job.job_id] = job
    ctrl._review_store.save_job(job)

    ok, _ = ctrl.reject_review("rv2", "テスト却下")
    assert ok
    assert "rv2" not in ctrl._review_jobs
    assert not img.exists()
    assert (review_tmp_dirs / "fail" / "doc2.jpg").exists()


def test_approve_review_end_to_end(
    qapp,
    review_tmp_dirs: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    ctrl = _make_controller_with_minimal_export_template(review_tmp_dirs, monkeypatch)
    img = review_tmp_dirs / "in" / "approve_me.jpg"
    img.write_bytes(b"\xff\xd8\xff")

    mapped = {"__raw__": {"note": "corrected"}, "note": "corrected"}
    job = Job(
        job_id="apr1",
        source_file=img,
        template_set_name="minimal_set",
        status=JobStatus.COMPLETED,
        review_required=True,
        review_status=ReviewStatus.PENDING,
        review_reasons=["low confidence"],
        raw_ocr_result={"minimal_tmpl": {"x": 1}},
        normalized_result={"minimal_tmpl": mapped},
        user_corrected_result={"minimal_tmpl": mapped},
    )

    counts: list[int] = []

    def _track(n: int) -> None:
        counts.append(n)

    ctrl.review_queue_count_changed.connect(_track)
    ctrl._on_job_completed(job)
    assert counts[-1] == 1
    assert (review_tmp_dirs / "review_jobs" / "apr1.json").exists()

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.controllers.app_controller"):
        ok, msg = ctrl.approve_review("apr1", None)
    assert ok, msg
    assert not msg
    assert (review_tmp_dirs / "out" / "done" / "out.txt").is_file()
    assert (review_tmp_dirs / "proc" / "approve_me.jpg").exists()
    assert not img.exists()
    assert "apr1" not in ctrl._review_jobs
    assert not (review_tmp_dirs / "review_jobs" / "apr1.json").exists()
    assert counts[-1] == 0

    log_text = " ".join(r.getMessage() for r in caplog.records)
    assert "レビュー再出力完了:" in log_text and "apr1" in log_text
    assert "レビュー承認:" in log_text and "template_set=minimal_set" in log_text

    hist = ctrl._review_history_store.list_history(None)
    assert any(e.job_id == "apr1" and e.outcome == "approved" for e in hist)
    approved = next(e for e in hist if e.job_id == "apr1")
    assert approved.template_set_name == "minimal_set"
    assert approved.review_reasons == ["low confidence"]
    assert approved.raw_ocr_result == {"minimal_tmpl": {"x": 1}}
    assert approved.user_corrected_result == {"minimal_tmpl": mapped}
    assert len(approved.output_files) == 1


def test_reject_review_logs_and_history(
    qapp,
    review_tmp_dirs: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    ctrl = _make_controller(review_tmp_dirs, monkeypatch)
    img = review_tmp_dirs / "in" / "rej.jpg"
    img.write_bytes(b"\xff\xd8\xff")
    job = Job(
        job_id="rj1",
        source_file=img,
        template_set_name="noop",
        review_required=True,
        review_status=ReviewStatus.PENDING,
        review_reasons=["check"],
        raw_ocr_result={"a": 1},
    )
    ctrl._review_jobs[job.job_id] = job
    ctrl._review_store.save_job(job)

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.controllers.app_controller"):
        ok, _ = ctrl.reject_review("rj1", "手動却下")
    assert ok
    log_text = " ".join(r.getMessage() for r in caplog.records)
    assert "レビュー却下:" in log_text
    assert "rj1" in log_text and "noop" in log_text and "手動却下" in log_text

    hist = ctrl._review_history_store.list_history(None)
    rejected = next(e for e in hist if e.job_id == "rj1")
    assert rejected.outcome == "rejected"
    assert rejected.rejection_reason == "手動却下"
