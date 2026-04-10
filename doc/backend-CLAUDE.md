# backend-CLAUDE.md — OCR Automation Backend 開発方針

このドキュメントは Cursor / Claude Code がバックエンドサービスを開発する際に遵守すべき方針を定義する。デスクトップアプリの開発方針は親ディレクトリの `CLAUDE.md` を参照。

## 1. プロジェクトの本質

このバックエンドは、OCR Automation デスクトップアプリのための **Gemini API 中継サービス**。責務は3つだけ:

1. **認証** — ライセンスキーで誰がアクセスしているかを検証
2. **中継** — 画像とプロンプトを受け取って Gemini に渡し、結果を返す
3. **計測** — 利用量を記録、quota とレート制限を実施

それ以外の機能は持たない。**シンプルさが最大の価値**。

詳細は `backend-requirements.md` と `backend-architecture.md` を参照。実装前に必ず両方を読むこと。

---

## 2. 絶対遵守ルール

### 2.1 技術スタック固定

- **言語**: Python 3.12
- **フレームワーク**: FastAPI
- **ASGI サーバー**: uvicorn
- **データバリデーション**: pydantic v2
- **インフラ**: GCP Cloud Run
- **データベース**: Cloud Firestore (Native mode)
- **シークレット**: GCP Secret Manager
- **LLM**: Google Gemini 3.1 Pro Preview (`google-genai` SDK、モデル ID 例: `gemini-3.1-pro-preview`)
- **ロギング**: structlog → Cloud Logging
- **依存管理**: uv

別ライブラリへの置き換えを提案したい場合は、必ずユーザーに相談。

### 2.2 アーキテクチャ境界の保持

層構造を厳守:

```
Routers → Middleware → Services → Repositories → External (Firestore / Gemini)
```

- Router は HTTP の入り口、Service にロジックを委譲する
- Service はビジネスロジック、Repository を通じてデータアクセス
- Repository は Firestore とのやり取りに専念、ビジネスロジックを持たない
- Service と Service の循環依存を作らない

### 2.3 機密情報の取り扱い (CRITICAL)

**以下は絶対に守ること:**

1. **Gemini API キー、Firestore 認証情報、その他の機密情報を絶対にコードにハードコードしない**
2. **`.env` ファイルや秘密情報を Git にコミットしない** (`.gitignore` に必ず追加)
3. **ログに API キー、ライセンスキー全文、画像内容を出力しない**
   - ライセンスキーをログに出す場合は先頭8文字 + ハッシュのみ
   - 画像の base64 はログに出さない
4. **本番環境の設定を開発環境と混在させない**
5. **Swagger UI を本番で公開しない** (`docs_url=None, redoc_url=None`)

### 2.4 デスクトップアプリ側との分離

- このバックエンドは独立したサービス
- デスクトップアプリ側のコード (`app/` 配下) を参照したり import したりしない
- API スキーマ (リクエスト/レスポンス) はこのリポジトリ内で完結
- デスクトップアプリ側の設計が変わっても、API の後方互換性を保つ

### 2.5 本番デプロイ前のチェックリスト

実装完了でも、本番デプロイ前に必ず以下を確認:

- [ ] `.env` が `.gitignore` に含まれているか
- [ ] Swagger UI が無効化されているか
- [ ] Gemini API キーが Secret Manager 経由か
- [ ] Firestore セキュリティルールがデフォルト拒否設定か
- [ ] ヘルスチェックエンドポイントが認証なしで通るか
- [ ] エラーレスポンスにスタックトレースや内部情報が漏れていないか
- [ ] ログにライセンスキー全文が出力されていないか
- [ ] レート制限が動作するか

---

## 3. 開発フェーズ

`backend-requirements.md` セクション 7 を参照。Phase B-1 から B-6 の順に進む。

| Phase | 内容 | 完了条件 |
|-------|------|---------|
| B-1 | スケルトン構築 | `/health` がローカルと Cloud Run で 200 を返す |
| B-2 | 認証層 | `/api/v1/license/verify` が動作する |
| B-3 | OCR 中継 | `/api/v1/ocr/extract` が Gemini を呼び出して結果を返す |
| B-4 | 利用量管理 | quota チェックとレート制限が動作する |
| B-5 | 運用準備 | 管理 CLI、構造化ログ、本番デプロイ |
| B-6 | 統合テスト | デスクトップアプリと結合確認 |

各 Phase の終了時に必ず動作確認を行い、ユーザーに完了報告すること。

---

## 4. コーディング規約

### 4.1 スタイル
- フォーマッタ: ruff format
- リンタ: ruff check
- 型ヒント: 必須(全関数に引数・戻り値の型)
- 型チェッカー: mypy (strict 推奨)

### 4.2 FastAPI 特有の慣習
- ルーター内のハンドラは `async def` を使う (Firestore も Gemini も非同期 SDK あり)
- 依存性注入は `Depends()` を活用
- リクエスト/レスポンスは必ず pydantic モデルで型付け
- HTTP エラーは `HTTPException` を投げる、自前で JSON 整形しない
- バックグラウンドタスク (`BackgroundTasks`) を使う際は、Cloud Run のリクエストライフサイクルを意識する (リクエスト終了後にコンテナが落ちる可能性)

### 4.3 非同期処理の注意
- Firestore Python SDK には同期版と非同期版がある — **必ず非同期版 (`google.cloud.firestore.AsyncClient`) を使う**
- Gemini SDK も `client.aio` の非同期 API を使う
- 同期 I/O を async ハンドラ内で呼ぶと性能が劣化する

### 4.4 docstring
全てのパブリック関数・クラスに Google スタイルの docstring を書くこと。

### 4.5 エラーハンドリング
- カスタム例外を `app/core/exceptions.py` に定義
- ミドルウェアで例外をキャッチして HTTP レスポンスに変換
- ログには必ず例外の trace を含める (`logger.exception()`)
- ユーザー (= デスクトップアプリ) 向けエラーメッセージは英語の error code + 人間向けメッセージ (英語)
  - 日本語化はクライアント側で行う

```python
# 例
{
  "error": "license_expired",
  "message": "License key has expired",
  "expires_at": "2026-01-01T00:00:00Z"
}
```

---

## 5. テスト方針

### 5.1 必須テスト
- Service 層の主要メソッドはユニットテスト必須
- Repository 層は Firestore エミュレータを使ったテスト
- ミドルウェアは TestClient で各種シナリオをテスト
- Gemini 呼び出しはモック (実際の API は CI で叩かない)

### 5.2 ローカル開発環境
```bash
# Firestore エミュレータ起動
gcloud emulators firestore start --host-port=localhost:8200

# 別ターミナルで環境変数設定
export FIRESTORE_EMULATOR_HOST=localhost:8200
export BACKEND_PROJECT_ID=ocr-automation-dev

# テストデータ投入
uv run python scripts/seed_test_data.py

# アプリ起動
uv run uvicorn app.main:app --reload --port 8080
```

### 5.3 統合テスト
- ローカル Firestore エミュレータ + モック Gemini で E2E
- 実 Gemini を叩くテストは別途、コスト管理しながら手動で

---

## 6. Git コミット規約

### 6.1 コミット粒度
- 1 コミット = 1 論理的変更
- Phase B-1 から B-6 までを最低 15 コミット程度に分割すること

### 6.2 推奨コミット分割例

**Phase B-1 (スケルトン)**
1. `chore: バックエンドプロジェクト初期化 (uv, pyproject.toml)`
2. `feat: FastAPI スケルトンと /health エンドポイント`
3. `feat: Dockerfile と Cloud Run デプロイ設定`
4. `feat: 構造化ログ (structlog) のセットアップ`

**Phase B-2 (認証)**
5. `feat: LicenseDocument モデルと LicenseRepository`
6. `feat: LicenseService と /api/v1/license/verify`
7. `feat: LicenseAuthMiddleware`
8. `test: ライセンス検証のユニットテスト`

**Phase B-3 (OCR 中継)**
9. `feat: GeminiService の実装`
10. `feat: /api/v1/ocr/extract エンドポイント`
11. `test: モック Gemini で OCR エンドポイントテスト`

**Phase B-4 (利用量管理)**
12. `feat: UsageLogRepository と UsageService`
13. `feat: monthly quota チェックの実装`
14. `feat: RateLimitMiddleware`

**Phase B-5 (運用準備)**
15. `feat: scripts/admin.py (ライセンス管理 CLI)`
16. `docs: README とデプロイ手順`
17. `chore: 本番デプロイ用 cloudbuild.yaml`

### 6.3 メッセージ形式
```
<type>: <短い説明>
```

type: `feat` / `fix` / `refactor` / `docs` / `test` / `chore` / `build`

---

## 7. 禁止事項

絶対にやらないこと:

1. **API キーやシークレットをコードにハードコード**
2. **`.env` ファイルや認証情報を Git にコミット**
3. **ログにライセンスキー全文・画像 base64・PII を出力**
4. **Swagger UI を本番で公開**
5. **Firestore に画像を保存** (バックエンドはステートレス、画像はメモリ内のみ)
6. **同期 SDK を async ハンドラ内で使用** (パフォーマンス劣化)
7. **管理 API を公開エンドポイントとして実装** (CLI のみ)
8. **デスクトップアプリ側のコードを import**
9. **テストなしのコア機能追加**
10. **依存ライブラリの勝手な追加** (新規依存追加時はユーザー承認必須)

---

## 8. リポジトリ配置戦略

このバックエンドは2つの配置パターンが考えられる:

### パターン A: モノレポ (1リポジトリに統合)
```
ocr-automation/
├── app/                  # デスクトップアプリ
├── backend/              # バックエンド
└── docs/
```

メリット: 1つのリポジトリで全部管理、ドキュメント連携が容易
デメリット: CI が複雑化、デプロイトリガーが混在

### パターン B: 別リポジトリ
- `ocr-automation` (デスクトップアプリ)
- `ocr-automation-backend` (バックエンド)

メリット: 明確に分離、CI/デプロイがシンプル、権限管理がしやすい
デメリット: ドキュメント連携に手間

**推奨**: 初期はパターン A (モノレポ) で始め、運用が安定してから必要に応じてパターン B に分割する。

実装開始前にユーザーと確認すること。

---

## 9. 質問していい場面・自走していい場面

### 9.1 質問すべき場面
- API スキーマの仕様判断 (フィールド追加・削除)
- 新規依存ライブラリを追加したい時
- セキュリティに関わる判断 (認証・暗号化方式の変更等)
- リポジトリ配置 (モノレポ vs 別リポジトリ)
- 本番デプロイ前のチェックで気になる点

### 9.2 自走していい場面
- ドキュメントに記載済みの内容を実装する時
- バグ修正・リファクタリング (既存の振る舞いを変えない範囲)
- テスト追加
- ドキュメント補完

---

## 10. 参照ドキュメント

- `backend-requirements.md` — 機能要件・非機能要件
- `backend-architecture.md` — アーキテクチャ・モジュール仕様
- 親ディレクトリの `requirements.md` / `architecture.md` — デスクトップアプリ側の設計 (必要に応じて参照)
- FastAPI 公式: <https://fastapi.tiangolo.com/>
- Google Gen AI Python SDK: <https://github.com/googleapis/python-genai>
- google-cloud-firestore: <https://cloud.google.com/python/docs/reference/firestore/latest>
- Cloud Run 公式: <https://cloud.google.com/run/docs>
- pydantic v2: <https://docs.pydantic.dev/latest/>

---

## 11. コアバリューとの接続

このバックエンドは独立したサービスだが、最終的にはデスクトップアプリのコアバリュー「**入り口と出口だけが人間、間は全部自動**」を支える存在。バックエンドが落ちていたり遅かったりすると、デスクトップアプリの「自動処理」が止まる。

つまりバックエンドの非機能要件 (可用性・レイテンシ・エラー処理) は、デスクトップアプリのコアバリューを守るためにある。実装中に判断に迷ったら、「これは自動処理を止めずに済む実装か?」を問い直すこと。

---

## 12. このドキュメントの更新

このドキュメントの内容に変更が必要な場合、勝手に編集せず必ずユーザーに提案すること。
