"""AppController — アプリケーション全体のオーケストレーション。"""

from __future__ import annotations

import queue
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from app.controllers.ocr_worker import OCRWorker
from app.controllers.print_worker import PrintJob, PrintWorker
from app.core.license_manager import LicenseManager
from app.core.ocr_engine import OCREngine
from app.core.printer import Printer, create_printer
from app.core.review_rules import ReviewTier, assess_review
from app.core.template import (
    TemplateEngine,
    load_all_template_sets,
    load_all_templates,
)
from app.core.watcher import FolderWatcher
from app.infrastructure.logger import get_logger
from app.infrastructure.paths import (
    get_review_history_dir,
    get_review_jobs_dir,
    get_user_template_sets_dir,
    get_user_templates_dir,
)
from app.infrastructure.review_history_store import ReviewHistoryStore
from app.infrastructure.review_store import ReviewStore
from app.infrastructure.settings_store import SettingsStore
from app.models.job_model import Job, JobStatus, ReviewStatus
from app.models.ocr_result_model import FieldConfidence
from app.models.settings_model import AppSettings
from app.models.template_model import Template, TemplateApplicationResult, TemplateSet
from app.utils.helpers import generate_job_id

logger = get_logger(__name__)


class AppController(QObject):
    """アプリケーション層の中心。Watcher → Job 投入 → Worker 管理を行う。"""

    review_queue_count_changed = Signal(int)

    def __init__(
        self,
        settings_store: SettingsStore,
        ocr_engine: OCREngine,
        license_manager: LicenseManager,
    ) -> None:
        super().__init__()
        self._settings_store = settings_store
        self._settings: AppSettings = settings_store.load()
        self._ocr_engine = ocr_engine
        self._license_manager = license_manager

        self._template_engine = TemplateEngine()
        self._printer: Printer = create_printer()

        self._templates: dict[str, Template] = {}
        self._template_sets: dict[str, TemplateSet] = {}
        self._reload_templates()

        self._job_queue: queue.Queue[Job] = queue.Queue()
        self._print_queue: queue.Queue[PrintJob] = queue.Queue()

        self._watcher: FolderWatcher | None = None
        self._ocr_worker: OCRWorker | None = None
        self._print_worker: PrintWorker | None = None

        self._review_store = ReviewStore(get_review_jobs_dir())
        self._review_history_store = ReviewHistoryStore(get_review_history_dir())
        self._review_jobs: dict[str, Job] = {}
        self._load_persisted_review_jobs()

    def _load_persisted_review_jobs(self) -> None:
        for job in self._review_store.load_all_review_jobs():
            if job.review_status in (ReviewStatus.PENDING, ReviewStatus.IN_REVIEW):
                self._review_jobs[job.job_id] = job
        self._emit_review_count()

    def _emit_review_count(self) -> None:
        self.review_queue_count_changed.emit(self.pending_review_count)

    @property
    def pending_review_count(self) -> int:
        return sum(
            1
            for j in self._review_jobs.values()
            if j.review_status in (ReviewStatus.PENDING, ReviewStatus.IN_REVIEW)
        )

    @property
    def settings(self) -> AppSettings:
        return self._settings

    @property
    def templates(self) -> dict[str, Template]:
        return self._templates

    @property
    def template_sets(self) -> dict[str, TemplateSet]:
        return self._template_sets

    @property
    def template_engine(self) -> TemplateEngine:
        return self._template_engine

    def reload_settings(self) -> None:
        """設定ファイルを再読み込みする。"""
        self._settings = self._settings_store.load()

    def save_settings(self) -> None:
        """現在の設定を保存する。"""
        self._settings_store.save(self._settings)

    def get_review_jobs(self) -> list[Job]:
        """レビュー待ち・レビュー中のジョブを新しい順で返す。"""
        jobs = [
            j
            for j in self._review_jobs.values()
            if j.review_status in (ReviewStatus.PENDING, ReviewStatus.IN_REVIEW)
        ]
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        return jobs

    def get_review_job(self, job_id: str) -> Job | None:
        return self._review_jobs.get(job_id)

    def mark_job_open_in_review(self, job_id: str) -> None:
        """レビュー編集 UI を開いたときに状態を更新して保存する。"""
        job = self._review_jobs.get(job_id)
        if job is None:
            return
        job.review_status = ReviewStatus.IN_REVIEW
        self._review_store.save_job(job)

    def save_review_job(self, job: Job) -> None:
        """修正内容をメモリとストアに保存する。"""
        if job.job_id not in self._review_jobs:
            self._review_jobs[job.job_id] = job
        self._review_store.save_job(job)

    def validate_review_job_for_approval(self, job: Job) -> tuple[bool, list[str]]:
        """承認前に修正済みデータをルールで再検証する。"""
        reasons: list[str] = []
        template_set = self._template_sets.get(job.template_set_name)
        if not template_set:
            return False, ["テンプレートセットが見つかりません"]
        for entry in template_set.entries:
            if not entry.enabled:
                continue
            template = self._templates.get(entry.template_name)
            if template is None:
                continue
            mapped = job.user_corrected_result.get(entry.template_name)
            if mapped is None:
                mapped = job.normalized_result.get(entry.template_name)
            if not mapped:
                continue
            raw = mapped.get("__raw__", {})
            if not isinstance(raw, dict):
                raw = {}
            mfc = mapped.get("__field_confidences__") or {}
            fc_parsed: dict[str, FieldConfidence] | None = None
            if mfc:
                fc_parsed = {
                    k: FieldConfidence.model_validate(v) if isinstance(v, dict) else v
                    for k, v in mfc.items()
                }
            a = assess_review(
                raw,
                template,
                template_label=template.name,
                field_confidences=fc_parsed,
            )
            if a.tier == ReviewTier.NEEDS_REVIEW:
                reasons.extend(a.reasons)
        return (len(reasons) == 0, reasons)

    def export_corrected_job(self, job: Job) -> None:
        """修正済み (または正規化済み) データからファイルを出力し template_results を更新する。"""
        template_set = self._template_sets.get(job.template_set_name)
        if not template_set:
            raise ValueError(f"テンプレートセット未定義: {job.template_set_name}")
        output_root = self._settings.folders.output_root
        new_results: list[TemplateApplicationResult] = []
        for entry in template_set.entries:
            if not entry.enabled:
                continue
            template = self._templates.get(entry.template_name)
            if template is None:
                new_results.append(
                    TemplateApplicationResult(
                        template_name=entry.template_name,
                        status="failed",
                        error_message="テンプレート未定義",
                    )
                )
                continue
            data = job.user_corrected_result.get(entry.template_name)
            if data is None:
                data = job.normalized_result.get(entry.template_name)
            if data is None:
                new_results.append(
                    TemplateApplicationResult(
                        template_name=entry.template_name,
                        status="failed",
                        error_message="出力用データがありません",
                    )
                )
                continue
            try:
                path = self._template_engine.export_mapped_entry(
                    mapped=data,
                    template=template,
                    entry=entry,
                    output_root=output_root,
                )
                new_results.append(
                    TemplateApplicationResult(
                        template_name=entry.template_name,
                        status="success",
                        output_file=path,
                    )
                )
                logger.info(
                    "レビュー再出力完了: job_id=%s 出力ファイル=%s",
                    job.job_id,
                    path,
                )
            except Exception as e:
                logger.warning(
                    "レビュー再出力失敗: job_id=%s エラー=%s",
                    job.job_id,
                    e,
                )
                new_results.append(
                    TemplateApplicationResult(
                        template_name=entry.template_name,
                        status="failed",
                        error_message=str(e),
                    )
                )
        job.template_results = new_results

    def approve_review(
        self,
        job_id: str,
        corrected_by_template: dict[str, dict[str, Any]] | None = None,
    ) -> tuple[bool, str]:
        """承認して出力・processed へ移動・印刷キュー投入。"""
        job = self._review_jobs.get(job_id)
        if job is None:
            return False, "ジョブが見つかりません"
        if corrected_by_template:
            job.user_corrected_result.update(corrected_by_template)
        ok, reasons = self.validate_review_job_for_approval(job)
        if not ok:
            return False, "承認できません:\n" + "\n".join(reasons)
        try:
            self.export_corrected_job(job)
        except Exception as e:
            return False, str(e)
        failures = [r for r in job.template_results if r.status == "failed"]
        if failures:
            return False, "出力に失敗したテンプレートがあります"
        job.review_status = ReviewStatus.APPROVED
        job.review_required = False
        job.reviewed_at = datetime.now()
        output_paths = [
            r.output_file
            for r in job.template_results
            if r.status == "success" and r.output_file is not None
        ]
        try:
            self._review_history_store.save_approved(job, output_paths)
        except Exception as e:
            logger.warning("レビュー履歴の保存に失敗しました (承認): %s", e)
        self._move_to_processed(job)
        self._enqueue_print_jobs(job)
        self._review_store.delete_job(job_id)
        del self._review_jobs[job_id]
        self._emit_review_count()
        logger.info(
            "レビュー承認: job_id=%s template_set=%s 処理完了",
            job.job_id,
            job.template_set_name,
        )
        return True, ""

    def reject_review(self, job_id: str, reason: str = "") -> tuple[bool, str]:
        """却下して failed フォルダへ移動。"""
        job = self._review_jobs.get(job_id)
        if job is None:
            return False, "ジョブが見つかりません"
        job.review_status = ReviewStatus.REJECTED
        job.review_required = False
        job.reviewed_at = datetime.now()
        if reason.strip():
            job.review_reasons = [*job.review_reasons, f"却下: {reason.strip()}"]
        try:
            self._review_history_store.save_rejected(job, reason)
        except Exception as e:
            logger.warning("レビュー履歴の保存に失敗しました (却下): %s", e)
        self._move_to_failed(job)
        self._review_store.delete_job(job_id)
        del self._review_jobs[job_id]
        self._emit_review_count()
        reason_disp = reason.strip() if reason.strip() else "(なし)"
        logger.info(
            "レビュー却下: job_id=%s template_set=%s 理由=%s",
            job.job_id,
            job.template_set_name,
            reason_disp,
        )
        return True, ""

    def _reload_templates(self) -> None:
        """テンプレートとセットを全て読み込み直す。"""
        from pathlib import Path as P

        bundled_templates = P(__file__).parent.parent.parent / "templates"
        bundled_sets = P(__file__).parent.parent.parent / "template_sets"
        user_templates = get_user_templates_dir()
        user_sets = get_user_template_sets_dir()

        self._templates = load_all_templates([bundled_templates, user_templates])
        self._template_sets = load_all_template_sets([bundled_sets, user_sets])
        logger.info(
            "テンプレート %d 件, セット %d 件を読み込みました",
            len(self._templates),
            len(self._template_sets),
        )

    def start_watching(self) -> OCRWorker:
        """フォルダ監視と OCR ワーカーを開始する。"""
        folders = self._settings.folders
        folders.input_root.mkdir(parents=True, exist_ok=True)
        folders.output_root.mkdir(parents=True, exist_ok=True)
        folders.failed_folder.mkdir(parents=True, exist_ok=True)
        folders.processed_folder.mkdir(parents=True, exist_ok=True)

        self._reload_templates()

        self._watcher = FolderWatcher(
            watch_dir=folders.input_root,
            on_new_file=self._on_new_file,
        )
        self._watcher.start()

        self._ocr_worker = OCRWorker(
            job_queue=self._job_queue,
            ocr_engine=self._ocr_engine,
            template_engine=self._template_engine,
            templates=self._templates,
            template_sets=self._template_sets,
            retry_settings=self._settings.retry,
            license_key_getter=self._license_manager.get_active_key,
            output_root=str(folders.output_root),
        )
        self._ocr_worker.job_completed.connect(self._on_job_completed)
        self._ocr_worker.job_failed.connect(self._on_job_failed)
        self._ocr_worker.start()

        self._print_worker = PrintWorker(
            print_queue=self._print_queue,
            printer=self._printer,
        )
        self._print_worker.start()

        logger.info("監視を開始しました")
        return self._ocr_worker

    def stop_watching(self) -> None:
        """フォルダ監視と全ワーカーを停止する。"""
        if self._watcher:
            self._watcher.stop()
            self._watcher = None

        if self._ocr_worker:
            self._ocr_worker.stop()
            self._ocr_worker.wait(5000)
            self._ocr_worker = None

        if self._print_worker:
            self._print_worker.stop()
            self._print_worker.wait(5000)
            self._print_worker = None

        logger.info("監視を停止しました")

    @property
    def is_watching(self) -> bool:
        """監視中かどうかを返す。"""
        return self._watcher is not None and self._watcher.is_running

    def _on_new_file(self, file_path: Path) -> None:
        """新規ファイル検知時のコールバック。"""
        subfolder = self._get_relative_subfolder(file_path)
        set_name = self._settings.folders.subfolder_to_set.get(subfolder)

        if set_name is None:
            logger.warning(
                "サブフォルダに対応するテンプレートセットが未設定: %s", subfolder
            )
            return

        job = Job(
            job_id=generate_job_id(),
            source_file=file_path,
            template_set_name=set_name,
        )
        self._job_queue.put(job)
        logger.info("ジョブを投入: %s (セット: %s)", file_path.name, set_name)

    def _get_relative_subfolder(self, file_path: Path) -> str:
        """入力ルートからの相対サブフォルダ名を返す。"""
        try:
            relative = file_path.parent.relative_to(self._settings.folders.input_root)
            return str(relative)
        except ValueError:
            return file_path.parent.name

    def _on_job_completed(self, job: Job) -> None:
        """ジョブ完了時 — レビュー待ちなら保持、それ以外は processed + 印刷。"""
        if job.review_required and job.review_status == ReviewStatus.PENDING:
            self._review_jobs[job.job_id] = job
            self._review_store.save_job(job)
            self._emit_review_count()
            logger.info("レビュー待ちに登録: %s", job.job_id)
            return
        self._move_to_processed(job)
        self._enqueue_print_jobs(job)

    def _on_job_failed(self, job: Job) -> None:
        """ジョブ失敗時 — 失敗フォルダへ移動。"""
        if job.status == JobStatus.PARTIAL_SUCCESS:
            self._enqueue_print_jobs(job)
        self._move_to_failed(job)

    def _move_to_processed(self, job: Job) -> None:
        """処理済み画像を処理済みフォルダへ移動。"""
        dest = self._settings.folders.processed_folder / job.source_file.name
        try:
            shutil.move(str(job.source_file), str(dest))
            logger.info("処理済みフォルダへ移動: %s", dest)
        except Exception:
            logger.exception("処理済み移動失敗: %s", job.source_file)

    def _move_to_failed(self, job: Job) -> None:
        """失敗画像を失敗フォルダへ移動。"""
        dest = self._settings.folders.failed_folder / job.source_file.name
        try:
            shutil.move(str(job.source_file), str(dest))
            logger.info("失敗フォルダへ移動: %s", dest)
        except Exception:
            logger.exception("失敗フォルダ移動失敗: %s", job.source_file)

    def _enqueue_print_jobs(self, job: Job) -> None:
        """印刷対象のテンプレート結果を印刷キューに投入する。"""
        template_set = self._template_sets.get(job.template_set_name)
        if not template_set:
            return

        entry_map = {e.template_name: e for e in template_set.entries}
        for result in job.template_results:
            if result.status != "success" or result.output_file is None:
                continue
            entry = entry_map.get(result.template_name)
            if entry and entry.auto_print:
                self._print_queue.put(
                    PrintJob(
                        file_path=result.output_file,
                        printer_name=entry.printer_name,
                        copies=self._settings.printer.copies,
                    )
                )
