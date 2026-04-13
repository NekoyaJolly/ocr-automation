"""テンプレートから Gemini 向け抽出プロンプトを組み立てる。"""

from __future__ import annotations

from app.core.industry_presets import get_industry_preset
from app.models.template_model import Template


def build_extraction_prompt(template: Template) -> str:
    """役割・抽出ルール・推測ポリシー・出力形式・ユーザー指示を結合する。"""
    preset_key = template.industry_preset
    preset = get_industry_preset(preset_key)
    role = preset["role"]
    preset_ctx = (preset["context"] or "").strip()
    industry_extra = (template.industry_context or "").strip()

    blocks: list[str] = []

    blocks.append("# 役割\n")
    blocks.append(role + "\n")

    blocks.append("\n# 抽出対象フィールド\n")
    blocks.append("以下のフィールドを画像から読み取り、指定の JSON 形式で返してください。\n")
    for fp in template.field_placements:
        label = fp.display_name or fp.source_key
        req = " (レビュー上必須)" if fp.required_for_review else ""
        blocks.append(f"- `{fp.source_key}` {label} {req}\n")

    if preset_ctx:
        blocks.append("\n# 業種コンテキスト (プリセット)\n")
        blocks.append(preset_ctx + "\n")
    if industry_extra:
        blocks.append("\n# 業種・案件の補足指示\n")
        blocks.append(industry_extra + "\n")

    user_block = (
        template.custom_extraction_instructions.strip()
        or template.extraction_prompt.strip()
    )
    if user_block:
        blocks.append("\n# ユーザー固有の追加指示\n")
        blocks.append(user_block + "\n")

    blocks.append(
        """

# 推測ルール

基本原則: 画像から確実に読み取れた値のみを返してください。

ただし、以下のケースでは限定的に推測を許可します:

1. 文字形状の類似による判別 (confidence: "inferred")
   - 数字欄で「O」→「0」、「l」→「1」、「B」→「8」として扱う
   - 読み取りの確信度が低い場合は confidence: "uncertain"

2. フォーマット制約による補完 (confidence: "inferred")
   - 日付欄で「R3.3.29」「令3.3.29」等は和暦・略号を西暦 YYYY-MM-DD に変換
   - 金額欄のカンマ欠落を数値として補完
   - 郵便番号のハイフン欠落を補完

## 推測が許されないケース

以下は value を null とし、適切な confidence を付けてください:
- 会社名、人名、商品名などの固有名詞の推測
- 完全に読み取れない文字 (掠れ、塗りつぶし、切れた文字)
- 複数の解釈が成立する曖昧な文字 (意味的推測)

## 各フィールドの出力

各トップレベルフィールドはオブジェクトで、次のキーを持ちます:
- value: 抽出された値 (または null)
- confidence: "certain" (確実) / "inferred" (上記に基づく推測) / "uncertain" (不確か)
- inference_reason: inferred / uncertain のとき簡潔な理由。それ以外は null 可

配列フィールド (例: 明細) の各要素も、同様に各サブフィールドを
{value, confidence, inference_reason} で返してください。
"""
    )

    blocks.append(
        "\n# ドキュメント説明 (参考)\n"
        f"{template.name}: {template.description}\n"
    )

    return "".join(blocks).strip() + "\n"
