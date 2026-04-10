"""E2E パイプラインの統合テスト (モック OCR エンジン使用)。"""

import shutil
from pathlib import Path
from typing import Any

from app.core.ocr_engine import OCREngine
from app.core.template import (
    TemplateEngine,
    load_all_template_sets,
    load_all_templates,
)
from app.models.ocr_result_model import OCRResult


class MockOCREngine(OCREngine):
    def process(
        self,
        image_path: Path,
        extraction_prompt: str,
        response_schema: dict[str, Any],
        license_key: str,
    ) -> OCRResult:
        return OCRResult(
            source_image=image_path,
            extracted_data={
                "invoice_no": "INV-2026-001",
                "issue_date": "2026-04-11",
                "customer_name": "田中商事",
                "items": [
                    {"name": "商品A", "quantity": 10, "unit_price": 500, "amount": 5000},
                    {"name": "商品B", "quantity": 5, "unit_price": 1500, "amount": 7500},
                ],
                "total_amount": 12500,
            },
            processing_time_ms=100,
        )


class TestE2EPipeline:
    """E2E パイプライン: テンプレート読込 → OCR → エクスポート。"""

    def test_load_bundled_templates(self):
        templates_dir = Path(__file__).parent.parent.parent / "templates"
        templates = load_all_templates([templates_dir])
        assert len(templates) >= 2
        assert "default_invoice" in templates
        assert "default_receipt" in templates

    def test_load_bundled_template_sets(self):
        sets_dir = Path(__file__).parent.parent.parent / "template_sets"
        sets = load_all_template_sets([sets_dir])
        assert "default_set" in sets
        s = sets["default_set"]
        assert len(s.entries) == 2

    def test_full_pipeline_with_set(self, tmp_path: Path):
        """1枚の画像 → テンプレートセット適用 → 複数ファイル同時出力。"""
        templates_dir = Path(__file__).parent.parent.parent / "templates"
        sets_dir = Path(__file__).parent.parent.parent / "template_sets"

        templates = load_all_templates([templates_dir])
        sets = load_all_template_sets([sets_dir])

        image = tmp_path / "input" / "test.jpg"
        image.parent.mkdir(parents=True)
        image.write_bytes(b"\xff\xd8\xff")

        output_root = tmp_path / "output"
        engine = TemplateEngine()
        ocr = MockOCREngine()

        template_set = sets["default_set"]
        results = engine.apply_set(
            ocr_engine=ocr,
            image_path=image,
            template_set=template_set,
            templates_by_name=templates,
            output_root=output_root,
            license_key="test-license-key",
        )

        assert len(results) == 2

        successes = [r for r in results if r.status == "success"]
        assert len(successes) == 2

        invoices_dir = output_root / "invoices"
        receipts_dir = output_root / "receipts"
        assert invoices_dir.exists()
        assert receipts_dir.exists()

        xlsx_files = list(invoices_dir.glob("*.xlsx"))
        txt_files = list(receipts_dir.glob("*.txt"))
        assert len(xlsx_files) == 1
        assert len(txt_files) == 1

    def test_partial_success(self, tmp_path: Path):
        """セット内の一部テンプレートが見つからない場合、部分成功を許容する。"""
        templates_dir = Path(__file__).parent.parent.parent / "templates"
        templates = load_all_templates([templates_dir])

        from app.models.template_model import TemplateSet, TemplateSetEntry
        partial_set = TemplateSet(
            name="部分テスト",
            entries=[
                TemplateSetEntry(
                    template_name="default_invoice",
                    output_subfolder="invoices",
                ),
                TemplateSetEntry(
                    template_name="存在しないテンプレート",
                    output_subfolder="nonexistent",
                ),
            ],
        )

        image = tmp_path / "test.jpg"
        image.write_bytes(b"\xff\xd8\xff")

        engine = TemplateEngine()
        ocr = MockOCREngine()
        results = engine.apply_set(
            ocr_engine=ocr,
            image_path=image,
            template_set=partial_set,
            templates_by_name=templates,
            output_root=tmp_path / "output",
            license_key="key",
        )

        assert len(results) == 2
        statuses = {r.template_name: r.status for r in results}
        assert statuses["default_invoice"] == "success"
        assert statuses["存在しないテンプレート"] == "failed"

    def test_file_move_to_processed(self, tmp_path: Path):
        """処理済みファイルが正しく移動されることを確認。"""
        source = tmp_path / "input" / "test.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"\xff\xd8\xff")

        processed_dir = tmp_path / "processed"
        processed_dir.mkdir()

        dest = processed_dir / source.name
        shutil.move(str(source), str(dest))

        assert not source.exists()
        assert dest.exists()

    def test_file_move_to_failed(self, tmp_path: Path):
        """失敗ファイルが失敗フォルダに移動されることを確認。"""
        source = tmp_path / "input" / "test.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"\xff\xd8\xff")

        failed_dir = tmp_path / "failed"
        failed_dir.mkdir()

        dest = failed_dir / source.name
        shutil.move(str(source), str(dest))

        assert not source.exists()
        assert dest.exists()
