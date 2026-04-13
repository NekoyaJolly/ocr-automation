"""Gemini の confidence 付きネスト JSON を平坦化する。"""

from __future__ import annotations

from typing import Any, Literal

from app.models.ocr_result_model import FieldConfidence

ConfidenceLiteral = Literal["certain", "inferred", "uncertain"]

_ORDER: dict[ConfidenceLiteral, int] = {"certain": 0, "inferred": 1, "uncertain": 2}


def _worst(a: ConfidenceLiteral, b: ConfidenceLiteral) -> ConfidenceLiteral:
    return a if _ORDER[a] >= _ORDER[b] else b


def _parse_confidence(raw: Any) -> ConfidenceLiteral:
    if raw == "inferred":
        return "inferred"
    if raw == "uncertain":
        return "uncertain"
    return "certain"


def _unwrap_cell(obj: Any) -> tuple[Any, FieldConfidence]:
    """単一フィールドの {value, confidence, inference_reason} を解釈。"""
    if not isinstance(obj, dict):
        return obj, FieldConfidence(value=obj, confidence="certain", inference_reason=None)
    if "value" not in obj or "confidence" not in obj:
        return obj, FieldConfidence(value=obj, confidence="certain", inference_reason=None)
    conf = _parse_confidence(obj.get("confidence"))
    reason = obj.get("inference_reason")
    reason = reason.strip() or None if isinstance(reason, str) else None
    return obj["value"], FieldConfidence(
        value=obj["value"],
        confidence=conf,
        inference_reason=reason,
    )


def _flatten_row(row: Any) -> tuple[dict[str, Any], ConfidenceLiteral]:
    """明細 1 行をフラット dict にし、行内の最悪 confidence を返す。"""
    if not isinstance(row, dict):
        return {}, "certain"
    out: dict[str, Any] = {}
    worst: ConfidenceLiteral = "certain"
    for sk, cell in row.items():
        val, fc = _unwrap_cell(cell)
        out[sk] = val
        worst = _worst(worst, fc.confidence)
    return out, worst


def flatten_gemini_extracted(
    data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, FieldConfidence]]:
    """トップレベルおよび明細行の confidence 付きオブジェクトを平坦化する。

    欠損時は value ごと certain として扱う。
    """
    flat: dict[str, Any] = {}
    fmap: dict[str, FieldConfidence] = {}

    for key, raw in data.items():
        if isinstance(raw, list):
            rows_out: list[dict[str, Any]] = []
            row_worst: ConfidenceLiteral = "certain"
            for row in raw:
                rdict, rw = _flatten_row(row)
                rows_out.append(rdict)
                row_worst = _worst(row_worst, rw)
            flat[key] = rows_out
            fmap[key] = FieldConfidence(
                value=rows_out,
                confidence=row_worst,
                inference_reason=None,
            )
            continue

        val, fc = _unwrap_cell(raw)

        if isinstance(val, list) and (not val or isinstance(val[0], dict)):
            rows_out: list[dict[str, Any]] = []
            row_worst: ConfidenceLiteral = "certain"
            for row in val:
                rdict, rw = _flatten_row(row)
                rows_out.append(rdict)
                row_worst = _worst(row_worst, rw)
            flat[key] = rows_out
            merged = _worst(fc.confidence, row_worst)
            fmap[key] = FieldConfidence(
                value=rows_out,
                confidence=merged,
                inference_reason=fc.inference_reason,
            )
            continue

        flat[key] = val
        fmap[key] = fc

    return flat, fmap
