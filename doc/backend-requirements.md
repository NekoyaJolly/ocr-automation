# OCR Automation Backend — 要件定義書

> このドキュメントは OCR Automation プロジェクトのバックエンドサービスの要件を定義する。デスクトップアプリ側の要件は `docs/requirements.md` を参照。

## 1. プロジェクト概要

### 1.1 目的
デスクトップアプリ (OCR Automation) からの画像 OCR + 構造化抽出リクエストを受け付け、Google Gemini API を呼び出して結果を返す中継サービス。ライセンスキー認証と利用量管理を担当する。

### 1.2 役割
- **API キーの守護**: Gemini API キーをサーバー側に保管し、クライアントに渡さない
- **認証**: ライセンスキーによるアクセス制御
- **中継**: 画像 + プロンプトを受け取り、Gemini API を呼び出して結果を返す
- **管理**: 利用ログの記録、月間利用量の管理、レート制限

### 1.3 設計思想
- **ステートレスな処理層**: API ロジックは Cloud Run のステートレスコンテナで動かす
- **Firestore でステート保管**: ライセンス情報・利用ログのみ Firestore に保存
- **最小限の責務**: 認証と中継以外の機能は持たない (画像保管などはしない)
- **低コスト運用**: 30 社規模なら月数ドル以内、Google AI Ultra クレジット内で完結

---

## 2. 機能要件

### 2.1 API エンドポイント

#### B-01: ライセンス検証
```
POST /api/v1/license/verify
Headers:
  X-License-Key: <license_key>

Response (200):
{
  "is_valid": true,
  "company_name": "株式会社サンプル",
  "expires_at": "2027-04-10T00:00:00Z",
  "monthly_quota": 1000,
  "used_this_month": 47,
  "last_verified_at": "2026-04-10T12:34:56Z"
}

Response (401):
{
  "error": "license_invalid",
  "message": "ライセンスキーが無効です"
}

Response (403):
{
  "error": "license_expired",
  "message": "ライセンスキーの有効期限が切れています"
}
```

#### B-02: OCR + 構造化抽出
```
POST /api/v1/ocr/extract
Headers:
  X-License-Key: <license_key>
  Content-Type: application/json

Request body:
{
  "image_base64": "...",
  "image_mime_type": "image/jpeg",
  "extraction_prompt": "この納品書から請求書番号と...",
  "response_schema": {
    "type": "object",
    "properties": { ... }
  }
}

Response (200):
{
  "data": {
    "invoice_no": "INV-2026-001",
    "issue_date": "2026-04-10",
    "customer_name": "田中商事",
    "items": [...],
    "total_amount": 12500
  },
  "processing_time_ms": 3421,
  "model_used": "gemini-3.1-pro-preview"
}

Response (401): ライセンス認証失敗
Response (403): ライセンス期限切れ or quota 超過
Response (429): レート制限
Response (500): Gemini API エラー or 内部エラー
```

#### B-03: ヘルスチェック
```
GET /health

Response (200):
{
  "status": "ok",
  "timestamp": "2026-04-10T12:34:56Z"
}
```

### 2.2 認証・認可

#### B-10: ライセンスキー方式
- 全てのリクエスト (ヘルスチェック除く) は `X-License-Key` ヘッダに有効なライセンスキーを含む必要がある
- ライセンスキーは Firestore の `licenses` コレクションで管理
- キーが存在しない、無効、期限切れ、quota 超過の場合はリクエスト拒否

#### B-11: ライセンスキー形式
- UUID v4 ベース、または UUID + チェックサム
- 例: `OCRA-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX`
- 推測困難であれば形式は問わない

### 2.3 利用量管理

#### B-20: クオータ管理
- 各ライセンスに `monthly_quota` (月間処理可能枚数) を設定
- リクエストごとに `usage_logs` コレクションに記録
- リクエスト処理前にカレント月の利用数をチェック、超過時は 403 返却
- 月初(JST)に自動リセット (リセットは Cloud Scheduler で実装、または都度集計)

#### B-21: レート制限
- 各ライセンスにつき秒間 5 リクエスト、分間 60 リクエストを上限とする
- 超過時は HTTP 429 を返す
- 実装は Cloud Run の組み込み機能 or アプリ内の簡易レートリミッター

### 2.4 ロギング

#### B-30: 構造化ログ
- 全てのリクエストを Cloud Logging に出力
- ログ項目: timestamp, license_key (ハッシュ化), endpoint, status_code, processing_time, gemini_tokens_used, error_type
- 個人情報・画像内容はログに出力しない

#### B-31: 利用ログ (Firestore)
- 課金準備のため、`usage_logs` コレクションに以下を記録
  - license_key_id (Firestore ドキュメント ID)
  - timestamp
  - endpoint
  - success / failure
  - processing_time_ms
  - gemini_input_tokens
  - gemini_output_tokens

### 2.5 管理機能 (オプション)

#### B-40: 管理 CLI
- ライセンス追加・更新・無効化を CLI で行える
- 実装は別途 `scripts/admin.py` などのローカルスクリプトで OK
- 公開エンドポイントとしての管理 API は **作らない**(セキュリティリスク回避)

---

## 3. 非機能要件

### 3.1 パフォーマンス
- ライセンス検証: 200ms 以内
- OCR + 抽出: Gemini の応答時間に依存 (通常 3〜10秒)
- バックエンド固有の処理オーバーヘッド: 500ms 以内

### 3.2 可用性
- Cloud Run の SLO に依存 (99.95% 程度)
- マルチリージョン展開は不要 (asia-northeast1 のみ)
- ダウン時の挙動: クライアントは失敗フォルダに画像を退避 (デスクトップアプリ側で対応済み)

### 3.3 スケーラビリティ
- 30 社規模での想定リクエスト数: 月 6000〜10000 リクエスト
- ピーク時想定: 同時 10 リクエスト程度
- Cloud Run の自動スケーリングで対応 (最小インスタンス 0、最大 10)

### 3.4 セキュリティ
- 全通信 HTTPS のみ
- Gemini API キーは Secret Manager に保管
- Firestore のセキュリティルール: バックエンドからのみアクセス可能
- リクエストボディ (画像) は処理後に即破棄、ログに保存しない
- ライセンスキーはログ内ではハッシュ化

### 3.5 コスト
- Cloud Run: 実行時間ベース、30 社規模で月数ドル以内
- Firestore: 無料枠内 (1日 5万読み取り、2万書き込み) で完結
- Gemini API: Google AI Ultra の $100/月 GCP クレジットを充当
- ドメイン: 年 $10〜15
- **目標: 月額 $10 以内**

---

## 4. 技術スタック

### 4.1 ランタイム
- 言語: Python 3.12
- フレームワーク: FastAPI
- ASGI サーバー: uvicorn (Cloud Run 内)
- 依存管理: uv

### 4.2 主要ライブラリ
| 用途 | ライブラリ |
|------|-----------|
| Web フレームワーク | FastAPI |
| ASGI サーバー | uvicorn |
| データバリデーション | pydantic v2 |
| Firestore クライアント | google-cloud-firestore |
| Gemini API クライアント | google-genai |
| Secret Manager クライアント | google-cloud-secret-manager |
| 構造化ログ | structlog |
| HTTP テスト | httpx + pytest |

### 4.3 GCP サービス
- **Cloud Run**: API 実行環境
- **Cloud Firestore**: ライセンス・利用ログのデータベース
- **Secret Manager**: Gemini API キー保管
- **Cloud Logging**: 構造化ログ
- **Cloud Scheduler** (オプション): 月次クオータリセット
- **Artifact Registry**: コンテナイメージ保管

---

## 5. データモデル

### 5.1 Firestore コレクション

#### `licenses` コレクション
```javascript
{
  // ドキュメント ID = ライセンスキー (またはハッシュ)
  "id": "OCRA-XXXX-XXXX-XXXX-XXXX",
  
  "company_name": "株式会社サンプル",
  "contact_email": "admin@sample.co.jp",
  "is_active": true,
  "created_at": Timestamp,
  "expires_at": Timestamp,
  "monthly_quota": 1000,
  "current_month_usage": 47,
  "current_month_period": "2026-04",  // 月次リセット用
  "notes": "営業担当: ..."
}
```

#### `usage_logs` コレクション
```javascript
{
  "license_id": "OCRA-XXXX-XXXX-XXXX-XXXX",
  "timestamp": Timestamp,
  "endpoint": "/api/v1/ocr/extract",
  "status": "success",  // success / failure
  "processing_time_ms": 3421,
  "gemini_input_tokens": 1234,
  "gemini_output_tokens": 567,
  "error_type": null  // failure 時のみ
}
```

#### `system_config` コレクション (オプション)
```javascript
{
  // ドキュメント ID = "global"
  "default_monthly_quota": 1000,
  "rate_limit_per_minute": 60,
  "maintenance_mode": false,
  "maintenance_message": null
}
```

---

## 6. 制約事項

### 6.1 スコープ外
- 画像の永続保管 (バックエンドは画像を持たない)
- ユーザー認証 UI (管理は Neko が CLI で実施)
- 課金システム (将来検討)
- マルチテナント対応 (1ライセンス = 1企業の単純構造)
- リアルタイムストリーミング (REST API のみ)

### 6.2 制約
- Gemini API のレート制限・利用規約に従う
- Cloud Run の最大リクエストサイズ: 32MB (画像が大きい場合は事前圧縮を推奨)

---

## 7. 開発フェーズ

### Phase B-1: スケルトン構築
- FastAPI プロジェクト作成
- ローカル開発環境 (Firestore エミュレータ)
- ヘルスチェックエンドポイント
- Cloud Run へのデプロイパイプライン

### Phase B-2: 認証層
- ライセンスキー検証エンドポイント
- Firestore `licenses` コレクション
- ライセンス検証ミドルウェア

### Phase B-3: OCR 中継
- `/api/v1/ocr/extract` エンドポイント
- Gemini API 呼び出し
- structured output (response_schema) 対応
- エラーハンドリング

### Phase B-4: 利用量管理
- `usage_logs` 記録
- 月間 quota チェック
- レート制限

### Phase B-5: 運用準備
- 構造化ログ整備
- 管理 CLI スクリプト
- README 整備
- 本番デプロイ

### Phase B-6: 統合テスト
- デスクトップアプリと結合テスト
- E2E シナリオ確認
