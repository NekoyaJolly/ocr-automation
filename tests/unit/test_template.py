"""TemplateEngineのユニットテスト。"""

from pathlib import Path
from datetime import date
import pytest

from app.core.template import TemplateEngine, get_intersection_area
from app.models.ocr_result_model import OCRBlock, OCRResult
from app.models.template_model import FieldMapping, Template


def test_get_intersection_area():
    # 重なりあり
    box1 = (0, 0, 10, 10)
    box2 = (5, 5, 10, 10)
    assert get_intersection_area(box1, box2) == 25

    # 重なりなし
    box3 = (15, 15, 5, 5)
    assert get_intersection_area(box1, box3) == 0

    # 一致
    assert get_intersection_area(box1, box1) == 100


def test_template_engine_extract_by_position():
    ocr_result = OCRResult(
        source_image=Path("dummy.png"),
        blocks=[
            OCRBlock(text="ターゲットテキスト", bbox=(10, 10, 100, 30), confidence=0.9),
            OCRBlock(text="無関係なテキスト", bbox=(200, 200, 100, 30), confidence=0.8),
        ],
        raw_text="ターゲットテキスト\n無関係なテキスト",
        processing_time_ms=100,
    )

    mapping = FieldMapping(
        source_key="dummy",
        output_label="テスト項目",
        target_position="A1",
        data_type="string",
        extraction_type="position",
        bbox=(5, 5, 120, 40),  # 重なりがある領域
    )

    template = Template(
        name="テストテンプレート",
        output_format="txt",
        output_filename_pattern="test_{date}.txt",
        fields=[mapping],
    )

    engine = TemplateEngine()
    result = engine.apply_single(ocr_result, template)

    assert result["テスト項目"] == "ターゲットテキスト"


def test_template_engine_extract_by_keyword():
    ocr_result = OCRResult(
        source_image=Path("dummy.png"),
        blocks=[
            OCRBlock(text="請求書番号: INV-00123", bbox=(10, 10, 100, 30), confidence=0.9),
            OCRBlock(text="合計金額  ¥150,000", bbox=(10, 50, 100, 30), confidence=0.8),
        ],
        raw_text="請求書番号: INV-00123\n合計金額  ¥150,000",
        processing_time_ms=100,
    )

    template = Template(
        name="テストテンプレート",
        output_format="txt",
        output_filename_pattern="test_{date}.txt",
        fields=[
            FieldMapping(
                source_key="請求書番号",
                output_label="番号",
                target_position="A1",
                data_type="string",
                extraction_type="keyword",
            ),
            FieldMapping(
                source_key="合計金額",
                output_label="金額",
                target_position="A2",
                data_type="currency",
                extraction_type="keyword",
            ),
        ],
    )

    engine = TemplateEngine()
    result = engine.apply_single(ocr_result, template)

    assert result["番号"] == "INV-00123"
    assert result["金額"] == 150000


def test_template_engine_type_conversion():
    engine = TemplateEngine()

    # 数値/通貨
    field_num = FieldMapping(
        source_key="x", output_label="y", target_position="A1", data_type="number"
    )
    assert engine._convert_value("123", field_num) == 123
    assert engine._convert_value("  -12.50 ", field_num) == -12.5

    field_cur = FieldMapping(
        source_key="x", output_label="y", target_position="A1", data_type="currency"
    )
    assert engine._convert_value("¥1,500,000-", field_cur) == 1500000

    # 日付
    field_date1 = FieldMapping(
        source_key="x", output_label="y", target_position="A1", data_type="date"
    )
    assert engine._convert_value("2026/06/13", field_date1) == date(2026, 6, 13)
    assert engine._convert_value("2026年06月13日", field_date1) == date(2026, 6, 13)

    field_date2 = FieldMapping(
        source_key="x",
        output_label="y",
        target_position="A1",
        data_type="date",
        format_string="%Y-%m-%d",
    )
    assert engine._convert_value("2026/06/13", field_date2) == "2026-06-13"
