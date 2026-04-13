"""prompt_builder の単体テスト。"""

from app.core.prompt_builder import build_extraction_prompt
from app.models.template_model import FieldPlacement, Template


def test_build_includes_role_and_field_list():
    t = Template(
        name="請求",
        description="desc",
        output_format="txt",
        output_filename_pattern="o.txt",
        response_schema={"type": "object", "properties": {}},
        industry_preset="general",
        field_placements=[
            FieldPlacement(
                source_key="invoice_no",
                target="B2",
                display_name="請求書番号",
                required_for_review=True,
            ),
        ],
    )
    p = build_extraction_prompt(t)
    assert "事務業務" in p
    assert "invoice_no" in p
    assert "請求書番号" in p
    assert "レビュー上必須" in p
    assert "推測ルール" in p
    assert "confidence" in p


def test_build_appends_custom_instructions():
    t = Template(
        name="n",
        description="d",
        output_format="txt",
        output_filename_pattern="x.txt",
        response_schema={"type": "object"},
        custom_extraction_instructions="特別に〇〇に注意",
        field_placements=[],
    )
    assert "特別に〇〇に注意" in build_extraction_prompt(t)


def test_construction_preset_in_prompt():
    t = Template(
        name="n",
        description="d",
        output_format="txt",
        output_filename_pattern="x.txt",
        response_schema={"type": "object"},
        industry_preset="construction",
        field_placements=[],
    )
    p = build_extraction_prompt(t)
    assert "建設業" in p
    assert "㎡" in p or "建設" in p
