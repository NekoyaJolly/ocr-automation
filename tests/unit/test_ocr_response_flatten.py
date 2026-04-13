"""confidence 付きレスポンスの平坦化テスト。"""

from app.core.ocr_response_flatten import flatten_gemini_extracted


def test_flatten_wrapped_scalars():
    raw = {
        "invoice_no": {
            "value": "INV-1",
            "confidence": "certain",
            "inference_reason": None,
        },
        "total_amount": {"value": 100, "confidence": "inferred", "inference_reason": "comma"},
    }
    flat, fc = flatten_gemini_extracted(raw)
    assert flat == {"invoice_no": "INV-1", "total_amount": 100}
    assert fc["invoice_no"].confidence == "certain"
    assert fc["total_amount"].confidence == "inferred"


def test_legacy_plain_values_all_certain():
    raw = {"invoice_no": "X", "total_amount": 1}
    flat, fc = flatten_gemini_extracted(raw)
    assert flat == raw
    assert all(v.confidence == "certain" for v in fc.values())


def test_items_rows_wrapped():
    raw = {
        "items": {
            "value": [
                {
                    "name": {"value": "a", "confidence": "certain", "inference_reason": None},
                    "quantity": {"value": 1, "confidence": "inferred", "inference_reason": "shape"},
                    "unit_price": {"value": 10, "confidence": "certain", "inference_reason": None},
                    "amount": {"value": 10, "confidence": "certain", "inference_reason": None},
                },
            ],
            "confidence": "certain",
            "inference_reason": None,
        },
    }
    flat, fc = flatten_gemini_extracted(raw)
    assert flat["items"][0]["name"] == "a"
    assert flat["items"][0]["quantity"] == 1
    assert fc["items"].confidence == "inferred"
