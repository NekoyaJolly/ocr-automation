# OCR Automation

手書き画像から OCR + 構造化抽出を行い、テンプレートに沿った複数フォーマットで自動出力・自動印刷するデスクトップアプリケーション。

## セットアップ

```bash
# 依存のインストール
uv sync

# 開発用依存を含む
uv sync --extra dev

# アプリの起動
uv run python -m app

# テストの実行
uv run pytest tests/

# リンター
uv run ruff check app/
uv run ruff format app/
```

## データの保存場所

アプリは設定・ログなどを OS のアプリデータ配下（Windows では `%APPDATA%\OCRAutomation\`）に保存します。承認・却下したレビューは `review_history\YYYY-MM\<job_id>.json` に履歴として残ります。履歴は自動削除されないため、ディスクを空けたい場合は **必要に応じて `review_history` フォルダごと手動で削除** して構いません。

## 技術スタック

- **言語**: Python 3.12
- **GUI**: PySide6 (Qt6)
- **OCR**: Google Gemini 3 Pro (バックエンド経由)
- **依存管理**: uv
- **パッケージング**: PyInstaller

## ディレクトリ構成

```
ocr-automation/
├── app/              # デスクトップアプリ
│   ├── gui/          # GUI 層 (PySide6)
│   ├── controllers/  # アプリケーション層
│   ├── core/         # コア層 (ビジネスロジック)
│   ├── models/       # データモデル (pydantic)
│   └── infrastructure/  # インフラ層
├── backend/          # バックエンド (FastAPI + Cloud Run)
├── templates/        # テンプレート YAML
├── template_sets/    # テンプレートセット YAML
└── tests/            # テスト
```
