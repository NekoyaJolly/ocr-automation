"""controllers/ocr_worker.py のユニットテスト。"""

from pathlib import Path
from unittest.mock import MagicMock

from app.controllers.ocr_worker import OCRWorker
from app.models.ocr_result_model import OCRBlock, OCRResult




class TestOCRWorkerHandleFailure:
    """OCRWorker の _handle_failure メソッドのテスト。"""

    def test_copies_image_and_writes_error_log(self, tmp_path: Path) -> None:
        """失敗時に画像がコピーされ、エラーログが作成されることを確認。"""
        mock_engine = MagicMock()
        output_dir = tmp_path / "output"
        failed_dir = tmp_path / "failed"
        worker = OCRWorker(mock_engine, output_dir, failed_dir)

        image_path = tmp_path / "scan001.jpg"
        image_path.write_bytes(b"\xff\xd8\xff" + b"x" * 100)

        worker._handle_failure(image_path, "テストエラー")

        assert failed_dir.exists()
        copied_files = list(failed_dir.glob("scan001*"))
        assert len(copied_files) >= 1

        error_logs = list(failed_dir.glob("*.error.log"))
        assert len(error_logs) == 1
        content = error_logs[0].read_text(encoding="utf-8")
        assert "テストエラー" in content
