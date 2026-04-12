"""review_rules の単体テスト。"""

from app.core.review_rules import ReviewTier, assess_review
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
