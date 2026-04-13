"""review_rules の単体テスト。"""

from app.core.review_rules import (
    ReviewTier,
    assess_review,
    source_keys_for_review_presence_marker,
)
from app.models.ocr_result_model import FieldConfidence
from app.models.template_model import FieldPlacement, Template


def _minimal_template(*, required: list[str] | None = None) -> Template:
    return Template(
        name="t",
        output_format="txt",
        output_filename_pattern="{a}.txt",
        extraction_prompt="p",
        response_schema={
            "type": "object",
            "required": required or [],
            "properties": {
                "invoice_no": {"type": "string"},
                "issue_date": {"type": "string", "format": "date"},
                "total_amount": {"type": "number"},
                "items": {"type": "array"},
            },
        },
        field_placements=[
            FieldPlacement(source_key="invoice_no", target="x"),
        ],
    )


def test_empty_extracted_needs_review():
    t = _minimal_template(required=["invoice_no"])
    a = assess_review({}, t)
    assert a.tier == ReviewTier.NEEDS_REVIEW
    assert any("空" in r for r in a.reasons)


def test_required_missing_needs_review():
    t = _minimal_template(required=["invoice_no"])
    a = assess_review({"issue_date": "2026-04-12"}, t)
    assert a.tier == ReviewTier.NEEDS_REVIEW
    assert any("invoice_no" in r for r in a.reasons)


def test_valid_data_safe():
    t = _minimal_template(required=["invoice_no"])
    data = {
        "invoice_no": "INV-1",
        "issue_date": "2026-04-12",
        "total_amount": 1000,
        "items": [{"x": 1}],
    }
    a = assess_review(data, t)
    assert a.tier == ReviewTier.SAFE
    assert a.reasons == []


def test_invalid_date_needs_review():
    t = _minimal_template()
    a = assess_review(
        {"invoice_no": "x", "issue_date": "not-a-date", "total_amount": 1, "items": [1]},
        t,
    )
    assert a.tier == ReviewTier.NEEDS_REVIEW


def test_empty_array_when_schema_array_needs_review():
    t = _minimal_template()
    a = assess_review(
        {"invoice_no": "x", "issue_date": "2026-04-01", "total_amount": 1, "items": []},
        t,
    )
    assert a.tier == ReviewTier.NEEDS_REVIEW


def test_inferred_gives_warning_when_other_rules_pass():
    t = _minimal_template(required=["invoice_no"])
    data = {
        "invoice_no": "INV-1",
        "issue_date": "2026-04-12",
        "total_amount": 1000,
        "items": [{"x": 1}],
    }
    fc = {
        "invoice_no": FieldConfidence(value="INV-1", confidence="inferred", inference_reason="O→0"),
        "issue_date": FieldConfidence(value="2026-04-12", confidence="certain"),
        "total_amount": FieldConfidence(value=1000, confidence="certain"),
        "items": FieldConfidence(value=data["items"], confidence="certain"),
    }
    a = assess_review(data, t, field_confidences=fc)
    assert a.tier == ReviewTier.WARNING


def test_uncertain_triggers_needs_review():
    t = _minimal_template(required=["invoice_no"])
    data = {
        "invoice_no": "X",
        "issue_date": "2026-04-12",
        "total_amount": 1,
        "items": [1],
    }
    fc = {
        "invoice_no": FieldConfidence(value="X", confidence="uncertain"),
        "issue_date": FieldConfidence(value="2026-04-12", confidence="certain"),
        "total_amount": FieldConfidence(value=1, confidence="certain"),
        "items": FieldConfidence(value=[1], confidence="certain"),
    }
    a = assess_review(data, t, field_confidences=fc)
    assert a.tier == ReviewTier.NEEDS_REVIEW


def test_source_keys_for_review_presence_marker_falls_back_to_schema_required():
    t = _minimal_template(required=["invoice_no"])
    assert source_keys_for_review_presence_marker(t) == frozenset({"invoice_no"})


def test_source_keys_for_review_presence_marker_follows_flags():
    """UI の * マーク対象が assess の欠落チェックキーと一致する。"""
    t = Template(
        name="inv",
        output_format="txt",
        output_filename_pattern="x.txt",
        extraction_prompt="p",
        response_schema={
            "type": "object",
            "required": ["invoice_no", "total_amount"],
            "properties": {
                "invoice_no": {"type": "string"},
                "total_amount": {"type": "number"},
            },
        },
        field_placements=[
            FieldPlacement(source_key="invoice_no", target="a", required_for_review=False),
            FieldPlacement(source_key="total_amount", target="b", required_for_review=True),
        ],
    )
    assert source_keys_for_review_presence_marker(t) == frozenset({"total_amount"})


def test_when_required_for_review_set_only_those_keys_need_values():
    """required_for_review 指定時は Schema の required よりフラグ優先 (null 許容)。"""
    t = Template(
        name="inv",
        output_format="txt",
        output_filename_pattern="x.txt",
        extraction_prompt="p",
        response_schema={
            "type": "object",
            "required": ["invoice_no", "total_amount"],
            "properties": {
                "invoice_no": {"type": "string"},
                "total_amount": {"type": "number"},
            },
        },
        field_placements=[
            FieldPlacement(source_key="invoice_no", target="a", required_for_review=False),
            FieldPlacement(source_key="total_amount", target="b", required_for_review=True),
        ],
    )
    data = {"invoice_no": None, "total_amount": 100}
    a = assess_review(data, t)
    assert a.tier == ReviewTier.SAFE


def test_required_for_review_empty_needs_review():
    t = Template(
        name="t",
        output_format="txt",
        output_filename_pattern="{a}.txt",
        extraction_prompt="p",
        response_schema={
            "type": "object",
            "required": [],
            "properties": {
                "total_amount": {"type": "number"},
            },
        },
        field_placements=[
            FieldPlacement(
                source_key="total_amount",
                target="x",
                required_for_review=True,
            ),
        ],
    )
    a = assess_review({"total_amount": None}, t, field_confidences={})
    assert a.tier == ReviewTier.NEEDS_REVIEW
