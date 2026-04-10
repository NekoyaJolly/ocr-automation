# OCR Automation Backend — アーキテクチャ設計書

> このドキュメントはバックエンドサービスのアーキテクチャを定義する。

## 1. アーキテクチャ概要

### 1.1 設計原則
- **ステートレス**: API ハンドラはステートを持たず、Cloud Run の自動スケーリングを最大限活用
- **責務最小**: 認証 + 中継 + ログ記録のみ。それ以外の機能は持たない
- **依存性注入**: Firestore クライアント、Gemini クライアント等は DI で注入し、テスタビリティを確保
- **構造化ログ**: 全ての処理を構造化ログで記録、Cloud Logging で検索可能に
- **設定の外部化**: API キー・接続情報は Secret Manager と環境変数経由

### 1.2 全体構造図

```
┌──────────────────────────────────────┐
│   デスクトップアプリ (クライアント)     │
└────────────────┬─────────────────────┘
                 │ HTTPS
                 ▼
┌──────────────────────────────────────┐
│         Cloud Run (FastAPI)          │
│ ┌──────────────────────────────────┐ │
│ │       FastAPI Application        │ │
│ │ ┌────────────────────────────┐  │ │
│ │ │ Routers                    │  │ │
│ │ │  - license_router          │  │ │
│ │ │  - ocr_router              │  │ │
│ │ │  - health_router           │  │ │
│ │ └────────────────────────────┘  │ │
│ │ ┌────────────────────────────┐  │ │
│ │ │ Middleware                 │  │ │
│ │ │  - LicenseAuthMiddleware   │  │ │
│ │ │  - RateLimitMiddleware     │  │ │
│ │ │  - LoggingMiddleware       │  │ │
│ │ └────────────────────────────┘  │ │
│ │ ┌────────────────────────────┐  │ │
│ │ │ Services                   │  │ │
│ │ │  - LicenseService          │  │ │
│ │ │  - GeminiService           │  │ │
│ │ │  - UsageService            │  │ │
│ │ └────────────────────────────┘  │ │
│ │ ┌────────────────────────────┐  │ │
│ │ │ Repositories (Firestore)   │  │ │
│ │ │  - LicenseRepository       │  │ │
│ │ │  - UsageLogRepository      │  │ │
│ │ └────────────────────────────┘  │ │
│ └──────────────────────────────────┘ │
└──────────────────────────────────────┘
       │                  │
       ▼                  ▼
┌─────────────┐   ┌──────────────┐
│  Firestore  │   │  Gemini API  │
└─────────────┘   └──────────────┘
       ▲
       │
┌──────────────┐
│Secret Manager│ (Gemini API キー)
└──────────────┘
```

---

## 2. ディレクトリ構造

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI エントリポイント
│   │
│   ├── routers/                    # API ルーター
│   │   ├── __init__.py
│   │   ├── health.py
│   │   ├── license.py
│   │   └── ocr.py
│   │
│   ├── middleware/                 # ミドルウェア
│   │   ├── __init__.py
│   │   ├── auth.py                 # ライセンスキー認証
│   │   ├── rate_limit.py
│   │   └── logging.py
│   │
│   ├── services/                   # ビジネスロジック
│   │   ├── __init__.py
│   │   ├── license_service.py
│   │   ├── gemini_service.py
│   │   └── usage_service.py
│   │
│   ├── repositories/               # データアクセス層
│   │   ├── __init__.py
│   │   ├── license_repository.py
│   │   └── usage_log_repository.py
│   │
│   ├── models/                     # pydantic モデル
│   │   ├── __init__.py
│   │   ├── license.py
│   │   ├── ocr.py
│   │   └── usage.py
│   │
│   ├── core/                       # 共通基盤
│   │   ├── __init__.py
│   │   ├── config.py               # 環境変数・Secret Manager
│   │   ├── firestore_client.py
│   │   ├── gemini_client.py
│   │   ├── logging_config.py
│   │   └── exceptions.py
│   │
│   └── utils/
│       └── __init__.py
│
├── scripts/                        # 管理スクリプト
│   ├── admin.py                    # ライセンス管理 CLI
│   └── seed_test_data.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
│
├── docker/
│   └── Dockerfile
│
├── deploy/
│   ├── cloudbuild.yaml             # Cloud Build 設定
│   └── service.yaml                # Cloud Run service 定義
│
├── pyproject.toml
├── uv.lock
├── README.md
└── .env.example                    # 環境変数テンプレート
```

**注意**: このディレクトリは OCR Automation のメインリポジトリの **サブディレクトリとして配置するか**、**完全に別リポジトリにするか** を決める必要がある。`backend-CLAUDE.md` で議論。

---

## 3. データフロー

### 3.1 OCR リクエスト処理フロー

```
[1] クライアントから POST /api/v1/ocr/extract
        ↓
[2] LoggingMiddleware: リクエスト受信ログ
        ↓
[3] LicenseAuthMiddleware:
    ├─ X-License-Key ヘッダ取得
    ├─ LicenseService.verify(key) 呼び出し
    ├─ 無効な場合 → 401/403 即返却
    └─ 有効な場合 → request.state にライセンス情報を格納
        ↓
[4] RateLimitMiddleware:
    ├─ ライセンスごとのレート制限チェック
    └─ 超過時 → 429 返却
        ↓
[5] OCR Router (handler):
    ├─ pydantic でリクエスト body バリデーション
    ├─ クオータチェック (LicenseService.check_quota)
    ├─ 超過時 → 403 返却
    └─ GeminiService.extract(image, prompt, schema) 呼び出し
        ↓
[6] GeminiService:
    ├─ google-genai クライアントで gemini-3.1-pro-preview 呼び出し
    ├─ structured output (response_schema) 指定
    ├─ レスポンス受信
    └─ パース + バリデーション
        ↓
[7] UsageService.record(license_id, success, tokens, time)
    └─ Firestore usage_logs に書き込み (非同期)
        ↓
[8] レスポンス返却
```

### 3.2 ライセンス検証フロー

```
[1] クライアントから POST /api/v1/license/verify
        ↓
[2] LicenseService.verify(key)
    ├─ LicenseRepository.find(key)
    ├─ 存在しない → LicenseInvalidError
    ├─ is_active == False → LicenseInvalidError
    ├─ expires_at < now → LicenseExpiredError
    └─ OK → LicenseInfo を返す
        ↓
[3] LicenseInfo に当月利用数を含めて返却
```

---

## 4. 主要モジュール仕様

### 4.1 `app/main.py`

```python
from fastapi import FastAPI
from app.routers import health, license, ocr
from app.middleware.auth import LicenseAuthMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.logging import LoggingMiddleware
from app.core.logging_config import configure_logging

configure_logging()

app = FastAPI(
    title="OCR Automation Backend",
    version="1.0.0",
    docs_url=None,  # 本番では Swagger UI を公開しない
    redoc_url=None,
)

# Middleware (順序重要)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(LicenseAuthMiddleware)

# Routers
app.include_router(health.router)
app.include_router(license.router, prefix="/api/v1/license")
app.include_router(ocr.router, prefix="/api/v1/ocr")
```

### 4.2 `app/middleware/auth.py`

```python
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

EXEMPT_PATHS = {"/health", "/api/v1/license/verify"}  # verify は認証扱いしない

class LicenseAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # ヘルスチェックとライセンス検証エンドポイントは除外
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)
        
        license_key = request.headers.get("X-License-Key")
        if not license_key:
            raise HTTPException(401, "X-License-Key header missing")
        
        license_service = request.app.state.license_service
        try:
            license_info = await license_service.verify(license_key)
        except LicenseInvalidError:
            raise HTTPException(401, "license_invalid")
        except LicenseExpiredError:
            raise HTTPException(403, "license_expired")
        
        request.state.license_info = license_info
        return await call_next(request)
```

### 4.3 `app/services/gemini_service.py`

```python
from google import genai
from google.genai import types

class GeminiService:
    def __init__(self, client: genai.Client, model_name: str):
        self._client = client
        self._model = model_name  # Settings.gemini_model (例: gemini-3.1-pro-preview)

    async def extract(
        self,
        image_base64: str,
        image_mime_type: str,
        extraction_prompt: str,
        response_schema: dict,
    ) -> ExtractResult:
        image_part = types.Part.from_bytes(
            data=base64.b64decode(image_base64),
            mime_type=image_mime_type,
        )
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            thinking_config=types.ThinkingConfig(thinking_level="low"),
            temperature=0.0,
        )
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=[image_part, extraction_prompt],
            config=config,
        )
        return ExtractResult(..., model_used=self._model)
```

### 4.4 `app/repositories/license_repository.py`

```python
from google.cloud import firestore

class LicenseRepository:
    COLLECTION = "licenses"
    
    def __init__(self, db: firestore.AsyncClient):
        self._db = db
    
    async def find(self, license_key: str) -> LicenseDocument | None:
        doc_ref = self._db.collection(self.COLLECTION).document(license_key)
        snapshot = await doc_ref.get()
        if not snapshot.exists:
            return None
        return LicenseDocument(**snapshot.to_dict(), id=snapshot.id)
    
    async def increment_usage(self, license_key: str, current_period: str) -> None:
        doc_ref = self._db.collection(self.COLLECTION).document(license_key)
        # 月が変わっていればリセット、同じならインクリメント
        @firestore.async_transactional
        async def update_in_tx(tx, doc_ref):
            snapshot = await doc_ref.get(transaction=tx)
            data = snapshot.to_dict()
            if data.get("current_month_period") != current_period:
                tx.update(doc_ref, {
                    "current_month_period": current_period,
                    "current_month_usage": 1,
                })
            else:
                tx.update(doc_ref, {
                    "current_month_usage": firestore.Increment(1),
                })
        
        await update_in_tx(self._db.transaction(), doc_ref)
```

### 4.5 `app/core/config.py`

```python
from pydantic_settings import BaseSettings
from google.cloud import secretmanager

class Settings(BaseSettings):
    project_id: str
    firestore_database: str = "(default)"
    gemini_api_key_secret_name: str = "gemini-api-key"
    gemini_model: str = "gemini-3.1-pro-preview"  # BACKEND_GEMINI_MODEL で上書き
    log_level: str = "INFO"
    rate_limit_per_minute: int = 60
    
    class Config:
        env_file = ".env"
        env_prefix = "BACKEND_"

def load_secret(secret_name: str, project_id: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")
```

---

## 5. データモデル

### 5.1 `app/models/license.py`

```python
class LicenseDocument(BaseModel):
    """Firestore に保存されるライセンスドキュメント"""
    id: str  # ライセンスキー
    company_name: str
    contact_email: str
    is_active: bool = True
    created_at: datetime
    expires_at: datetime
    monthly_quota: int = 1000
    current_month_usage: int = 0
    current_month_period: str  # "2026-04" 形式
    notes: str = ""

class LicenseInfo(BaseModel):
    """API レスポンス用"""
    is_valid: bool
    company_name: str
    expires_at: datetime
    monthly_quota: int
    used_this_month: int
    last_verified_at: datetime
```

### 5.2 `app/models/ocr.py`

```python
class OCRExtractRequest(BaseModel):
    image_base64: str
    image_mime_type: Literal["image/jpeg", "image/png", "image/webp", "application/pdf"]
    extraction_prompt: str
    response_schema: dict

class OCRExtractResponse(BaseModel):
    data: dict
    processing_time_ms: int
    model_used: str
```

### 5.3 `app/models/usage.py`

```python
class UsageLogEntry(BaseModel):
    license_id: str
    timestamp: datetime
    endpoint: str
    status: Literal["success", "failure"]
    processing_time_ms: int
    gemini_input_tokens: int = 0
    gemini_output_tokens: int = 0
    error_type: str | None = None
```

---

## 6. デプロイメント

### 6.1 Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# uv のインストール
RUN pip install uv

# 依存関係のインストール
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# アプリケーションコード
COPY app ./app

# Cloud Run は PORT 環境変数を渡してくる
ENV PORT=8080
EXPOSE 8080

CMD uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### 6.2 Cloud Run デプロイ設定

```yaml
# deploy/service.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: ocr-automation-backend
  annotations:
    run.googleapis.com/launch-stage: GA
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "0"
        autoscaling.knative.dev/maxScale: "10"
        run.googleapis.com/cpu-throttling: "true"
    spec:
      timeoutSeconds: 120
      containerConcurrency: 20
      containers:
        - image: asia-northeast1-docker.pkg.dev/PROJECT_ID/ocr-automation/backend:latest
          resources:
            limits:
              cpu: "1"
              memory: "512Mi"
          env:
            - name: BACKEND_PROJECT_ID
              value: PROJECT_ID
            - name: BACKEND_LOG_LEVEL
              value: INFO
          ports:
            - containerPort: 8080
```

### 6.3 環境変数とシークレット

| 変数 | 用途 | 取得方法 |
|------|------|---------|
| `BACKEND_PROJECT_ID` | GCP プロジェクト ID | 環境変数 |
| `BACKEND_LOG_LEVEL` | ログレベル | 環境変数 |
| Gemini API キー | Gemini 呼び出し | Secret Manager |
| Firestore 認証 | DB アクセス | Cloud Run のサービスアカウント |

---

## 7. テスト戦略

### 7.1 ユニットテスト
- Service 層: Repository をモックして純粋なロジックをテスト
- Repository 層: Firestore エミュレータを使ったテスト
- Middleware: TestClient で各種シナリオをテスト

### 7.2 統合テスト
- ローカル Firestore エミュレータ + モック Gemini クライアントで E2E
- 実際の Gemini API を叩くテストは別途、コスト管理しながら手動実行

### 7.3 ローカル開発
```bash
# Firestore エミュレータ起動
gcloud emulators firestore start --host-port=localhost:8200

# 環境変数で接続先を指定
export FIRESTORE_EMULATOR_HOST=localhost:8200

# アプリ起動
uv run uvicorn app.main:app --reload
```

---

## 8. セキュリティ詳細

### 8.1 ライセンスキーの保護
- Firestore 内では平文保存だが、Firestore はバックエンド (サービスアカウント経由) からのみアクセス可能
- Firestore セキュリティルール: 直接アクセス全拒否
- ログにはライセンスキーの一部 (先頭8文字) のみ記録、または SHA256 ハッシュ

### 8.2 Gemini API キーの保護
- Secret Manager に保存
- Cloud Run のサービスアカウントに `roles/secretmanager.secretAccessor` 付与
- アプリ起動時に1回だけロードしてメモリ内保持

### 8.3 入力検証
- リクエストボディは pydantic で必ずバリデーション
- 画像サイズ上限: 10MB (Cloud Run の 32MB 制限より小さく設定)
- `extraction_prompt` の最大文字数: 5000 文字
- `response_schema` のネスト深さ制限: 5 段階まで

### 8.4 レート制限
- アプリ内で簡易レートリミッター実装 (Redis 不要、メモリベース)
- インスタンスごとの状態なので厳密ではないが、Cloud Run の最大インスタンス 10 を考慮すれば十分
- 厳密に制御したい場合は Cloud Memorystore (Redis) を追加検討

---

## 9. 監視

### 9.1 Cloud Logging
- 全リクエストを構造化ログで記録
- ラベルでフィルタリング: `severity`, `license_id_hash`, `endpoint`, `status_code`

### 9.2 Cloud Monitoring (オプション)
- リクエスト数、エラー率、レイテンシのダッシュボード
- アラート: エラー率 > 5%、レイテンシ > 30秒

### 9.3 利用統計
- Firestore `usage_logs` を BigQuery にエクスポート (将来)
- 月次レポート: ライセンスごとの利用数

---

## 10. 運用シナリオ

### 10.1 新規ライセンス発行
```bash
# Neko がローカルから実行
uv run python scripts/admin.py create-license \
  --company "株式会社サンプル" \
  --email "admin@sample.co.jp" \
  --quota 1000 \
  --expires "2027-04-10"

# 出力: ライセンスキー OCRA-XXXX-XXXX-...
```

### 10.2 ライセンス停止
```bash
uv run python scripts/admin.py disable-license OCRA-XXXX-XXXX-...
```

### 10.3 利用状況確認
```bash
uv run python scripts/admin.py show-usage --license OCRA-XXXX-XXXX-...
```

### 10.4 デプロイ
```bash
# Cloud Build でビルド + デプロイ
gcloud builds submit --config deploy/cloudbuild.yaml
```

---

## 11. 将来の拡張ポイント

実装しないが、将来の選択肢として頭の片隅に置いておく:

- **Stripe 連携**: 自動課金、ライセンスの月額契約化
- **管理 Web UI**: Admin CLI を Web 化
- **Webhook 通知**: ライセンス quota 80% 到達時にメール通知
- **複数 LLM 対応**: Gemini の他に Claude/GPT も選択可能に
- **画像前処理パイプライン**: 傾き補正・ノイズ除去をバックエンドで実施
- **キャッシュ**: 同一画像の重複処理時にキャッシュから返す
