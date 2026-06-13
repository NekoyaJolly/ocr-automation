# OCR Automation App — アーキテクチャ設計書

## 1. アーキテクチャ概要

### 1.1 設計原則
- **単一プロセス・完全バンドル**: NDL OCR Lite を含む全コンポーネントを 1 つの Python プロセス内で動作させる
- **層分離**: GUI 層 / アプリケーション層 / コア層 / インフラ層を明確に分離
- **抽象化**: OCR エンジン・出力フォーマット・印刷機能は抽象インターフェース経由で利用
- **イベント駆動**: フォルダ監視イベント → 処理パイプライン起動の非同期モデル
- **UI 非ブロッキング**: 重い処理は QThread で実行し GUI 応答性を維持

### 1.2 全体構造図

```
┌─────────────────────────────────────────────────────────┐
│                    GUI 層 (PySide6)                      │
│  MainWindow │ FolderSettings │ TemplateEditor │ ...     │
└────────────────────────┬────────────────────────────────┘
                         │ Signal/Slot
┌────────────────────────▼────────────────────────────────┐
│                  アプリケーション層                       │
│  AppController │ TaskQueue │ EventDispatcher            │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                      コア層                              │
│  Watcher │ OCREngine │ Parser │ Template │ Exporter │   │
│                              │ Printer                  │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                   インフラ層                             │
│  Settings │ Logger │ FileSystem │ NDL OCR Lite (内蔵)   │
└─────────────────────────────────────────────────────────┘
```

---

## 2. ディレクトリ構造

```
ocr-automation/
├── app/
│   ├── __init__.py
│   ├── main.py                       # エントリポイント
│   │
│   ├── gui/                          # GUI 層
│   │   ├── __init__.py
│   │   ├── main_window.py            # メインウィンドウ
│   │   ├── folder_settings.py        # フォルダ設定画面
│   │   ├── template_editor.py        # テンプレート編集画面
│   │   ├── printer_settings.py       # プリンタ設定画面
│   │   ├── log_viewer.py             # ログ表示ウィジェット
│   │   └── widgets/                  # 再利用ウィジェット
│   │       ├── __init__.py
│   │       └── field_mapper.py       # フィールドマッピング UI
│   │
│   ├── controllers/                  # アプリケーション層
│   │   ├── __init__.py
│   │   ├── app_controller.py         # 全体統括コントローラ
│   │   ├── ocr_worker.py             # QThread ベース OCR ワーカー
│   │   └── print_worker.py           # QThread ベース印刷ワーカー
│   │
│   ├── core/                         # コア層
│   │   ├── __init__.py
│   │   ├── watcher.py                # watchdog ラッパー
│   │   ├── ocr_engine.py             # OCR エンジン抽象 + NDL 実装
│   │   ├── parser.py                 # OCR 結果パーサ
│   │   ├── template.py               # テンプレート読込・適用
│   │   ├── exporter.py               # 出力フォーマット抽象 + 各実装
│   │   └── printer.py                # 印刷抽象 + OS 別実装
│   │
│   ├── models/                       # データモデル(pydantic)
│   │   ├── __init__.py
│   │   ├── settings_model.py         # ユーザー設定モデル
│   │   ├── template_model.py         # テンプレート定義モデル
│   │   ├── ocr_result_model.py       # OCR 結果モデル
│   │   └── job_model.py              # 処理ジョブモデル
│   │
│   ├── infrastructure/               # インフラ層
│   │   ├── __init__.py
│   │   ├── settings_store.py         # 設定永続化
│   │   ├── logger.py                 # ロガー初期化
│   │   └── paths.py                  # OS 別パス解決
│   │
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
│
├── vendor/                           # サードパーティを内包
│   └── ndlocr_lite/                  # NDL OCR Lite 本体
│       ├── src/                      # ソースコード
│       ├── models/                   # ONNX モデル
│       └── LICENSE
│
├── resources/                        # GUI リソース
│   ├── icons/
│   ├── styles/
│   └── translations/
│
├── templates/                        # デフォルトテンプレート
│   ├── default_text.yaml
│   └── default_table.yaml
│
├── template_sets/                    # デフォルトテンプレートセット
│   └── default_set.yaml
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│       └── sample_images/
│
├── build/                            # ビルド成果物・spec ファイル
│   ├── pyinstaller_win.spec
│   ├── pyinstaller_mac.spec
│   └── hooks/                        # PyInstaller フック
│
├── .github/
│   └── workflows/
│       ├── build.yml                 # マルチ OS ビルド
│       └── test.yml                  # ユニットテスト
│
├── docs/
│   ├── requirements.md
│   ├── architecture.md
│   └── user_guide.md
│
├── pyproject.toml
├── uv.lock
├── CLAUDE.md
├── README.md
└── LICENSE
```

---

## 3. データフロー

### 3.1 OCR 処理パイプライン

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
[6] OCREngine.process() で NDL OCR Lite 呼び出し (1 回のみ)
        ↓
[7] Parser が OCR 結果を構造化データに変換
        ↓
[8] テンプレートセット内の有効な各テンプレートをループ:
    ├─ Template が現在のテンプレートを適用しフィールドマッピング
    ├─ Exporter が指定フォーマットでファイル生成
    ├─ 各テンプレート固有の出力サブフォルダへ保存
    └─ 失敗時: テンプレート単位でリトライ(最大 2 回 / 指数バックオフ)
        ↓
[9] 全テンプレート処理完了後、結果を集約
    ├─ 全成功: 元画像を「処理済み」へ
    ├─ 部分成功: 成功分は出力済み、失敗テンプレートのみ「失敗」記録
    └─ 全失敗: 元画像を「失敗フォルダ」へ
        ↓
[10] (テンプレートごとの auto_print フラグ) 印刷対象ファイルのみ PrintWorker へ送信
        ↓
[11] ログに結果記録 → GUI へ Signal 送信
```

### 3.2 エラーハンドリング

各テンプレート単位でリトライを行い、テンプレートセット全体としては部分成功を許容する:

1. テンプレート適用または出力で例外発生
2. 例外内容をログに記録
3. 同一テンプレートで最大 2 回までリトライ(1 秒 → 3 秒間隔)
4. 全リトライ失敗 → そのテンプレートの結果を「失敗」とマーク
5. セット内の他のテンプレートは継続処理
6. セット全処理完了後、全体結果を集約してログと GUI に通知

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
    
    # 内部: ファイルサイズが N 秒間安定したら「書き込み完了」と判定
```

**責務**: フォルダ監視のみ。ビジネスロジックは持たない。

### 4.2 `core/ocr_engine.py`

```python
class OCREngine(ABC):
    @abstractmethod
    def process(self, image_path: Path) -> OCRResult: ...

class NDLOCRLiteEngine(OCREngine):
    """NDL OCR Lite を同一プロセス内で import して使用"""
    
    def __init__(self):
        # vendor/ndlocr_lite から必要モジュールを import
        from vendor.ndlocr_lite.src import ocr as ndl_ocr
        self._ndl = ndl_ocr
        self._initialize_models()
    
    def process(self, image_path: Path) -> OCRResult:
        # NDL OCR Lite の内部 API を呼び出し
        # (具体的な API は実装フェーズで NDL のソースを読んで決定)
        ...
```

**重要**: NDL OCR Lite の内部 API は公式ドキュメント化されていないため、実装フェーズで `vendor/ndlocr_lite/src/ocr.py` のソースを読み、`main()` 関数の内部処理を再現する形で組み込む。

### 4.3 `core/template.py`

```python
class Template(BaseModel):
    """単一テンプレート定義"""
    name: str
    output_format: Literal["txt", "docx", "xlsx", "pdf"]
    output_filename_pattern: str
    fields: list[FieldMapping]

class FieldMapping(BaseModel):
    source_key: str           # OCR 出力のキー
    output_label: str         # 出力フォーマット上のラベル
    target_position: str      # docx の段落名 / xlsx のセル / etc
    data_type: Literal["string", "number", "date", "currency"]
    format_string: str | None = None

class TemplateSetEntry(BaseModel):
    """セット内の 1 テンプレートエントリ"""
    template_name: str           # 参照する Template の名前
    enabled: bool = True
    output_subfolder: str        # 出力ルート配下のサブフォルダ名
    auto_print: bool = False
    printer_name: str | None = None  # None ならデフォルトプリンタ

class TemplateSet(BaseModel):
    """複数テンプレートをまとめるセット"""
    name: str
    description: str = ""
    entries: list[TemplateSetEntry]

class TemplateEngine:
    def apply_set(
        self,
        ocr_result: OCRResult,
        template_set: TemplateSet,
        templates_by_name: dict[str, Template],
    ) -> list[TemplateApplicationResult]:
        """テンプレートセットを適用し、各テンプレートの結果リストを返す。

        部分成功を許容し、失敗したテンプレートはリトライ機構に渡される。
        """
        ...

    def apply_single(
        self, ocr_result: OCRResult, template: Template
    ) -> dict[str, Any]:
        """単一テンプレート適用(セット内部から呼ばれる)"""
        ...

class TemplateApplicationResult(BaseModel):
    template_name: str
    status: Literal["success", "failed"]
    output_file: Path | None = None
    error_message: str | None = None
    retry_count: int = 0
```

### 4.4 `core/exporter.py`

```python
class Exporter(ABC):
    @abstractmethod
    def export(self, mapped_data: dict, template: Template, output_path: Path) -> None: ...

class TxtExporter(Exporter): ...
class DocxExporter(Exporter): ...   # python-docx
class XlsxExporter(Exporter): ...   # openpyxl
class PdfExporter(Exporter): ...    # reportlab

class ExporterFactory:
    @staticmethod
    def create(format_name: str) -> Exporter: ...
```

### 4.5 `core/printer.py`

```python
class Printer(ABC):
    @abstractmethod
    def list_printers(self) -> list[str]: ...
    @abstractmethod
    def print_file(self, file_path: Path, printer_name: str | None = None) -> None: ...

class WindowsPrinter(Printer):
    """pywin32 を使用"""
    ...

class MacPrinter(Printer):
    """lp コマンドを subprocess で使用"""
    ...

def get_printer() -> Printer:
    if sys.platform == "win32":
        return WindowsPrinter()
    elif sys.platform == "darwin":
        return MacPrinter()
    else:
        raise NotImplementedError
```

### 4.6 `controllers/app_controller.py`

```python
class AppController(QObject):
    """アプリ全体の状態管理と Worker 統括"""
    
    # Signals
    job_started = Signal(str)       # job_id
    job_completed = Signal(str, Path)  # job_id, output_path
    job_failed = Signal(str, str)   # job_id, error_message
    log_message = Signal(str, str)  # level, message
    
    def __init__(self, settings: Settings):
        super().__init__()
        self._watcher_input = FolderWatcher(...)
        self._watcher_output = FolderWatcher(...)
        self._ocr_worker = OCRWorker(...)
        self._print_worker = PrintWorker(...)
    
    def start(self) -> None: ...
    def stop(self) -> None: ...
```

### 4.7 `controllers/ocr_worker.py`

```python
class OCRWorker(QThread):
    """OCR 処理を別スレッドで実行(GUI 非ブロッキング)"""
    
    def __init__(self, ocr_engine: OCREngine, template_engine: TemplateEngine,
                 exporter_factory: ExporterFactory):
        super().__init__()
        self._queue: Queue[Job] = Queue()
        ...
    
    def enqueue(self, job: Job) -> None: ...
    def run(self) -> None:
        while not self._stop_requested:
            job = self._queue.get()
            self._process(job)
```

---

## 5. データモデル

### 5.1 設定モデル(`models/settings_model.py`)

```python
class FolderSettings(BaseModel):
    input_root: Path             # 入力ルートフォルダ
    output_root: Path            # 出力ルートフォルダ
    failed_folder: Path
    # サブフォルダ → テンプレートセット名 のマッピング
    # 例: {"納品書": "delivery_note_set", "領収書": "receipt_set"}
    subfolder_to_set: dict[str, str]

class PrinterSettings(BaseModel):
    default_printer: str | None = None  # システムデフォルトを使う場合 None
    copies: int = 1

class RetrySettings(BaseModel):
    max_retries: int = 2
    initial_backoff_seconds: float = 1.0
    backoff_multiplier: float = 3.0

class AppSettings(BaseModel):
    folders: FolderSettings
    printer: PrinterSettings
    retry: RetrySettings = RetrySettings()
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
```

### 5.2 OCR 結果モデル

```python
class OCRBlock(BaseModel):
    text: str
    bbox: tuple[int, int, int, int]   # x, y, w, h
    confidence: float

class OCRResult(BaseModel):
    source_image: Path
    blocks: list[OCRBlock]
    raw_text: str
    processing_time_ms: int
```

### 5.3 ジョブモデル

```python
class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PARTIAL_SUCCESS = "partial_success"  # セット内一部成功
    COMPLETED = "completed"
    FAILED = "failed"

class Job(BaseModel):
    job_id: str                              # UUID
    source_file: Path
    template_set_name: str                   # 適用するテンプレートセット名
    status: JobStatus
    created_at: datetime
    completed_at: datetime | None = None
    template_results: list[TemplateApplicationResult] = []  # 各テンプレートの結果
```

---

## 6. テンプレートファイル仕様

### 6.1 単一テンプレート YAML 定義例

```yaml
# templates/invoice_template.yaml
name: "請求書フォーマットA"
description: "手書き請求書を Excel に変換"
output_format: "xlsx"
output_filename_pattern: "{date}_{source_basename}_invoice.xlsx"

template_file: "invoice_template.xlsx"  # ベースとなるテンプレートファイル(任意)

fields:
  - source_key: "invoice_no"
    output_label: "請求書番号"
    target_position: "B2"
    data_type: "string"
  
  - source_key: "issue_date"
    output_label: "発行日"
    target_position: "B3"
    data_type: "date"
    format_string: "YYYY/MM/DD"
  
  - source_key: "total_amount"
    output_label: "合計金額"
    target_position: "D10"
    data_type: "currency"
    format_string: "¥#,##0"
```

### 6.2 テンプレートセット YAML 定義例

```yaml
# template_sets/delivery_note_set.yaml
name: "納品書処理セット"
description: "1 枚の納品書画像から請求書・領収書・控えを同時生成"

entries:
  - template_name: "請求書フォーマットA"
    enabled: true
    output_subfolder: "invoices"
    auto_print: true               # 請求書は印刷する
    printer_name: null             # null = デフォルトプリンタ

  - template_name: "領収書フォーマットA"
    enabled: true
    output_subfolder: "receipts"
    auto_print: true               # 領収書も印刷する
    printer_name: null

  - template_name: "控えフォーマットA"
    enabled: true
    output_subfolder: "copies"
    auto_print: false              # 控えは保存のみ(税理士共有用)
    printer_name: null
```

### 6.3 サブフォルダとセットの紐付け

`AppSettings.folders.subfolder_to_set` で管理:

```json
{
  "folders": {
    "input_root": "C:/OCR/入力",
    "output_root": "C:/OCR/出力",
    "failed_folder": "C:/OCR/失敗",
    "subfolder_to_set": {
      "納品書": "delivery_note_set",
      "領収書のみ": "receipt_only_set",
      "見積書": "quote_set"
    }
  }
}
```

実行時の動作:
- `C:/OCR/入力/納品書/abc.jpg` を検知 → `delivery_note_set` を適用
- `delivery_note_set` 内の有効な 3 テンプレートを順次適用
- 出力は `C:/OCR/出力/invoices/`, `C:/OCR/出力/receipts/`, `C:/OCR/出力/copies/` へ
- 請求書と領収書は自動印刷、控えはファイル保存のみ

### 6.4 フィールドマッピング戦略

OCR 結果から `source_key` への対応付けは以下の戦略を選択可能:

1. **位置ベース**: 画像上の座標範囲を指定
2. **正規表現ベース**: 抽出テキスト全体からパターンマッチ
3. **キーワードベース**: 「請求書番号:」のような前置きキーワードで検索

初版では位置ベースとキーワードベースを実装。

---

## 7. パッケージング戦略

### 7.1 PyInstaller 構成

```python
# build/pyinstaller_win.spec (抜粋)
a = Analysis(
    ['app/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('vendor/ndlocr_lite/models/*.onnx', 'vendor/ndlocr_lite/models'),
        ('vendor/ndlocr_lite/src/*.py', 'vendor/ndlocr_lite/src'),
        ('resources/icons/*', 'resources/icons'),
        ('templates/*.yaml', 'templates'),
    ],
    hiddenimports=[
        'onnxruntime',
        'PIL',
        'numpy',
        # NDL OCR Lite 内部で使われる暗黙インポートをここに列挙
    ],
    hookspath=['build/hooks'],
    ...
)
```

### 7.2 ビルドターゲット
| OS | 出力形式 | サイズ目安 |
|----|---------|-----------|
| Windows | `.exe` (onedir) → Inno Setup で `.exe` インストーラ化 | 1.5GB |
| macOS | `.app` バンドル → `.dmg` 化 | 1.5GB |

### 7.3 GitHub Actions マトリクス

```yaml
strategy:
  matrix:
    os: [windows-latest, macos-latest]
    python-version: ["3.11"]
```

---

## 8. スレッディング設計

### 8.1 スレッド構成
- **メインスレッド**: GUI(PySide6 イベントループ)
- **Watcher スレッド**: watchdog の Observer(自動)
- **OCRWorker スレッド**: OCR 処理キュー消化(QThread)
- **PrintWorker スレッド**: 印刷ジョブ送信(QThread)

### 8.2 スレッド間通信
- watchdog → AppController: `QtCore.QMetaObject.invokeMethod` または Signal Emit(別スレッドから安全)
- Worker → GUI: Qt の Signal/Slot 機構(自動的にスレッド境界を越える)

### 8.3 注意点
- NDL OCR Lite 内部の ONNX Runtime は GIL を解放して CPU 計算するため、別スレッドで実行しても GUI はブロックされない
- ただし NDL OCR Lite が内部でグローバル状態を持つ場合、複数 Worker から同時呼び出しは避ける(初版は OCRWorker 1 つに限定)

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
├── settings.json          # ユーザー設定(サブフォルダ→セット紐付け含む)
├── templates/             # ユーザー作成テンプレート
│   └── *.yaml
├── template_sets/         # ユーザー作成テンプレートセット
│   └── *.yaml
└── logs/                  # ログファイル
    └── app_YYYY-MM-DD.log
```

---

## 10. 実装上の重要ポイント

### 10.1 NDL OCR Lite の内部組み込み
- `vendor/ndlocr_lite/` 配下に NDL OCR Lite のソース一式を配置
- `git submodule` ではなくファイルコピーで管理(ライセンス上 CC BY 4.0 で再配布可能)
- `__init__.py` を追加して Python パッケージとして import 可能にする
- NDL 側の依存ライブラリ(onnxruntime 等)はメインの `pyproject.toml` に統合

### 10.2 ファイル書き込み完了検知
画像ファイルは書き込み中に `on_created` イベントが発火する場合があるため、ファイルサイズの安定化を待つ:

```python
def wait_for_stable(path: Path, check_interval: float = 0.5, stable_count: int = 3) -> bool:
    last_size = -1
    stable = 0
    while stable < stable_count:
        try:
            current = path.stat().st_size
        except FileNotFoundError:
            return False
        if current == last_size:
            stable += 1
        else:
            stable = 0
            last_size = current
        time.sleep(check_interval)
    return True
```

### 10.3 出力フォルダ監視と無限ループ防止
- 出力フォルダ監視で印刷をトリガーする際、出力フォルダ自体を入力にしないこと
- 印刷後のファイルを「印刷済み」サブフォルダに移動するか、印刷済みファイルパスを記録して重複防止

### 10.4 PySide6 と PyInstaller の相性
- PySide6 は PyInstaller との相性が良いが、Qt プラグインの自動検出が時々失敗する
- `--collect-all PySide6` オプションで全プラグインを強制バンドル

### 10.5 リトライ機構の実装
テンプレート単位でのリトライは Worker 内部で完結させる:

```python
def _apply_with_retry(
    self,
    ocr_result: OCRResult,
    entry: TemplateSetEntry,
    template: Template,
) -> TemplateApplicationResult:
    max_retries = self._settings.retry.max_retries
    backoff = self._settings.retry.initial_backoff_seconds
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            mapped = self._template_engine.apply_single(ocr_result, template)
            output_path = self._exporter.export(mapped, template, entry.output_subfolder)
            return TemplateApplicationResult(
                template_name=template.name,
                status="success",
                output_file=output_path,
                retry_count=attempt,
            )
        except Exception as e:
            last_error = e
            self._logger.warning(
                f"テンプレート '{template.name}' 適用失敗 (試行 {attempt + 1}/{max_retries + 1}): {e}"
            )
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

**注意点**:
- リトライ対象は「テンプレート適用 + ファイル出力」のステップのみ
- OCR 処理自体はリトライしない(セット内の全テンプレートで結果を共有するため)
- 印刷ジョブのリトライは PrintWorker 側で別途管理

### 10.6 サブフォルダベース監視の注意
- watchdog の Observer は再帰監視 (`recursive=True`) を使用
- 入力ルートの直下サブフォルダを動的に検出し、`subfolder_to_set` 設定と照合
- 紐付けされていないサブフォルダのファイルはスキップ(警告ログのみ)
- 入力ルート配下に新しいサブフォルダが作成された場合、GUI に通知して紐付け設定を促す

---

## 11. テスト戦略

### 11.1 ユニットテスト(`tests/unit/`)
- 各 Core モジュールの単体動作
- pydantic モデルのバリデーション
- テンプレート適用ロジック

### 11.2 統合テスト(`tests/integration/`)
- サンプル画像 → OCR → 出力ファイル生成までの E2E
- 実際のテンプレートファイルを使用

### 11.3 GUI テスト
- pytest-qt を使用
- 主要画面のスモークテスト
