"""OCR 結果に対するレビュー要否判定 (confidence + schema)。"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.models.ocr_result_model import FieldConfidence
from app.models.template_model import Template


class ReviewTier(StrEnum):
    """判定の段階。"""

    SAFE = "safe"
    WARNING = "warning"
    NEEDS_REVIEW = "needs_review"
    ERROR = "error"


class ReviewAssessment(BaseModel):
    """レビュー判定結果。"""

    tier: ReviewTier = ReviewTier.SAFE
    reasons: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

    @property
    def needs_human_review(self) -> bool:
        """人手レビューが必要か (NEEDS_REVIEW のみ)。"""
        return self.tier == ReviewTier.NEEDS_REVIEW


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_json_schema_required(schema: dict[str, Any]) -> list[str]:
    if schema.get("type") != "object":
        return []
    req = schema.get("required")
    if isinstance(req, list):
        return [str(x) for x in req]
    return []


def _json_schema_properties(schema: dict[str, Any]) -> dict[str, Any]:
    if schema.get("type") != "object":
        return {}
    props = schema.get("properties")
    return props if isinstance(props, dict) else {}


def _unwrap_property_schema(prop: Any) -> dict[str, Any]:
    """confidence ラッパー object の内側の value 用スキーマを返す。"""
    if not isinstance(prop, dict):
        return {}
    if prop.get("type") == "object":
        inner = prop.get("properties")
        if isinstance(inner, dict) and "value" in inner and "confidence" in inner:
            v = inner.get("value")
            return v if isinstance(v, dict) else {}
    return prop


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return bool(isinstance(value, list | dict) and len(value) == 0)


def _validate_date_string(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    s = value.strip()
    if not _ISO_DATE_RE.match(s):
        return False
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _is_numeric_amount(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int | float):
        return True
    if isinstance(value, str):
        s = value.strip().replace(",", "")
        if s == "":
            return False
        try:
            float(s)
            return True
        except ValueError:
            return False
    return False


def _field_confidence_map(
    field_confidences: dict[str, FieldConfidence] | dict[str, Any] | None,
    extracted_data: dict[str, Any],
) -> dict[str, FieldConfidence]:
    if not field_confidences:
        return {
            k: FieldConfidence(value=v, confidence="certain", inference_reason=None)
            for k, v in extracted_data.items()
        }
    out: dict[str, FieldConfidence] = {}
    for k in extracted_data:
        raw = field_confidences.get(k) if isinstance(field_confidences, dict) else None
        if isinstance(raw, FieldConfidence):
            out[k] = raw
        elif isinstance(raw, dict):
            out[k] = FieldConfidence.model_validate(raw)
        else:
            out[k] = FieldConfidence(
                value=extracted_data.get(k),
                confidence="certain",
                inference_reason=None,
            )
    return out


def assess_review(
    extracted_data: dict[str, Any],
    template: Template,
    *,
    template_label: str | None = None,
    field_confidences: dict[str, FieldConfidence] | dict[str, Any] | None = None,
) -> ReviewAssessment:
    """抽出データ・confidence・スキーマから tier を決定する。"""
    prefix = f"[{template_label}] " if template_label else ""
    reasons: list[str] = []
    schema = template.response_schema

    fc_map = _field_confidence_map(field_confidences, extracted_data)

    if not extracted_data:
        return ReviewAssessment(
            tier=ReviewTier.NEEDS_REVIEW,
            reasons=[prefix + "OCR結果が空です"],
        )

    required_keys = _parse_json_schema_required(schema)
    for key in required_keys:
        value = extracted_data.get(key)
        if _is_empty_value(value):
            reasons.append(prefix + f"必須項目が未取得です: {key}")

    props = _json_schema_properties(schema)
    for key, prop in props.items():
        eff = _unwrap_property_schema(prop)
        if not eff:
            continue
        value = extracted_data.get(key)
        if _is_empty_value(value):
            continue
        fmt = eff.get("format")
        if fmt == "date" and not _validate_date_string(value):
            reasons.append(prefix + f"日付形式が不正です: {key}")
        if eff.get("type") == "number" and not _is_numeric_amount(value):
            reasons.append(prefix + f"数値として解釈できません: {key}")

    for key, prop in props.items():
        eff = _unwrap_property_schema(prop)
        if not eff:
            continue
        if eff.get("type") != "array":
            continue
        value = extracted_data.get(key)
        if isinstance(value, list) and len(value) == 0:
            reasons.append(prefix + f"明細配列が空です: {key}")

    missing_placement_keys: list[str] = []
    for fp in template.field_placements:
        if fp.source_key not in extracted_data:
            missing_placement_keys.append(fp.source_key)
    for mk in missing_placement_keys:
        reasons.append(prefix + f"テンプレート配置に必要なキーがありません: {mk}")

    if reasons:
        return ReviewAssessment(tier=ReviewTier.NEEDS_REVIEW, reasons=reasons)

    placement_keys = [fp.source_key for fp in template.field_placements]
    if not placement_keys:
        placement_keys = list(extracted_data.keys())

    required_review = {fp.source_key for fp in template.field_placements if fp.required_for_review}

    for sk in placement_keys:
        fc = fc_map.get(sk)
        if fc is None:
            fc = FieldConfidence(value=extracted_data.get(sk), confidence="certain")
        if fc.confidence == "uncertain":
            return ReviewAssessment(
                tier=ReviewTier.NEEDS_REVIEW,
                reasons=[prefix + f"不確かな読み取り: {sk}"],
            )

    for sk in required_review:
        val = extracted_data.get(sk)
        if _is_empty_value(val):
            return ReviewAssessment(
                tier=ReviewTier.NEEDS_REVIEW,
                reasons=[prefix + f"レビュー必須項目が空です: {sk}"],
            )

    all_certain = all(
        (fc_map.get(sk) or FieldConfidence(confidence="certain")).confidence == "certain"
        for sk in placement_keys
    )
    any_inferred = any(
        (fc_map.get(sk) or FieldConfidence(confidence="certain")).confidence == "inferred"
        for sk in placement_keys
    )

    if all_certain:
        return ReviewAssessment(tier=ReviewTier.SAFE, reasons=[])

    if any_inferred:
        return ReviewAssessment(
            tier=ReviewTier.WARNING,
            reasons=[prefix + "一部フィールドが形状・フォーマット推測により補完されています"],
        )

    return ReviewAssessment(tier=ReviewTier.SAFE, reasons=[])
