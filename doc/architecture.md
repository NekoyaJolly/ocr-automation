# OCR Automation App — アーキテクチャ設計書 (v2, デスクトップアプリ編)

> **v2 改訂の背景**
> v1 のローカル OCR エンジン (NDL OCR Lite) 方式から、Gemini API 経由のクラウド OCR + 構造化抽出方式に変更。バックエンド (Cloud Run) 経由でアクセスする3層構成。本ドキュメントはデスクトップアプリ部分のみを扱う。バックエンド側の設計は `backend/backend-architecture.md` を参照。

## 1. アーキテクチャ概要

### 1.1 設計原則
- **コアバリュー優先**: 「入り口と出口だけが人間、間は全部自動」を常に最優先
- **層分離**: GUI 層 / アプリケーション層 / コア層 / インフラ層を明確に分離
- **抽象化**: OCR エンジン・出力フォーマット・印刷機能は抽象インターフェース経由で利用
- **イベント駆動**: フォルダ監視イベント → 処理パイプライン起動の非同期モデル
- **UI 非ブロッキング**: 重い処理は QThread で実行し GUI 応答性を維持
- **ステートレスなクライアント**: アプリ側に Gemini API キー等の機密情報を持たない

### 1.2 全体構造図(v2)

```
┌─────────────────────────────────────────────────────────┐
│                    GUI 層 (PySide6)                      │
│  MainWindow │ FolderSettings │ TemplateEditor │         │
│             │ TemplateSetEditor │ LicenseSettings       │
└────────────────────────┬────────────────────────────────┘
                         │ Signal/Slot
┌────────────────────────▼────────────────────────────────┐
│                  アプリケーション層                       │
│  AppController │ TaskQueue │ EventDispatcher            │
│  OCRWorker │ PrintWorker                                │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                      コア層                              │
│  Watcher │ OCREngine (Gemini Backend) │ Template │      │
│  Exporter │ Printer │ LicenseManager                    │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                   インフラ層                             │
│  Settings │ Logger │ FileSystem │ HttpClient │          │
│  KeyringStore (OS キーチェーン)                         │
└────────────────────────┬────────────────────────────────┘
                         │ HTTPS
                         ▼
            [バックエンド (別ドキュメント参照)]
                         │
                         ▼
                  [Gemini API]
```

---

## 2. ディレクトリ構造

```
ocr-automation/
├── app/
│   ├── __init__.py
│   ├── main.py                       # エントリポイント
│   ├── __main__.py
│   │
│   ├── gui/                          # GUI 層
│   │   ├── __init__.py
│   │   ├── main_window.py
│   │   ├── folder_settings.py
│   │   ├── template_editor.py        # テンプレート編集 (Phase 4)
│   │   ├── template_set_editor.py    # セット編集 (Phase 4)
│   │   ├── license_settings.py       # ライセンス設定 (Phase 3)
│   │   ├── printer_settings.py       # プリンタ設定 (Phase 5)
│   │   ├── log_viewer.py
│   │   └── widgets/
│   │       ├── __init__.py
│   │       └── field_placement_editor.py
│   │
│   ├── controllers/                  # アプリケーション層
│   │   ├── __init__.py
│   │   ├── app_controller.py
│   │   ├── ocr_worker.py
│   │   └── print_worker.py
│   │
│   ├── core/                         # コア層
│   │   ├── __init__.py
│   │   ├── watcher.py
│   │   ├── ocr_engine.py             # OCR エンジン抽象 + Gemini Backend 実装
│   │   ├── template.py               # テンプレート読込・適用
│   │   ├── exporter.py               # 出力フォーマット抽象 + 各実装
│   │   ├── printer.py                # 印刷抽象 + OS 別実装
│   │   └── license_manager.py        # ライセンスキー管理
│   │
│   ├── models/                       # データモデル(pydantic)
│   │   ├── __init__.py
│   │   ├── settings_model.py
│   │   ├── template_model.py
│   │   ├── ocr_result_model.py
│   │   ├── job_model.py
│   │   └── license_model.py
│   │
│   ├── infrastructure/               # インフラ層
│   │   ├── __init__.py
│   │   ├── settings_store.py
│   │   ├── logger.py
│   │   ├── paths.py
│   │   ├── http_client.py            # バックエンド API クライアント
│   │   └── keyring_store.py          # OS キーチェーンラッパー
│   │
│   ├── exceptions.py
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
│
├── resources/
│   ├── icons/
│   ├── styles/
│   └── translations/
│
├── templates/                        # デフォルトテンプレート
│   ├── default_invoice.yaml
│   └── default_receipt.yaml
│
├── template_sets/                    # デフォルトセット
│   └── default_set.yaml
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│       └── sample_images/
│
├── build/
│   ├── pyinstaller_win.spec
│   └── pyinstaller_mac.spec
│
├── .github/workflows/
│   ├── build.yml
│   └── test.yml
│
├── docs/
│   ├── requirements.md
│   ├── architecture.md
│   ├── CLAUDE.md
│   └── backend/
│       ├── backend-requirements.md
│       ├── backend-architecture.md
│       └── backend-CLAUDE.md
│
├── pyproject.toml
├── uv.lock
├── README.md
└── LICENSE
```

**v1 からの変更点:**
- `vendor/ndlocr_lite/` 削除
- `app/core/license_manager.py` 新規追加
- `app/infrastructure/http_client.py` 新規追加
- `app/infrastructure/keyring_store.py` 新規追加
- `app/models/license_model.py` 新規追加
- `app/gui/license_settings.py` 新規追加
- `docs/backend/` 新規追加

---

## 3. データフロー

### 3.1 処理パイプライン(v2)

```
[1] 入力ルート配下のサブフォルダに画像追加
        ↓
[2] Watcher (watchdog) がイベント検知 + サブフォルダから使用セットを特定
        ↓
[3] ファイル書き込み完了確認(サイズ安定待ち)
        ↓
[4] AppController に Job として投入(画像 + 適用するテンプレートセット)
        ↓
[5] OCRWorker (QThread) がキューから Job 取得
        ↓
[6] テンプレートセット内の有効な各テンプレートをループ:
    ├─ HttpClient でバックエンドに POST
    │   (画像 base64 + 抽出プロンプト + JSON Schema + ライセンスキー)
    ├─ バックエンドが Gemini API を呼び出して構造化 JSON を返す
    ├─ 受信した JSON を pydantic でバリデーション
    ├─ TemplateEngine が field_placements に従って出力データを構築
    ├─ Exporter が指定フォーマットでファイル生成
    ├─ 各テンプレート固有の出力サブフォルダへ保存
    └─ 失敗時: テンプレート単位でリトライ(最大 2 回)
        ↓
[7] 全テンプレート処理完了後、結果を集約
    ├─ 全成功: 元画像を「処理済み」へ移動
    ├─ 部分成功: 成功分は出力済み、失敗分のみ「失敗」記録
    └─ 全失敗: 元画像を「失敗フォルダ」へ移動
        ↓
[8] (テンプレートごとの auto_print フラグ) 印刷対象を PrintWorker へ
        ↓
[9] ログに結果記録 → GUI へ Signal 送信
```

### 3.2 ネットワークエラーハンドリング

ネットワーク起因の失敗はリトライ対象にする:

| 失敗パターン | 扱い |
|------------|------|
| HTTP 5xx (バックエンドエラー) | リトライ対象 |
| HTTP 429 (レート制限) | リトライ対象、バックオフ長め |
| HTTP 401/403 (認証失敗) | リトライしない、ライセンス再確認を促す |
| HTTP 400 (リクエスト不正) | リトライしない、テンプレート設定エラーとして失敗 |
| タイムアウト | リトライ対象 |
| DNS 解決失敗・接続失敗 | リトライ対象 |

リトライ設定:
- 最大 2 回(初回 + リトライ 2 回)
- 指数バックオフ(1秒 → 3秒)
- リトライ対象外のエラーは即失敗扱い

---

## 4. 主要モジュール仕様

### 4.1 `core/watcher.py`

```python
class FolderWatcher:
    """watchdog をラップし、ファイル書き込み完了まで待ってからイベントを発火"""
    
    def __init__(self, watch_dir: Path, on_new_file: Callable[[Path], None]):
        ...
    
    def start(self) -> None: ...
    def stop(self) -> None: ...
```

責務: フォルダ監視のみ。Phase 2 から変更なし。

### 4.2 `core/ocr_engine.py`

```python
class OCREngine(ABC):
    @abstractmethod
    def process(
        self,
        image_path: Path,
        extraction_prompt: str,
        response_schema: dict,
    ) -> OCRResult: ...

class GeminiBackendEngine(OCREngine):
    """バックエンド API 経由で Gemini を呼び出す実装"""
    
    def __init__(
        self,
        http_client: HttpClient,
        license_manager: LicenseManager,
    ):
        self._http = http_client
        self._license = license_manager
    
    def process(
        self,
        image_path: Path,
        extraction_prompt: str,
        response_schema: dict,
    ) -> OCRResult:
        # 1. 画像読み込み + base64 エンコード
        image_b64 = self._encode_image(image_path)
        
        # 2. リクエスト構築
        payload = {
            "image_base64": image_b64,
            "image_mime_type": self._detect_mime(image_path),
            "extraction_prompt": extraction_prompt,
            "response_schema": response_schema,
        }
        
        # 3. ライセンスキー取得
        license_key = self._license.get_active_key()
        
        # 4. バックエンドへ POST
        response = self._http.post(
            "/api/v1/ocr/extract",
            json=payload,
            headers={"X-License-Key": license_key},
        )
        
        # 5. レスポンスパース
        return OCRResult(
            source_image=image_path,
            extracted_data=response.json()["data"],
            raw_response=response.json(),
            processing_time_ms=response.json().get("processing_time_ms", 0),
        )
```

**重要**: v1 で設計していた `OCRBlock` (テキスト + bbox + 信頼度) は廃止。v2 では Gemini が直接構造化 JSON を返すため、ブロック単位のテキスト情報は中間表現として持たない。

### 4.3 `core/template.py`

```python
class FieldPlacement(BaseModel):
    """抽出されたフィールドを出力フォーマットのどこに配置するか"""
    source_key: str           # JSON Schema のキー
    target: str               # 出力先 (xlsx: "B2", docx: "{{invoice_no}}", etc.)
    format_string: str | None = None  # 表示フォーマット
    expand: Literal["none", "rows", "cols"] = "none"  # 配列展開方向

class Template(BaseModel):
    """単一テンプレート定義"""
    name: str
    description: str = ""
    output_format: Literal["txt", "docx", "xlsx", "pdf"]
    output_filename_pattern: str       # 例: "{invoice_no}_{date}.xlsx"
    base_template_file: str | None = None  # ベーステンプレートファイル名
    
    extraction_prompt: str             # Gemini への指示文
    response_schema: dict              # JSON Schema (Gemini structured output)
    field_placements: list[FieldPlacement]

class TemplateSetEntry(BaseModel):
    """セット内の 1 テンプレートエントリ"""
    template_name: str
    enabled: bool = True
    output_subfolder: str
    auto_print: bool = False
    printer_name: str | None = None

class TemplateSet(BaseModel):
    name: str
    description: str = ""
    entries: list[TemplateSetEntry]

class TemplateApplicationResult(BaseModel):
    template_name: str
    status: Literal["success", "failed"]
    output_file: Path | None = None
    error_message: str | None = None
    retry_count: int = 0

class TemplateEngine:
    def apply_set(
        self,
        ocr_engine: OCREngine,
        image_path: Path,
        template_set: TemplateSet,
        templates_by_name: dict[str, Template],
    ) -> list[TemplateApplicationResult]:
        """セット内の各テンプレートを適用、結果リストを返す"""
        ...
    
    def apply_single(
        self,
        ocr_engine: OCREngine,
        image_path: Path,
        template: Template,
    ) -> dict[str, Any]:
        """単一テンプレート適用 (OCR 含む)"""
        # 1. ocr_engine.process() で構造化データ取得
        # 2. field_placements に従ってデータ整形
        # 3. 整形済みデータを返す (Exporter に渡す前段階)
        ...
```

### 4.4 `core/exporter.py`

```python
class Exporter(ABC):
    @abstractmethod
    def export(
        self,
        data: dict[str, Any],
        template: Template,
        output_path: Path,
    ) -> None: ...

class TxtExporter(Exporter):
    """シンプルな key: value のテキスト出力"""
    ...

class DocxExporter(Exporter):
    """python-docx でテンプレート docx に値を埋め込む"""
    # base_template_file をベースに開き、ブックマーク or {{プレースホルダ}} を置換
    ...

class XlsxExporter(Exporter):
    """openpyxl でセル単位に値を書き込む"""
    # field_placements の target をセル番号として解釈
    # expand: "rows" の場合、配列を縦方向に展開
    ...

class PdfExporter(Exporter):
    """pypdf でテンプレート PDF のフォームフィールドに値を書き込む"""
    ...

class ExporterFactory:
    @staticmethod
    def create(format_name: str) -> Exporter: ...
```

### 4.5 `core/license_manager.py` (新規)

```python
class LicenseManager:
    """ライセンスキーの保管・検証を担当"""
    
    def __init__(self, keyring_store: KeyringStore, http_client: HttpClient):
        self._keyring = keyring_store
        self._http = http_client
        self._cached_info: LicenseInfo | None = None
    
    def set_key(self, key: str) -> LicenseInfo:
        """新しいキーを設定し、バックエンドで検証"""
        info = self._verify_with_backend(key)
        if info.is_valid:
            self._keyring.store("license_key", key)
            self._cached_info = info
        return info
    
    def get_active_key(self) -> str:
        """現在有効なキーを取得 (バックエンド呼び出し時に使用)"""
        key = self._keyring.retrieve("license_key")
        if not key:
            raise LicenseNotConfiguredError()
        return key
    
    def get_info(self, force_refresh: bool = False) -> LicenseInfo:
        """ライセンス情報を取得 (キャッシュあり)"""
        if self._cached_info and not force_refresh:
            return self._cached_info
        return self._verify_with_backend(self.get_active_key())
    
    def _verify_with_backend(self, key: str) -> LicenseInfo:
        response = self._http.post(
            "/api/v1/license/verify",
            headers={"X-License-Key": key},
        )
        return LicenseInfo(**response.json())
```

### 4.6 `infrastructure/http_client.py` (新規)

```python
class HttpClient:
    """バックエンド API への HTTP クライアント (httpx ベース)"""
    
    def __init__(self, base_url: str, timeout: float = 30.0):
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={"User-Agent": f"OCRAutomation/{APP_VERSION}"},
        )
    
    def post(self, path: str, json: dict, headers: dict | None = None) -> httpx.Response:
        response = self._client.post(path, json=json, headers=headers or {})
        response.raise_for_status()
        return response
    
    def close(self) -> None:
        self._client.close()
```

`base_url` は環境変数 or 設定ファイルから読み込み。開発時はローカル Cloud Run エミュレータ、本番は Cloud Run の URL。

### 4.7 `infrastructure/keyring_store.py` (新規)

```python
class KeyringStore:
    """OS のキーチェーンを使った機密情報の安全な保存"""
    
    SERVICE_NAME = "OCRAutomation"
    
    def store(self, key: str, value: str) -> None:
        keyring.set_password(self.SERVICE_NAME, key, value)
    
    def retrieve(self, key: str) -> str | None:
        return keyring.get_password(self.SERVICE_NAME, key)
    
    def delete(self, key: str) -> None:
        keyring.delete_password(self.SERVICE_NAME, key)
```

`keyring` ライブラリは:
- macOS: Keychain Access
- Windows: Credential Manager
- Linux: Secret Service (GNOME Keyring 等)

を自動で使い分ける。

---

## 5. データモデル

### 5.1 設定モデル(`models/settings_model.py`)

v1 から `BackendSettings` を追加:

```python
class FolderSettings(BaseModel):
    input_root: Path
    output_root: Path
    failed_folder: Path
    subfolder_to_set: dict[str, str] = {}

class PrinterSettings(BaseModel):
    default_printer: str | None = None
    copies: int = 1

class RetrySettings(BaseModel):
    max_retries: int = 2
    initial_backoff_seconds: float = 1.0
    backoff_multiplier: float = 3.0

class BackendSettings(BaseModel):
    """バックエンド接続設定 (v2 新規)"""
    base_url: str = "https://ocr-backend-xxxxx.run.app"
    timeout_seconds: float = 30.0

class AppSettings(BaseModel):
    folders: FolderSettings
    printer: PrinterSettings
    retry: RetrySettings = RetrySettings()
    backend: BackendSettings = BackendSettings()
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
```

### 5.2 OCR 結果モデル(v2 で全面改訂)

```python
class OCRResult(BaseModel):
    """v2: Gemini が返す構造化データを直接保持"""
    source_image: Path
    extracted_data: dict[str, Any]    # JSON Schema に沿った構造化データ
    raw_response: dict | None = None  # デバッグ用 (生レスポンス)
    processing_time_ms: int = 0
```

v1 の `OCRBlock` (テキスト + bbox + 信頼度) は廃止。

### 5.3 ライセンスモデル(`models/license_model.py`)新規

```python
class LicenseInfo(BaseModel):
    """バックエンドから返るライセンス情報"""
    company_name: str
    is_valid: bool
    expires_at: datetime | None
    monthly_quota: int            # 月間利用上限 (画像数)
    used_this_month: int          # 当月利用数
    last_verified_at: datetime
```

### 5.4 ジョブモデル

```python
class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PARTIAL_SUCCESS = "partial_success"
    COMPLETED = "completed"
    FAILED = "failed"

class Job(BaseModel):
    job_id: str
    source_file: Path
    template_set_name: str
    status: JobStatus
    created_at: datetime
    completed_at: datetime | None = None
    template_results: list[TemplateApplicationResult] = []
```

---

## 6. テンプレートファイル仕様(v2)

### 6.1 テンプレート YAML 定義例

```yaml
# templates/invoice_template.yaml
name: "請求書フォーマットA"
description: "手書き納品書から請求書 xlsx を生成"
output_format: "xlsx"
output_filename_pattern: "{invoice_no}_{issue_date}_invoice.xlsx"
base_template_file: "invoice_base.xlsx"

# Gemini への指示プロンプト (v2 新規)
extraction_prompt: |
  この納品書画像から以下の項目を抽出してください。
  - 請求書番号 (英数字)
  - 発行日 (YYYY-MM-DD 形式)
  - 宛名 (会社名)
  - 明細 (品名・数量・単価・金額の配列)
  - 合計金額 (数値、円)
  
  手書き文字を読み取れない場合は null を返してください。
  推測や創作は絶対にしないでください。

# Gemini structured output 用 JSON Schema (v2 新規)
# nullable は OpenAPI 3.0 形式 (type: string, nullable: true)。
# type: [string, null] の配列表現は Gemini SDK の Schema で拒否される。
response_schema:
  type: object
  required: [invoice_no, issue_date, customer_name, items, total_amount]
  properties:
    invoice_no:
      type: string
      nullable: true
    issue_date:
      type: string
      nullable: true
      format: date
    customer_name:
      type: string
      nullable: true
    items:
      type: array
      items:
        type: object
        properties:
          name: { type: string, nullable: true }
          quantity: { type: number, nullable: true }
          unit_price: { type: number, nullable: true }
          amount: { type: number, nullable: true }
    total_amount:
      type: number
      nullable: true

# 出力配置 (抽出された値をどこに置くか)
field_placements:
  - source_key: "invoice_no"
    target: "B2"
  - source_key: "issue_date"
    target: "B3"
    format_string: "YYYY/MM/DD"
  - source_key: "customer_name"
    target: "B4"
  - source_key: "items"
    target: "A10"
    expand: "rows"
  - source_key: "total_amount"
    target: "D25"
    format_string: "¥#,##0"
```

### 6.2 テンプレートセット YAML 定義例

```yaml
# template_sets/default_set.yaml (キーはファイル名の stem = default_set)
name: "納品書処理セット"
description: "1 枚の納品書から請求書・領収書・控えを同時生成"

entries:
  # template_name は templates/*.yaml のファイル名 (拡張子なし)
  - template_name: "default_invoice"
    enabled: true
    output_subfolder: "invoices"
    auto_print: true
    printer_name: null

  - template_name: "default_receipt"
    enabled: true
    output_subfolder: "receipts"
    auto_print: true
    printer_name: null

  - template_name: "copy_format_a"
    enabled: true
    output_subfolder: "copies"
    auto_print: false  # 控えは保存のみ
    printer_name: null
```

### 6.3 サブフォルダとセットの紐付け

`AppSettings.folders.subfolder_to_set` で管理(v1 と同じ):

```json
{
  "folders": {
    "input_root": "/Users/nekoya/OCR/入力",
    "output_root": "/Users/nekoya/OCR/出力",
    "failed_folder": "/Users/nekoya/OCR/失敗",
    "subfolder_to_set": {
      "納品書": "default_set",
      "見積書": "quote_set"
    }
  }
}
```

---

## 7. パッケージング戦略

### 7.1 PyInstaller 構成(v2 で大幅軽量化)

```python
# build/pyinstaller_mac.spec (抜粋)
a = Analysis(
    ['app/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('resources/icons/*', 'resources/icons'),
        ('templates/*.yaml', 'templates'),
        ('template_sets/*.yaml', 'template_sets'),
    ],
    hiddenimports=[
        'httpx',
        'keyring',
        'pydantic',
    ],
    hookspath=['build/hooks'],
    ...
)
```

`vendor/ndlocr_lite/` がなくなったので、`onnxruntime` などの巨大依存も削除。バンドルサイズは 100〜200MB に縮小見込み。

### 7.2 ビルドターゲット
| OS | 出力形式 | サイズ目安 |
|----|---------|-----------|
| Windows | `.exe` (onedir) → Inno Setup でインストーラ化 | 150MB |
| macOS | `.app` バンドル → `.dmg` 化 | 150MB |

### 7.3 環境変数とデフォルト
- バックエンド URL は **ビルド時に埋め込む**(本番ビルドと開発ビルドで切り替え)
- `BACKEND_BASE_URL` 環境変数で実行時オーバーライド可能(開発時のローカル接続用)

---

## 8. スレッディング設計

### 8.1 スレッド構成
- **メインスレッド**: GUI (PySide6 イベントループ)
- **Watcher スレッド**: watchdog の Observer
- **OCRWorker スレッド**: バックエンド API 呼び出し + テンプレート適用 (QThread)
- **PrintWorker スレッド**: 印刷ジョブ送信 (QThread)

### 8.2 スレッド間通信
- watchdog → AppController: Python 標準 `queue.Queue` + QTimer ポーリング (Phase 2 で確立、継続)
- Worker → GUI: Qt の Signal/Slot

### 8.3 注意点(v2 特有)
- バックエンド API 呼び出しは I/O バウンドなので、GIL は問題にならない
- 複数 Worker の並列実行は **将来検討**(初版は OCRWorker 1 つ)
- `httpx.Client` はスレッドセーフではないため、Worker ごとに別インスタンスを持たせるか、`asyncio` ベースに切り替える(初版はシンプルに同期版で行く)

---

## 9. 設定ファイルの保存場所

### 9.1 ユーザーデータ
| OS | パス |
|----|------|
| Windows | `%APPDATA%\OCRAutomation\` |
| macOS | `~/Library/Application Support/OCRAutomation/` |

### 9.2 ファイル構成
```
OCRAutomation/
├── settings.json          # ユーザー設定
├── templates/             # ユーザー作成テンプレート
│   └── *.yaml
├── template_sets/         # ユーザー作成セット
│   └── *.yaml
└── logs/                  # ログファイル
    └── app_YYYY-MM-DD.log
```

**ライセンスキーは settings.json には保存しない**。OS キーチェーンに格納。

---

## 10. 実装上の重要ポイント

### 10.1 ライセンスキーのライフサイクル
1. 初回起動時: ライセンス設定画面を強制表示
2. キー入力 → バックエンド検証 → 成功時のみキーチェーンに保存
3. 通常起動時: キーチェーンから読み込み → バックエンドで再検証 (起動時に1回)
4. 検証失敗時: ライセンス設定画面に強制遷移、機能停止
5. 月初等の定期再検証: 1日1回バックエンドで再検証してキャッシュ更新

### 10.2 ファイル書き込み完了検知
v1 から変更なし。`watcher.py` 内でファイルサイズ安定化を待つ。

### 10.3 出力フォルダ監視と無限ループ防止
v1 から変更なし。出力フォルダ監視で印刷をトリガーする際、出力フォルダ自体を入力にしない。

### 10.4 PySide6 と PyInstaller の相性
`--collect-all PySide6` オプションで全プラグインを強制バンドル。

### 10.5 リトライ機構の実装
v1 設計を踏襲、ネットワークエラーも対象に追加:

```python
def _apply_with_retry(
    self,
    ocr_engine: OCREngine,
    image_path: Path,
    entry: TemplateSetEntry,
    template: Template,
) -> TemplateApplicationResult:
    max_retries = self._settings.retry.max_retries
    backoff = self._settings.retry.initial_backoff_seconds
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            data = self._template_engine.apply_single(ocr_engine, image_path, template)
            output_path = self._exporter.export(data, template, entry.output_subfolder)
            return TemplateApplicationResult(
                template_name=template.name,
                status="success",
                output_file=output_path,
                retry_count=attempt,
            )
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
            # ネットワーク系はリトライ対象
            last_error = e
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= self._settings.retry.backoff_multiplier
        except (LicenseInvalidError, TemplateConfigError) as e:
            # 認証エラー・設定エラーはリトライしない
            last_error = e
            break
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= self._settings.retry.backoff_multiplier

    return TemplateApplicationResult(
        template_name=template.name,
        status="failed",
        error_message=str(last_error),
        retry_count=max_retries,
    )
```

### 10.6 サブフォルダベース監視
v1 から変更なし。watchdog の Observer は再帰監視 (`recursive=True`)。

### 10.7 画像送信時のサイズ最適化
- バックエンドへの送信前に、画像が極端に大きい場合はリサイズ (例: 長辺 2000px に制限)
- ただし精度に影響しない範囲で。Gemini は内部で自動リサイズするため、過度な削減は不要
- ファイルフォーマットは jpeg/png/pdf を中心にサポート

---

## 11. テスト戦略

### 11.1 ユニットテスト
- 各 Core モジュールの単体動作
- pydantic モデルのバリデーション
- テンプレート適用ロジック
- リトライ機構(httpx.MockTransport を使ってネットワーク呼び出しをモック)

### 11.2 統合テスト
- バックエンドのモックサーバーを立てて E2E テスト
- 実際の Gemini API を叩くテストは別途、コスト管理しながら実行

### 11.3 GUI テスト
- pytest-qt でスモークテスト
- ライセンス未設定状態の起動シナリオ
- バックエンド接続失敗時の挙動

---

## 12. v1 からの主な変更点まとめ

| 項目 | v1 | v2 |
|------|----|----|
| OCR エンジン | NDL OCR Lite (ローカル) | Gemini 3.1 Pro Preview (バックエンド経由) |
| ネット接続 | 不要 | 必須 |
| 配布物サイズ | 1〜2GB | 100〜200MB |
| API キー管理 | 不要 | キーチェーン保存 + バックエンド検証 |
| フィールド抽出方式 | 位置/キーワード/正規表現の戦略 | Gemini の structured output で一発 |
| OCR 結果モデル | OCRBlock 配列 (テキスト + bbox) | extracted_data (構造化 JSON) |
| 認証 | なし | ライセンスキー方式 |
| 依存ライブラリ | onnxruntime, NDL OCR Lite | httpx, keyring |
| バックエンド | なし | Cloud Run + FastAPI + Firestore |
