# CLAUDE.md — OCR Automation App 開発方針

このドキュメントは Claude Code がこのプロジェクトを開発する際に遵守すべき方針・規約・優先順位を定義する。

## 1. プロジェクトの本質

このアプリは「**手書き画像 → OCR → 複数テンプレート同時適用 → 出力 → 自動印刷**」を一気通貫で自動化するクロスプラットフォームのデスクトップアプリ。

**最優先事項**:
1. **完全オフライン動作** — 一切のネット通信を行わない
2. **完全バンドル配布** — エンドユーザーのPCに Python が無くても動く単体アプリとして配布
3. **シンプルな UI** — Python やコマンドライン知識ゼロのユーザーが直感的に使える
4. **テンプレートセット** — 1 枚の画像から複数フォーマットを同時生成できる(例: 納品書 → 請求書 + 領収書 + 控え)
5. **部分成功許容 + リトライ** — セット内の一部失敗を許容、失敗テンプレートのみ最大 2 回リトライ

詳細は `docs/requirements.md` と `docs/architecture.md` を参照すること。**実装前に必ず両方を読むこと。**

---

## 2. 絶対遵守ルール

### 2.1 技術スタック固定
以下は確定事項であり、勝手に変更しないこと:

- **言語**: Python 3.11
- **GUI**: PySide6(Tkinter / customtkinter / Electron 等への変更禁止)
- **OCR エンジン**: NDL OCR Lite(`vendor/ndlocr_lite/` に内包、import で呼び出し)
- **フォルダ監視**: watchdog
- **データモデル**: pydantic v2
- **パッケージング**: PyInstaller(onedir 形式)
- **依存管理**: uv

別ライブラリへの置き換えを提案したい場合は、**実装前に必ずユーザーに相談すること。** 勝手にリファクタしない。

### 2.2 アーキテクチャ境界の保持
- 層構造(GUI / Controller / Core / Infrastructure)を守ること
- GUI 層から Core 層を直接呼ばない(必ず Controller 経由)
- Core 層は GUI フレームワーク(PySide6)に依存しない(将来 CLI 化も可能なように)
- OCR エンジン・出力フォーマット・印刷は **必ず抽象クラス経由** で利用

### 2.3 NDL OCR Lite の扱い
- `vendor/ndlocr_lite/` 配下のファイルは **NDL 公式の成果物** であり、内部を直接編集しないこと
- 必要なラッパーは `app/core/ocr_engine.py` の `NDLOCRLiteEngine` クラスに集約
- ライセンスは CC BY 4.0 — クレジット表記を About 画面と README に必ず含める
- NDL OCR Lite の内部 API は公式ドキュメント化されていない。実装時は `vendor/ndlocr_lite/src/ocr.py` のソースコードを読んで再現すること

### 2.4 サブプロセス禁止
NDL OCR Lite を **subprocess で呼び出さない**。必ず同一プロセス内で `import` して呼び出すこと。理由は配布形態(PyInstaller バンドル)で外部 Python を前提にできないため。

---

## 3. 開発フェーズと優先順位

`docs/requirements.md` セクション 6 で定義された Phase 順に進めること。**フェーズを飛び越えない**。

| Phase | 内容 | 完了条件 |
|-------|------|---------|
| 1 | コア機能プロトタイプ | CLI で画像を指定 → OCR → テキスト出力できる |
| 2 | GUI 実装 | PySide6 のメイン画面で監視開始/停止できる |
| 3 | テンプレートエンジン | YAML テンプレートで docx/xlsx/pdf 出力できる |
| 4 | テンプレートエディタ GUI | 視覚的にフィールドマッピング編集できる |
| 5 | 印刷機能 | Win/Mac で自動印刷が動く |
| 6 | パッケージング | PyInstaller で .exe / .app を生成できる |
| 7 | テスト・配布準備 | 各 OS で動作確認、リリース可能 |

各 Phase の終了時に必ず動作確認を行い、ユーザーに完了報告すること。

---

## 4. コーディング規約

### 4.1 スタイル
- フォーマッタ: **ruff format**(Black 互換)
- リンタ: **ruff check**
- 型ヒント: **必須**(全関数に引数・戻り値の型を付ける)
- 型チェッカー: mypy(strict モード推奨)

### 4.2 命名規則
- モジュール: `snake_case.py`
- クラス: `PascalCase`
- 関数・変数: `snake_case`
- 定数: `UPPER_SNAKE_CASE`
- プライベート: `_leading_underscore`

### 4.3 Pythonic な書き方
- pathlib を使う(`os.path` を使わない)
- f-string を使う(`%` や `.format()` を使わない)
- list/dict/set 内包表記を活用
- `match` 文を積極的に使う(Python 3.10+)
- 例外は具体的にキャッチ(裸の `except:` 禁止)

### 4.4 docstring
全てのパブリック関数・クラスに docstring を書くこと。スタイルは Google 形式。

```python
def process_image(image_path: Path) -> OCRResult:
    """画像ファイルを OCR 処理し結果を返す。

    Args:
        image_path: 処理対象の画像ファイルパス

    Returns:
        OCR 結果オブジェクト

    Raises:
        OCRError: OCR 処理に失敗した場合
    """
    ...
```

### 4.5 エラーハンドリング
- カスタム例外を `app/exceptions.py` に定義して使う
- ログには必ず例外の trace を含める(`logger.exception()`)
- ユーザー向けエラーメッセージは日本語で記述

---

## 5. テスト方針

### 5.1 必須テスト
- 新規追加した Core モジュールには必ずユニットテストを書く
- pydantic モデルはバリデーションテストを書く
- GUI コードは pytest-qt でスモークテスト

### 5.2 テスト実行
```bash
uv run pytest tests/
uv run pytest tests/unit/test_ocr_engine.py -v
```

### 5.3 サンプル画像
- `tests/fixtures/sample_images/` にテスト用画像を配置
- 著作権上問題ない画像のみ使用

---

## 6. 言語

### 6.1 ユーザー向け文字列
- GUI ラベル・メッセージ・ログ出力: **日本語**
- 将来的な多言語化を見越して、文字列は `app/i18n/` に集約することが望ましい(初版では直書きでも可)

### 6.2 開発者向け
- コメント: 日本語OK
- docstring: 日本語OK
- 変数名・関数名: 英語(必須)
- コミットメッセージ: 日本語OK

---

## 7. Git コミット規約

### 7.1 コミット粒度
- 1 コミット = 1 論理的変更
- 大きな機能追加は適切に分割
- WIP コミットは push 前に squash

### 7.2 メッセージ形式
```
<type>: <短い説明>

<詳細説明(任意)>
```

type: `feat` / `fix` / `refactor` / `docs` / `test` / `chore` / `build`

例:
```
feat: NDLOCRLiteEngine の基本実装を追加

vendor/ndlocr_lite を import して画像 1 枚を OCR 処理する
最小実装。エラーハンドリングは未対応。
```

---

## 8. 禁止事項

以下は **絶対にやらないこと**:

1. **クラウドAPI への接続** — このアプリはオフライン専用
2. **ユーザーデータの外部送信** — テレメトリやエラーレポート送信も含む
3. **NDL OCR Lite ソースの改変** — `vendor/` 配下は読み取り専用扱い
4. **subprocess での Python 呼び出し** — 同一プロセス内 import に統一
5. **GUI 層からの直接 OCR 呼び出し** — Controller 経由必須
6. **同期処理での GUI ブロック** — 重い処理は必ず QThread
7. **テストなしのコア機能追加** — Core 層は必ずテストとセット
8. **依存ライブラリの勝手な追加** — 新規依存追加時はユーザー承認必須

---

## 9. 質問していい場面・自走していい場面

### 9.1 質問すべき場面
- 要件定義書・アーキテクチャ設計書に明記されていない仕様判断が必要な時
- 技術スタックの変更を検討したい時
- NDL OCR Lite の内部 API が想定と異なり、設計変更が必要な時
- 新規依存ライブラリを追加したい時

### 9.2 自走していい場面
- ドキュメントに記載済みの内容を実装する時
- バグ修正・リファクタリング(既存の振る舞いを変えない範囲)
- テスト追加
- ドキュメント補完

---

## 10. 参照ドキュメント

実装中に参照すべき情報源:

- `docs/requirements.md` — 機能要件・非機能要件・制約事項
- `docs/architecture.md` — アーキテクチャ・モジュール仕様・データフロー
- NDL OCR Lite 公式: <https://github.com/ndl-lab/ndlocr-lite>
- NDL OCR Lite 使い方: <https://lab.ndl.go.jp/data_set/ndlocrlite-usage/>
- PySide6 公式: <https://doc.qt.io/qtforpython-6/>
- watchdog 公式: <https://python-watchdog.readthedocs.io/>
- pydantic v2 公式: <https://docs.pydantic.dev/latest/>

---

## 11. 困った時の優先順位

実装中に判断に迷った場合の優先順位:

1. **ユーザー(開発者本人)に相談** — 仕様判断はユーザーが決める
2. `docs/requirements.md` の記載 — 要件に立ち戻る
3. `docs/architecture.md` の記載 — 設計に立ち戻る
4. 「シンプルさ」を選ぶ — 複雑な解決策より単純な解決策
5. 「動く実装」を優先 — 完璧より動作を優先(後でリファクタ可能)

---

## 12. このドキュメントの更新

- このドキュメントの内容に変更が必要な場合、**勝手に編集せず必ずユーザーに提案すること**
- ユーザーの承認を得てから更新すること
