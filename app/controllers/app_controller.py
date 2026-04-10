"""AppController — アプリケーション全体のオーケストレーション。"""

import queue
import shutil
from pathlib import Path

from app.controllers.ocr_worker import OCRWorker
from app.controllers.print_worker import PrintJob, PrintWorker
from app.core.license_manager import LicenseManager
from app.core.ocr_engine import OCREngine
from app.core.printer import Printer, create_printer
from app.core.template import (
    TemplateEngine,
    load_all_template_sets,
    load_all_templates,
)
from app.core.watcher import FolderWatcher
from app.infrastructure.logger import get_logger
from app.infrastructure.paths import get_user_template_sets_dir, get_user_templates_dir
from app.infrastructure.settings_store import SettingsStore
from app.models.job_model import Job, JobStatus
from app.models.settings_model import AppSettings
from app.models.template_model import Template, TemplateSet
from app.utils.helpers import generate_job_id

logger = get_logger(__name__)


class AppController:
    """アプリケーション層の中心。Watcher → Job 投入 → Worker 管理を行う。"""

    def __init__(
        self,
        settings_store: SettingsStore,
        ocr_engine: OCREngine,
        license_manager: LicenseManager,
    ) -> None:
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

    @property
    def settings(self) -> AppSettings:
        return self._settings

    @property
    def templates(self) -> dict[str, Template]:
        return self._templates

    @property
    def template_sets(self) -> dict[str, TemplateSet]:
        return self._template_sets

    def reload_settings(self) -> None:
        """設定ファイルを再読み込みする。"""
        self._settings = self._settings_store.load()

    def save_settings(self) -> None:
        """現在の設定を保存する。"""
        self._settings_store.save(self._settings)

    def _reload_templates(self) -> None:
        """テンプレートとセットを全て読み込み直す。"""
        bundled_templates = Path(__file__).parent.parent.parent / "templates"
        bundled_sets = Path(__file__).parent.parent.parent / "template_sets"
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
        """ジョブ完了時 — 処理済みフォルダへ移動 + 印刷キュー投入。"""
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
