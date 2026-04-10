"""OCRWorker — QThread でバックグラウンド OCR 処理を行うワーカー。"""

import queue
import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.core.ocr_engine import OCREngine
from app.core.template import TemplateEngine, format_available_keys_hint
from app.exceptions import LicenseError, TemplateConfigError
from app.infrastructure.logger import get_logger
from app.models.job_model import Job, JobStatus
from app.models.settings_model import RetrySettings
from app.models.template_model import (
    Template,
    TemplateApplicationResult,
    TemplateSet,
    TemplateSetEntry,
)

logger = get_logger(__name__)


class OCRWorker(QThread):
    """バックグラウンドで OCR + テンプレート適用を行うワーカースレッド。

    Signals:
        job_started: ジョブ処理開始時に発火 (job_id)。
        job_completed: ジョブ完了時に発火 (Job)。
        job_failed: ジョブ失敗時に発火 (Job)。
        log_message: ログメッセージ発火 (message)。
    """

    job_started = Signal(str)
    job_completed = Signal(object)
    job_failed = Signal(object)
    log_message = Signal(str)

    def __init__(
        self,
        job_queue: "queue.Queue[Job]",
        ocr_engine: OCREngine,
        template_engine: TemplateEngine,
        templates: dict[str, Template],
        template_sets: dict[str, TemplateSet],
        retry_settings: RetrySettings,
        license_key_getter: "callable",
        output_root: "str | None" = None,
    ) -> None:
        super().__init__()
        self._queue = job_queue
        self._ocr_engine = ocr_engine
        self._template_engine = template_engine
        self._templates = templates
        self._template_sets = template_sets
        self._retry = retry_settings
        self._get_license_key = license_key_getter
        self._output_root_str = output_root
        self._running = True

    def run(self) -> None:
        """キューからジョブを取り出して処理するメインループ。"""
        logger.info("OCRWorker 開始")
        while self._running:
            try:
                job = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            self._process_job(job)

        logger.info("OCRWorker 停止")

    def stop(self) -> None:
        """ワーカーを停止する。"""
        self._running = False

    def _process_job(self, job: Job) -> None:
        """1つのジョブを処理する。"""
        job.status = JobStatus.PROCESSING
        self.job_started.emit(job.job_id)
        self.log_message.emit(f"処理開始: {job.source_file.name} (セット: {job.template_set_name})")

        template_set = self._template_sets.get(job.template_set_name)
        if template_set is None:
            job.status = JobStatus.FAILED
            avail = format_available_keys_hint(list(self._template_sets.keys()))
            self.log_message.emit(
                f"エラー: テンプレートセットが見つかりません: キー {job.template_set_name!r}。"
                f" 利用可能なセットキー: [{avail}]"
            )
            self.job_failed.emit(job)
            return

        try:
            license_key = self._get_license_key()
        except Exception as e:
            job.status = JobStatus.FAILED
            self.log_message.emit(f"エラー: ライセンスキー取得失敗 — {e}")
            self.job_failed.emit(job)
            return

        output_root = (
            Path(self._output_root_str)
            if self._output_root_str
            else Path.home() / "OCR" / "出力"
        )

        results: list[TemplateApplicationResult] = []
        for entry in template_set.entries:
            if not entry.enabled:
                continue
            template = self._templates.get(entry.template_name)
            if template is None:
                avail = format_available_keys_hint(list(self._templates.keys()))
                results.append(
                    TemplateApplicationResult(
                        template_name=entry.template_name,
                        status="failed",
                        error_message=(
                            f"テンプレート未定義: キー {entry.template_name!r}。"
                            f" 利用可能なテンプレートキー: [{avail}]"
                        ),
                    )
                )
                continue

            result = self._apply_with_retry(
                entry=entry,
                template=template,
                image_path=job.source_file,
                output_root=output_root,
                license_key=license_key,
            )
            results.append(result)
            status_str = "成功" if result.status == "success" else "失敗"
            self.log_message.emit(f"  {template.name}: {status_str}")

        job.template_results = results
        successes = sum(1 for r in results if r.status == "success")
        failures = sum(1 for r in results if r.status == "failed")

        if failures == 0:
            job.status = JobStatus.COMPLETED
        elif successes > 0:
            job.status = JobStatus.PARTIAL_SUCCESS
        else:
            job.status = JobStatus.FAILED

        from datetime import datetime

        job.completed_at = datetime.now()
        self.log_message.emit(
            f"処理完了: {job.source_file.name} — 成功={successes}, 失敗={failures}"
        )

        if job.status == JobStatus.FAILED:
            self.job_failed.emit(job)
        else:
            self.job_completed.emit(job)

    def _apply_with_retry(
        self,
        entry: TemplateSetEntry,
        template: Template,
        image_path: Path,
        output_root: Path,
        license_key: str,
    ) -> TemplateApplicationResult:
        """リトライ付きでテンプレートを適用する。"""

        import httpx

        max_retries = self._retry.max_retries
        backoff = self._retry.initial_backoff_seconds
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                result = self._template_engine._apply_single_entry(
                    ocr_engine=self._ocr_engine,
                    image_path=image_path,
                    entry=entry,
                    template=template,
                    output_root=output_root,
                    license_key=license_key,
                )
                if result.status == "success":
                    result.retry_count = attempt
                    return result
                last_error = Exception(result.error_message)
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
            except (LicenseError, TemplateConfigError) as e:
                return TemplateApplicationResult(
                    template_name=entry.template_name,
                    status="failed",
                    error_message=str(e),
                    retry_count=attempt,
                )
            except Exception as e:
                last_error = e

            if attempt < max_retries:
                self.log_message.emit(
                    f"  リトライ {attempt + 1}/{max_retries}: {template.name}"
                )
                time.sleep(backoff)
                backoff *= self._retry.backoff_multiplier

        return TemplateApplicationResult(
            template_name=entry.template_name,
            status="failed",
            error_message=str(last_error) if last_error else "不明なエラー",
            retry_count=max_retries,
        )
