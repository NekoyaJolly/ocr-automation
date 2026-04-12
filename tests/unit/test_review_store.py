"""review_store の単体テスト。"""

from pathlib import Path

from app.infrastructure.review_store import ReviewStore
from app.models.job_model import Job, ReviewStatus


def test_save_load_delete_roundtrip(tmp_path: Path):
    store = ReviewStore(tmp_path)
    job = Job(
        job_id="j1",
        source_file=tmp_path / "x.jpg",
        template_set_name="set_a",
        review_status=ReviewStatus.PENDING,
        review_required=True,
        review_reasons=["test"],
    )
    store.save_job(job)
    loaded = store.load_all_review_jobs()
    assert len(loaded) == 1
    assert loaded[0].job_id == "j1"
    assert loaded[0].review_reasons == ["test"]

    store.delete_job("j1")
    assert store.load_all_review_jobs() == []
