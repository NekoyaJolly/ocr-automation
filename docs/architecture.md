# OCR Automation アーキテクチャメモ

## 6.1 テンプレートと OCR 抽出 (2026-04 更新)

### Template モデル

- **業種**: `industry_preset`（`general` / `construction` 等）と任意の `industry_context` でロール・文脈を切り替える。
- **ユーザー指示**: `custom_extraction_instructions` が主。YAML の旧キー `extraction_prompt` は読み込み時に同フィールドへ移行する。
- **抽出プロンプト**: 実行時に `app/core/prompt_builder.py` の `build_extraction_prompt()` が、役割・フィールド一覧・推測ポリシー・JSON 形式・ユーザー指示を結合して生成する。GUI の `extraction_prompt` フィールドは後方互換用にモデル内で `custom_extraction_instructions` と同期する。
- **response_schema**: Gemini 向け JSON Schema。各論理フィールドは `{ value, confidence, inference_reason }` のオブジェクトで返す形に統一できる（配列の要素も同様にネスト可能）。

### 業種プリセット

- `app/core/industry_presets.py` の `INDUSTRY_PRESETS` が `role` / `context` を提供する。`general` のみ詳細、その他は運用で拡張する想定。

### confidence 付きレスポンス

- バックエンドは Gemini の JSON をそのまま `data` で返す。
- デスクトップの `flatten_gemini_extracted()` がプレーンな `extracted_data`（出力・ファイル名用）と `field_confidences`（レビュー判定用）に分離する。
- ラッパが無い旧レスポンスは全フィールド `certain` として扱う。

### レビュー tier

- `assess_review()` は `SAFE` / `WARNING` / `NEEDS_REVIEW` を返す。
- `NEEDS_REVIEW` のときのみレビューキューへ。`WARNING` はログ用途で自動出力のまま通過可能（形状・フォーマット推測のみの場合）。
