# CLAUDE.md — OCR Automation App 開発方針 (v2)

このドキュメントは Cursor / Claude Code がこのプロジェクトのデスクトップアプリ部分を開発する際に遵守すべき方針・規約・優先順位を定義する。バックエンドの開発方針は `docs/backend/backend-CLAUDE.md` を参照。

## 1. プロジェクトの本質

このアプリは「**手書き画像 → クラウド OCR + 構造化抽出 → 複数テンプレート同時適用 → 出力 → 自動印刷**」を一気通貫で自動化するクロスプラットフォームのデスクトップアプリ。

### コアバリュー(North Star)

**「入り口と出口だけが人間、間は全部自動」**

- 入り口: スキャナで紙を取り込む or ユーザーがフォルダに画像をドラッグ
- 間: ファイル検知 → 画像送信 → OCR + 構造化抽出 → テンプレート適用 → ファイル生成 → 印刷 (全自動)
- 出口: プリンタから出てきた紙を受け取る

**全ての設計判断はこのコアバリューを最優先する**。設計上の迷いがあれば「これはコアバリューを守るか?」と問い直すこと。

### 最優先事項

1. **完全バンドル配布** — エンドユーザーの PC に Python が無くても動く単体アプリとして配布
2. **シンプルな UI** — Python やコマンドライン知識ゼロのユーザーが直感的に使える
3. **テンプレートセット** — 1 枚の画像から複数フォーマットを同時生成 (例: 納品書 → 請求書 + 領収書 + 控え)
4. **部分成功許容 + リトライ** — セット内の一部失敗を許容、失敗テンプレートのみ最大 2 回リトライ
5. **クラウド OCR + 構造化抽出** — Gemini 3.1 Pro Preview の構造化出力機能を活用、フィールドマッピング戦略は不要
6. **セキュアなライセンス管理** — API キーをアプリに埋め込まない、バックエンド経由

詳細は `docs/requirements.md` と `docs/architecture.md` を参照。**実装前に必ず両方を読むこと**。

---

## 2. 絶対遵守ルール

### 2.1 技術スタック固定

以下は確定事項であり、勝手に変更しないこと:

- **言語**: Python 3.12
- **GUI**: PySide6
- **OCR エンジン**: 自前バックエンド経由の Gemini 3.1 Pro Preview (`GeminiBackendEngine`)
- **HTTP クライアント**: httpx
- **キーチェーン**: keyring
- **フォルダ監視**: watchdog
- **データモデル**: pydantic v2
- **パッケージング**: PyInstaller (onedir 形式)
- **依存管理**: uv

別ライブラリへの置き換えを提案したい場合は、**実装前に必ずユーザーに相談すること**。

### 2.2 アーキテクチャ境界の保持

- 層構造 (GUI / Controller / Core / Infrastructure) を守ること
- GUI 層から Core 層を直接呼ばない (必ず Controller 経由)
- Core 層は GUI フレームワーク (PySide6) に依存しない
- OCR エンジン・出力フォーマット・印刷は **必ず抽象クラス経由** で利用

### 2.3 API キー・機密情報の取り扱い (CRITICAL)

- **アプリ内に Gemini API キーを絶対に埋め込まない**
- **アプリ内に GCP 認証情報を絶対に埋め込まない**
- ライセンスキーは平文で settings.json に保存しない (必ず `keyring` 経由でキーチェーンに保存)
- バックエンド URL のみ環境変数 or ビルド時定数として埋め込む
- バックエンドへの通信は常に HTTPS、ライセンスキーをヘッダで送信

**この方針に反する実装は重大なセキュリティ違反**。

### 2.4 v1 からの方針変更を理解すること

**v1 (NDL OCR Lite 方式) は廃止された**。以下を覚えておくこと:

- `vendor/ndlocr_lite/` ディレクトリは削除済み (もし存在したら削除)
- `onnxruntime` 等のローカル ML 依存は削除
- フィールドマッピング戦略 (位置ベース/キーワードベース/正規表現) は **実装しない**
- v1 で設計されていた `OCRBlock` (テキスト + bbox + 信頼度) は **廃止**
- 完全オフライン動作は **不可**(ネット接続必須)

### 2.5 バックエンド担当範囲との分離

- このプロジェクトの `app/` 配下はデスクトップアプリのみ
- バックエンド (FastAPI + Cloud Run) の実装は別ディレクトリ・別セッションで行う
- バックエンド呼び出しは `app/infrastructure/http_client.py` 経由のみ
- バックエンド側のコードを `app/` に書かない

### 2.6 テンプレート YAML の注意 (response_schema と辞書キー)

- **`response_schema` の nullable**: Gemini 用には OpenAPI 3.0 準拠の `type: string` と `nullable: true` の組み合わせで書く。**`type: [string, null]` の配列表現は `google-genai` の Schema バリデーションで拒否される**ため使わない。
- **テンプレート・セットの参照キー**: `load_all_templates` / `load_all_template_sets` の辞書キーは **YAML ファイル名の stem**（拡張子なし）。`subfolder_to_set` の値も `default_set` のように **template_sets のファイル名**を指す。YAML 内の `name` は人間向け表示用。

---

## 3. 開発フェーズと優先順位

`docs/requirements.md` セクション 6 で定義された Phase 順に進めること。

| Phase | 状態 | 内容 |
|-------|------|------|
| 1 | ✅ 完了 | コア機能プロトタイプ |
| 2 | ✅ 完了 | GUI 実装 (メインウィンドウ・watcher・フォルダ設定) |
| 3 | 🚧 次 | バックエンド構築 + Gemini 連携 + テンプレートセット + ライセンス + リトライ |
| 4 | 未着手 | テンプレート/セットエディタ GUI、ライセンス設定画面 |
| 5 | 未着手 | 印刷機能 |
| 6 | 未着手 | パッケージング (PyInstaller) |
| 7 | 未着手 | テスト・配布準備 |

各 Phase の終了時に必ず動作確認を行い、ユーザーに完了報告すること。

### Phase 3 のスコープ (デスクトップアプリ側)

Phase 3 はバックエンドと並行して進む。デスクトップアプリ側で実装するもの:

1. `app/infrastructure/http_client.py` — httpx ベースのバックエンド API クライアント
2. `app/infrastructure/keyring_store.py` — OS キーチェーンラッパー
3. `app/models/license_model.py` — `LicenseInfo`
4. `app/core/license_manager.py` — ライセンスキーの保管・検証
5. `app/core/ocr_engine.py` — `OCREngine` 抽象 + `GeminiBackendEngine` 実装
   - **既存の `NDLOCRLiteEngine` は削除または無効化**
6. `app/models/template_model.py` — `Template`, `FieldPlacement`, `TemplateSet`, `TemplateSetEntry`, `TemplateApplicationResult`
7. `app/core/template.py` — `TemplateEngine`
8. `app/core/exporter.py` — `Exporter` 抽象 + `TxtExporter` / `DocxExporter` / `XlsxExporter` / `PdfExporter`
9. `app/controllers/ocr_worker.py` の更新 — 新しい OCR エンジンとテンプレート機構を使う、リトライ機構追加
10. `app/controllers/app_controller.py` の更新 — サブフォルダ → セット紐付け対応
11. `app/models/settings_model.py` の更新 — `BackendSettings` 追加
12. 既存 `vendor/ndlocr_lite/` の削除と `pyproject.toml` の依存整理

### Phase 3 完了条件

1. ライセンスキーが未設定の状態でアプリ起動 → エラー or ライセンス要求が出る
2. ライセンスキーをコードから設定 (Phase 4 で GUI 実装) → バックエンド検証成功
3. `templates/` と `template_sets/` に YAML を手動配置 → アプリが読み込む
4. 入力サブフォルダごとに異なるテンプレートセットが適用される
5. 1 枚の画像から複数の出力ファイルが同時生成される (例: 納品書 → 請求書 xlsx + 領収書 pdf + 控え docx)
6. ネットワークエラー時に最大 2 回リトライされる
7. 部分成功を許容する (セット内の一部成功 + 一部失敗でも、成功分は出力)
8. 成功画像は処理済みフォルダへ移動、失敗画像は失敗フォルダへ移動

---

## 4. コーディング規約

### 4.1 スタイル
- フォーマッタ: **ruff format**
- リンタ: **ruff check**
- 型ヒント: **必須**(全関数に引数・戻り値の型を付ける)
- 型チェッカー: mypy (strict モード推奨)

### 4.2 命名規則
- モジュール: `snake_case.py`
- クラス: `PascalCase`
- 関数・変数: `snake_case`
- 定数: `UPPER_SNAKE_CASE`
- プライベート: `_leading_underscore`

### 4.3 Pythonic な書き方
- pathlib を使う
- f-string を使う
- list/dict/set 内包表記を活用
- `match` 文を積極的に使う
- 例外は具体的にキャッチ

### 4.4 docstring
全てのパブリック関数・クラスに Google スタイルの docstring を書くこと。

### 4.5 エラーハンドリング
- カスタム例外を `app/exceptions.py` に定義
- ログには必ず例外の trace を含める (`logger.exception()`)
- ユーザー向けエラーメッセージは日本語

### 4.6 v2 で追加するカスタム例外

```python
# app/exceptions.py に追加
class LicenseError(OCRAutomationError): pass
class LicenseNotConfiguredError(LicenseError): pass
class LicenseInvalidError(LicenseError): pass
class LicenseExpiredError(LicenseError): pass
class LicenseQuotaExceededError(LicenseError): pass

class BackendError(OCRAutomationError): pass
class BackendUnreachableError(BackendError): pass
class BackendBadRequestError(BackendError): pass

class TemplateConfigError(OCRAutomationError): pass
```

---

## 5. テスト方針

### 5.1 必須テスト
- 新規追加した Core モジュールには必ずユニットテストを書く
- バックエンド呼び出しは `httpx.MockTransport` でモック
- pydantic モデルはバリデーションテストを書く
- GUI コードは pytest-qt でスモークテスト

### 5.2 テスト実行
```bash
uv run pytest tests/
```

### 5.3 サンプル画像
- `tests/fixtures/sample_images/` にテスト用画像を配置
- バックエンドモックを使うので実際の Gemini 呼び出しは不要

---

## 6. 言語

### 6.1 ユーザー向け文字列
- GUI ラベル・メッセージ・ログ出力: **日本語**

### 6.2 開発者向け
- コメント・docstring: 日本語OK
- 変数名・関数名: 英語(必須)
- コミットメッセージ: 日本語OK

---

## 7. Git コミット規約

### 7.1 コミット粒度
- 1 コミット = 1 論理的変更
- 大きな機能追加は適切に分割
- **Phase 3 は実装範囲が広いため、最低 8〜10 コミットに分割すること**(一気にコミットしない)

### 7.2 推奨コミット分割例 (Phase 3)

1. `feat: OCREngine 抽象を Gemini 経由に書き換え、NDL OCR Lite 関連を削除`
2. `feat: HttpClient と KeyringStore のインフラ層追加`
3. `feat: LicenseManager と LicenseInfo モデル追加`
4. `feat: GeminiBackendEngine 実装`
5. `feat: テンプレートモデル (Template, FieldPlacement, TemplateSet 等) 追加`
6. `feat: TemplateEngine 実装 (apply_set, apply_single)`
7. `feat: Exporter 抽象 + TxtExporter 実装`
8. `feat: DocxExporter 実装`
9. `feat: XlsxExporter 実装`
10. `feat: PdfExporter 実装`
11. `feat: OCRWorker をリトライ機構付きに更新`
12. `feat: AppController をサブフォルダ→セット紐付け対応に更新`
13. `feat: BackendSettings を AppSettings に追加`
14. `chore: vendor/ndlocr_lite と関連依存を削除`
15. `test: 新規モジュールのユニットテスト追加`

### 7.3 メッセージ形式
```
<type>: <短い説明>

<詳細説明(任意)>
```

type: `feat` / `fix` / `refactor` / `docs` / `test` / `chore` / `build`

---

## 8. 禁止事項

以下は **絶対にやらないこと**:

1. **Gemini API キーや GCP 認証情報をアプリに埋め込む** — 重大なセキュリティ違反
2. **ライセンスキーを平文で settings.json に保存** — keyring 経由必須
3. **バックエンドを介さず直接 Gemini API を呼ぶ** — 設計違反
4. **完全オフライン動作の試み** — v2 ではネット接続前提
5. **NDL OCR Lite 関連コードの復活** — v1 で廃止された
6. **フィールドマッピング戦略 (位置/キーワード/正規表現) の実装** — Gemini structured output で代替
7. **GUI 層からの直接 OCR 呼び出し** — Controller 経由必須
8. **同期処理での GUI ブロック** — 重い処理は必ず QThread
9. **テストなしのコア機能追加** — Core 層は必ずテストとセット
10. **依存ライブラリの勝手な追加** — 新規依存追加時はユーザー承認必須
11. **`docs/backend/` 配下のドキュメントに従ってバックエンド側のコードを `app/` 配下に書く** — バックエンドは別プロジェクト

---

## 9. 質問していい場面・自走していい場面

### 9.1 質問すべき場面
- 要件定義書・アーキテクチャ設計書に明記されていない仕様判断
- 技術スタックの変更を検討したい時
- 新規依存ライブラリを追加したい時
- バックエンド API のスキーマ (リクエスト/レスポンス形式) が `backend-architecture.md` の記述と食い違う場合
- ライセンス検証の挙動が要件と一致しない場合

### 9.2 自走していい場面
- ドキュメントに記載済みの内容を実装する時
- バグ修正・リファクタリング (既存の振る舞いを変えない範囲)
- テスト追加
- ドキュメント補完

---

## 10. 参照ドキュメント

- `docs/requirements.md` — 機能要件・非機能要件・制約事項 (v2)
- `docs/architecture.md` — デスクトップアプリのアーキテクチャ (v2)
- `docs/backend/backend-requirements.md` — バックエンドの要件
- `docs/backend/backend-architecture.md` — バックエンドのアーキテクチャ
- `docs/backend/backend-CLAUDE.md` — バックエンド側の開発方針
- Gemini API 公式: <https://ai.google.dev/>
- PySide6 公式: <https://doc.qt.io/qtforpython-6/>
- httpx 公式: <https://www.python-httpx.org/>
- keyring 公式: <https://github.com/jaraco/keyring>
- pydantic v2 公式: <https://docs.pydantic.dev/latest/>

---

## 11. 困った時の優先順位

1. **ユーザー(開発者本人)に相談**
2. `docs/requirements.md` の記載 — 要件に立ち戻る
3. `docs/architecture.md` の記載 — 設計に立ち戻る
4. **コアバリュー (「入り口と出口だけが人間」) に立ち戻る**
5. 「シンプルさ」を選ぶ
6. 「動く実装」を優先 — 完璧より動作

---

## 12. このドキュメントの更新

- このドキュメントの内容に変更が必要な場合、**勝手に編集せず必ずユーザーに提案すること**
- ユーザーの承認を得てから更新すること
