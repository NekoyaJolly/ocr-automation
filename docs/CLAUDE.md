# Claude / エージェント向けメモ

## OCR 推測ポリシー

- **許可**: レベル2（文字形状の類似: O/0 等）とレベル3（フォーマット制約: 和暦→西暦、カンマ欠落、郵便番号ハイフン等）に限り `confidence: inferred` を付与してよい。
- **禁止**: 意味的推測、固有名詞（会社名・人名・商品名）の推測。読めない箇所は `value: null` と適切な `confidence`（多くは `uncertain`）とする。

## Gemini thinking_level

- バックエンドのデフォルトは **`medium`**（環境変数 `BACKEND_GEMINI_THINKING_LEVEL` で `low` / `high` に変更可）。

## レビュー

- `field_placement.required_for_review` が true のフィールドは空・`uncertain` のとき `NEEDS_REVIEW` になりやすい。
- 既存の `review_jobs/*.json` が新しい `Job` 形と合わない場合は読み込みをスキップし警告ログのみ（メインフローは継続）。
