"""業種別プロンプトプリセット (role / context)。"""

from __future__ import annotations

from typing import TypedDict


class IndustryPreset(TypedDict):
    role: str
    context: str


INDUSTRY_PRESETS: dict[str, IndustryPreset] = {
    "general": {
        "role": "あなたは日本の事務業務に詳しいアシスタントです。",
        "context": "",
    },
    "construction": {
        "role": "あなたは日本の建設業の経理実務に詳しいアシスタントです。",
        "context": (
            "明細には「㎡」「m³」「kg」などの単位が含まれることがあります。"
            "単位は画像に記載されたとおりに読み取ってください。"
        ),
    },
    "restaurant": {
        "role": "あなたは日本の飲食店の事務・仕入れ伝票処理に詳しいアシスタントです。",
        "context": "食材名・数量・単価が行ごとに並ぶ形式が多いです。",
    },
    "retail": {
        "role": "あなたは日本の小売・卸の伝票処理に詳しいアシスタントです。",
        "context": "品番・JAN・数量・単価の列形式が一般的です。",
    },
    "manufacturing": {
        "role": "あなたは日本の製造業の購買・納品書処理に詳しいアシスタントです。",
        "context": "品目コード・ロット・数量単位に注意してください。",
    },
}


def get_industry_preset(key: str | None) -> IndustryPreset:
    """プリセットキーを解決する。未設定・未知キーは general。"""
    if not key or key not in INDUSTRY_PRESETS:
        return INDUSTRY_PRESETS["general"]
    return INDUSTRY_PRESETS[key]
