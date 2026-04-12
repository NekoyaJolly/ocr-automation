"""OCR 結果に対するレビュー要否判定 (将来の tier 拡張を想定した戻り値)。"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.models.template_model import Template


class ReviewTier(StrEnum):
    """判定の段階。初版は SAFE / NEEDS_REVIEW のみ使用する。

    将来: WARNING (注意だが自動通過可), ERROR (ブロック) を追加し、
    NEEDS_REVIEW を人間確認必須の総称として細分化する想定。
    """

    SAFE = "safe"
    NEEDS_REVIEW = "needs_review"
    WARNING = "warning"
    ERROR = "error"


class ReviewAssessment(BaseModel):
    """レビュー判定結果。理由リストと tier を保持し、将来フィールドを足しやすい。"""

    tier: ReviewTier = ReviewTier.SAFE
    reasons: list[str] = Field(default_factory=list)
    # 将来: ルール ID、スコア、テンプレート別内訳などを追加可能
    meta: dict[str, Any] = Field(default_factory=dict)

    @property
    def needs_human_review(self) -> bool:
        """人の確認が必要か (初版: NEEDS_REVIEW のみ)。"""
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


def assess_review(
    extracted_data: dict[str, Any],
    template: Template,
    *,
    template_label: str | None = None,
) -> ReviewAssessment:
    """抽出データとテンプレート定義からレビュー tier と理由を返す。

    初版: tier は SAFE または NEEDS_REVIEW のみ。
    """
    prefix = f"[{template_label}] " if template_label else ""
    reasons: list[str] = []
    schema = template.response_schema

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
        if not isinstance(prop, dict):
            continue
        value = extracted_data.get(key)
        if _is_empty_value(value):
            continue
        fmt = prop.get("format")
        if fmt == "date" and not _validate_date_string(value):
            reasons.append(prefix + f"日付形式が不正です: {key}")
        if prop.get("type") == "number" and not _is_numeric_amount(value):
            reasons.append(prefix + f"数値として解釈できません: {key}")

    for key, prop in props.items():
        if not isinstance(prop, dict):
            continue
        if prop.get("type") != "array":
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
    return ReviewAssessment(tier=ReviewTier.SAFE, reasons=[])
