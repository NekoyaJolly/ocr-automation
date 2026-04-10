# OCR Automation Backend

OCR Automation デスクトップアプリのための Gemini API 中継サービス。

## セットアップ

```bash
cd backend

# 依存のインストール
uv sync --extra dev

# 環境変数の設定
cp .env.example .env
# .env を編集

# Firestore エミュレータ起動 (別ターミナル)
gcloud emulators firestore start --host-port=localhost:8200

# テストデータ投入
FIRESTORE_EMULATOR_HOST=localhost:8200 uv run python scripts/seed_test_data.py

# アプリ起動
FIRESTORE_EMULATOR_HOST=localhost:8200 uv run uvicorn app.main:app --reload --port 8080

# テスト
FIRESTORE_EMULATOR_HOST=localhost:8200 uv run pytest tests/ -v
```

## API エンドポイント

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/health` | ヘルスチェック |
| POST | `/api/v1/license/verify` | ライセンス検証 |
| POST | `/api/v1/ocr/extract` | OCR + 構造化抽出 |

## ライセンス管理 CLI

```bash
# 新規ライセンス作成
uv run python scripts/admin.py create-license --company "株式会社サンプル" --quota 1000 --expires "2027-04-10"

# ライセンス無効化
uv run python scripts/admin.py disable-license OCRA-XXXX-...

# 利用状況確認
uv run python scripts/admin.py show-usage --license OCRA-XXXX-...

# 一覧表示
uv run python scripts/admin.py list
```

## デプロイ

```bash
gcloud builds submit --config deploy/cloudbuild.yaml
```
