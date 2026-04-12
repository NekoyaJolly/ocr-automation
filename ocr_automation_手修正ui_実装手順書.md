# ocr-automation 手修正UI 実装手順書

## 1. 目的

本手順書は、`ocr-automation` に **OCR結果の手修正UI** を追加し、OCRの精度不足があってもユーザーが修正してそのまま再出力できる状態まで実装するための手順をまとめたものである。

本実装の主目的は、AIの読取精度をひたすら上げることではなく、**「読めなかった箇所だけ人が直し、業務を止めずに完了できる」** という運用導線を成立させることである。

---

## 2. 今回の完成条件

### 2.1 実装対象

今回の実装では、以下を完成条件とする。

- OCR後にレビュー要否を判定できる
- レビュー待ちジョブを一覧で確認できる
- 元画像を見ながら抽出結果を修正できる
- 必須項目の未入力や形式異常を検知できる
- 修正済みデータを保存できる
- 修正済みデータからOCR再実行なしで再出力できる
- 承認済みジョブを `processed` に移動できる
- 却下済みジョブを `failed` に移動できる

### 2.2 今回は実装しないもの

以下は今回のスコープ外とする。

- 画像上での矩形編集
- OCRモデルの再学習
- ベクトルストア連携
- 文字単位の学習データ保存
- 自動補正の高度化
- 複数人レビュー
- 権限管理
- 承認履歴の高度な監査機能

---

## 3. 現行アーキテクチャ上の実装方針

現行構成では、主に以下のコンポーネントが存在する。

- `MainWindow` : タブ構成のメインGUI
- `AppController` : アプリ全体のオーケストレーション
- `OCRWorker` : OCR + テンプレート処理ワーカー
- `Job` : 1件の処理単位を表すモデル

本実装では、既存構造を大きく壊さず、**OCRWorker 完了後にレビュー待ち分岐を挟み、AppController でレビュー待ちを管理し、MainWindow にレビュー用タブを追加する** 方針とする。

---

## 4. 実装全体像

### 4.1 処理フロー（変更後）

```text
画像追加
  ↓
Watcher が検知
  ↓
Job 作成・投入
  ↓
OCRWorker が OCR 実行
  ↓
抽出結果を正規化
  ↓
レビュー要否判定
  ├─ レビュー不要 → そのまま出力 → processed へ移動
  └─ レビュー必要 → review_jobs に保存 → レビューUIで修正
                                          ↓
                                     承認して出力
                                          ↓
                                   processed へ移動
```

---

## 5. 実装手順

# Phase 1: データモデル拡張

## 5.1 対象ファイル

- `app/models/job_model.py`

## 5.2 目的

レビュー待ち・レビュー中・承認済みなどの状態、およびOCR結果・修正結果を `Job` に保持できるようにする。

## 5.3 実装内容

### 5.3.1 `ReviewStatus` の追加

追加する状態:

- `NOT_REQUIRED`
- `PENDING`
- `IN_REVIEW`
- `APPROVED`
- `REJECTED`

### 5.3.2 `Job` への追加フィールド

追加候補:

- `review_status`
- `review_required`
- `review_reasons`
- `raw_ocr_result`
- `normalized_result`
- `user_corrected_result`
- `reviewed_at`

## 5.4 実装例

```python
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.models.template_model import TemplateApplicationResult


class JobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    PARTIAL_SUCCESS = "partial_success"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class Job(BaseModel):
    job_id: str
    source_file: Path
    template_set_name: str
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None
    template_results: list[TemplateApplicationResult] = Field(default_factory=list)

    # 手修正UI向け追加項目
    review_status: ReviewStatus = ReviewStatus.NOT_REQUIRED
    review_required: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    raw_ocr_result: dict[str, Any] = Field(default_factory=dict)
    normalized_result: dict[str, Any] = Field(default_factory=dict)
    user_corrected_result: dict[str, Any] = Field(default_factory=dict)
    reviewed_at: datetime | None = None
```

## 5.5 完了条件

- `Job` モデルがレビュー情報を保持できる
- 既存のジョブ処理に影響なく読み込める

---

# Phase 2: レビュー要否判定ルールの追加

## 6.1 対象ファイル

- 新規 `app/core/review_rules.py`

## 6.2 目的

OCR結果に対し、「そのまま出力してよいか」「人の確認が必要か」を機械的に判定できるようにする。

## 6.3 実装内容

### 6.3.1 `needs_review()` 関数の追加

返り値:

- `bool`: レビュー要否
- `list[str]`: レビュー理由

### 6.3.2 初期ルール

最低限、以下を実装する。

- OCR結果が空
- 必須項目が空
- 日付形式が不正
- 金額欄が数値でない
- 明細配列が空
- テンプレート配置に必要なキーがない

## 6.4 実装例

```python
from __future__ import annotations

from typing import Any

from app.models.template_model import Template


def needs_review(
    extracted_data: dict[str, Any],
    template: Template,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    if not extracted_data:
        reasons.append("OCR結果が空です")
        return True, reasons

    required_keys = template.response_schema.get("required", [])
    for key in required_keys:
        value = extracted_data.get(key)
        if value in (None, "", []):
            reasons.append(f"必須項目が未取得です: {key}")

    return len(reasons) > 0, reasons
```

## 6.5 完了条件

- 最低限のレビュー判定が可能
- 理由を文字列で返せる

---

# Phase 3: レビュー待ち永続化機構

## 7.1 対象ファイル

- 新規 `app/infrastructure/review_store.py`

## 7.2 目的

レビュー待ちジョブを永続化し、アプリ再起動後も復元できるようにする。

## 7.3 保存先方針

ユーザーデータ配下に以下を作成する。

```text
OCRAutomation/
└── review_jobs/
    ├── <job_id>.json
    └── ...
```

## 7.4 実装内容

### 7.4.1 `save_job(job)`
- `job_id.json` として保存

### 7.4.2 `load_all_review_jobs()`
- 全レビュー待ちジョブを読み込む

### 7.4.3 `delete_job(job_id)`
- 承認・却下後に削除可能にする

## 7.5 実装例

```python
from __future__ import annotations

import json
from pathlib import Path

from app.models.job_model import Job


class ReviewStore:
    def __init__(self, base_dir: Path) -> None:
        self._dir = base_dir / "review_jobs"
        self._dir.mkdir(parents=True, exist_ok=True)

    def save_job(self, job: Job) -> None:
        path = self._dir / f"{job.job_id}.json"
        path.write_text(job.model_dump_json(indent=2), encoding="utf-8")

    def load_all_review_jobs(self) -> list[Job]:
        jobs: list[Job] = []
        for file_path in self._dir.glob("*.json"):
            data = json.loads(file_path.read_text(encoding="utf-8"))
            jobs.append(Job.model_validate(data))
        return jobs

    def delete_job(self, job_id: str) -> None:
        path = self._dir / f"{job_id}.json"
        if path.exists():
            path.unlink()
```

## 7.6 完了条件

- レビュー待ちジョブが永続化される
- 再起動後に復元可能

---

# Phase 4: AppController へのレビュー管理追加

## 8.1 対象ファイル

- `app/controllers/app_controller.py`

## 8.2 目的

レビュー待ちジョブを `AppController` で管理し、承認・却下・再出力を一元化する。

## 8.3 実装内容

### 8.3.1 `ReviewStore` の組み込み

初期化時にレビュー待ち一覧を読み込む。

### 8.3.2 内部保持構造の追加

- `_review_jobs: dict[str, Job]`

### 8.3.3 追加メソッド

- `get_review_jobs()`
- `mark_job_for_review(job)`
- `approve_review(job_id, corrected_data)`
- `reject_review(job_id, reason)`
- `export_corrected_job(job_id)`

### 8.3.4 `_on_job_completed()` の見直し

現在は即 `processed` へ移動しているが、レビュー必要時は移動せず、レビュー待ちへ送る。

### 8.3.5 `_on_job_failed()` の見直し

レビューで却下されたもののみ `failed` へ移動する。

## 8.4 完了条件

- レビュー待ちジョブを保持できる
- 承認・却下・再出力導線が `AppController` に集約される

---

# Phase 5: OCRWorker でのレビュー待ち分岐実装

## 9.1 対象ファイル

- `app/controllers/ocr_worker.py`

## 9.2 目的

OCR完了後、ただちに出力するのではなく、レビュー必要なものをレビュー待ちへ回せるようにする。

## 9.3 実装内容

### 9.3.1 抽出結果を `Job` に保持

- `raw_ocr_result`
- `normalized_result`

### 9.3.2 `needs_review()` を呼び出す

レビュー必要なら:

- `job.review_required = True`
- `job.review_status = ReviewStatus.PENDING`
- `job.review_reasons = [...]`

### 9.3.3 レビュー必要時は出力を止める

今回は最小スコープとして、レビュー必要時は最終出力を行わず、レビュー待ちへ送る。

### 9.3.4 ステータス整理

- 出力済みなら `COMPLETED`
- レビュー待ちなら `PARTIAL_SUCCESS` でもよいが、レビュー待ち状態を優先的に参照する

## 9.4 完了条件

- OCR後にレビュー待ちへ送れる
- そのまま `processed` に流れない

---

# Phase 6: レビュー一覧タブの追加

## 10.1 対象ファイル

- 新規 `app/gui/review_queue.py`
- 修正 `app/gui/main_window.py`

## 10.2 目的

レビュー待ちジョブをGUIから一覧確認し、レビュー編集画面へ遷移できるようにする。

## 10.3 実装内容

### 10.3.1 `ReviewQueueWidget` 作成

表示項目:

- ファイル名
- テンプレートセット名
- レビュー理由
- 作成時刻
- レビュー状態
- 開くボタン

### 10.3.2 `MainWindow` にタブ追加

タブ名:

- `レビュー`

### 10.3.3 リロード処理追加

- タブ表示時に一覧更新
- 承認・却下後に更新

## 10.4 完了条件

- レビュー待ちジョブ一覧が表示される
- 詳細画面へ遷移可能

---

# Phase 7: レビュー編集画面の追加

## 11.1 対象ファイル

- 新規 `app/gui/review_editor.py`

## 11.2 目的

ユーザーが元画像を見ながらOCR結果を修正し、保存・承認・却下できるようにする。

## 11.3 画面要件

### 左ペイン

- 元画像プレビュー

### 右ペイン

- 項目名
- 抽出値
- 編集欄
- 必須表示
- レビュー理由
- バリデーションエラー表示

### 下部

- 保存
- 承認して出力
- 却下

## 11.4 実装内容

### 11.4.1 汎用フォーム描画

対応型は最初は以下でよい。

- `str`
- `int`
- `float`
- `date` 相当の文字列
- `list[object]` は簡易表示で開始してよい

### 11.4.2 バリデーション

- 必須項目未入力で承認不可
- 形式異常を表示

### 11.4.3 保存処理

- `user_corrected_result` を更新
- `ReviewStore` へ保存

## 11.5 完了条件

- ユーザーが修正できる
- 保存できる
- 必須項目チェックが効く

---

# Phase 8: 修正済みデータから再出力

## 12.1 対象ファイル

- `app/controllers/app_controller.py`
- 必要に応じて `app/core/template.py`

## 12.2 目的

ユーザー修正済みデータを使って、OCR再実行なしに最終出力を生成する。

## 12.3 実装内容

### 12.3.1 `export_corrected_job(job_id)` 実装

入力:

- `user_corrected_result`

出力:

- 既存のテンプレート・Exporter へ流す

### 12.3.2 承認後の処理

- `review_status = APPROVED`
- `processed` へ移動
- 必要なら印刷キュー投入
- `ReviewStore` から削除または履歴保存

### 12.3.3 却下後の処理

- `review_status = REJECTED`
- `failed` へ移動
- `ReviewStore` から削除または履歴保存

## 12.4 完了条件

- OCR再実行なしで再出力できる
- 承認導線が成立する

---

# Phase 9: MainWindow との統合

## 13.1 対象ファイル

- `app/gui/main_window.py`

## 13.2 実装内容

- `レビュー` タブ追加
- レビュー件数の更新
- 承認/却下後のログ表示
- 必要ならステータスバー表示追加

## 13.3 完了条件

- メイン画面からレビュー運用が可能

---

# Phase 10: テスト追加

## 14.1 対象

- `tests/unit/`
- `tests/integration/`

## 14.2 追加テスト

### 単体テスト

- `review_rules.py`
  - 必須欠落でレビュー必要
  - 正常データでレビュー不要

- `review_store.py`
  - 保存
  - 読込
  - 削除

### 統合テスト

- `AppController`
  - レビュー必要ジョブが `processed` に行かない
  - 承認後に出力へ進む
  - 却下後に `failed` へ移動する

### GUIスモークテスト（可能なら）

- レビュー一覧が開く
- レビュー編集画面が開く

## 14.3 完了条件

- レビュー導線の最低限保証がある

---

## 15. 実装順の推奨

実装順は以下とする。

1. `job_model.py` の拡張
2. `review_rules.py` 追加
3. `review_store.py` 追加
4. `app_controller.py` にレビュー管理追加
5. `ocr_worker.py` にレビュー待ち分岐追加
6. `review_queue.py` 作成
7. `main_window.py` にレビュータブ追加
8. `review_editor.py` 作成
9. 修正済み再出力実装
10. テスト追加

---

## 16. GitHub Issue に切る場合のタスク一覧

以下の8件に分けると実装管理しやすい。

1. `Jobモデルにレビュー状態と修正結果を追加する`
2. `レビュー要否判定ルールを追加する`
3. `レビュー待ちジョブの永続化機構を追加する`
4. `AppControllerにレビュー待ち管理機能を追加する`
5. `OCRWorkerでレビュー待ち分岐を実装する`
6. `レビュー一覧タブを追加する`
7. `レビュー編集画面を追加する`
8. `修正済みデータから再出力する導線を実装する`

---

## 17. 最小完成の定義

今回の最小完成は以下とする。

**1帳票・1テンプレート・OCR結果を手修正可能・修正後に再出力可能**

ここまで到達すれば、単なる技術デモではなく、実運用に試せる最小製品となる。

---

## 18. 補足方針

- 今回は「精度改善」より「運用で止まらない導線」を優先する
- ローカルOCR化やファインチューニングは別フェーズとする
- テンプレート編集UIとレビューUIは責務を分離する
- ユーザー修正結果は将来の改善資産として残す

---

## 19. 最終ゴール

本実装の最終ゴールは、次の一文に集約される。

**OCRが完全でなくても、ユーザーが不足箇所だけを直し、数分以内に出力まで完了できる状態を作る。**

