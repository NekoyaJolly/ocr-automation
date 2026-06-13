"""QThread ベースの OCR ワーカー。

バックグラウンドスレッドで OCR 処理を実行し、結果を Signal で通知する。
Phase 3 では、テンプレートセットをロードし、マッピング抽出および複数フォーマットファイル出力、
さらに指数バックオフ付きリトライおよび部分成功制御を実行する。
"""

import logging
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue

import yaml
from PySide6.QtCore import QThread, Signal

from app.core.ocr_engine import OCREngine
from app.core.template import TemplateEngine
from app.exceptions import OCRAutomationError
from app.models.job_model import TemplateApplicationResult
from app.models.settings_model import AppSettings
from app.models.template_model import Template, TemplateSet, TemplateSetEntry
from app.models.ocr_result_model import OCRResult

logger = logging.getLogger(__name__)


def load_template_set(name: str) -> TemplateSet | None:
    """テンプレートセット定義（YAML）をロードする。"""
    from app.infrastructure.paths import get_user_template_sets_dir

    paths_to_try = [
        get_user_template_sets_dir() / f"{name}.yaml",
        Path(__file__).resolve().parent.parent.parent / "template_sets" / f"{name}.yaml",
    ]
    for p in paths_to_try:
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    return TemplateSet.model_validate(data)
            except Exception as e:
                logger.error(f"テンプレートセットのロード失敗 ({p}): {e}")
    return None


def load_template(name: str) -> Template | None:
    """テンプレート定義（YAML）をロードする。"""
    from app.infrastructure.paths import get_user_templates_dir

    paths_to_try = [
        get_user_templates_dir() / f"{name}.yaml",
        Path(__file__).resolve().parent.parent.parent / "templates" / f"{name}.yaml",
    ]
    for p in paths_to_try:
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    return Template.model_validate(data)
            except Exception as e:
                logger.error(f"テンプレートのロード失敗 ({p}): {e}")
    return None


class OCRWorker(QThread):
    """OCR 処理を別スレッドで実行するワーカー。

    Signals:
        job_started(str): OCR 開始時にファイル名を通知
        job_completed(str, str): OCR 完了時に (ファイル名, 代表的な出力パス) を通知
        job_failed(str, str): OCR 失敗時に (ファイル名, エラーメッセージ) を通知
    """

    job_started = Signal(str)
    job_completed = Signal(str, str)
    job_failed = Signal(str, str)

    def __init__(
        self,
        ocr_engine: OCREngine,
        output_dir: Path,
        failed_dir: Path,
        settings: AppSettings | None = None,
    ) -> None:
        """ワーカーを初期化する。

        Args:
            ocr_engine: OCR エンジンインスタンス
            output_dir: OCR 結果の出力先ディレクトリ
            failed_dir: 失敗時のコピー先ディレクトリ
            settings: アプリケーション設定
        """
        super().__init__()
        self._engine = ocr_engine
        self._output_dir = output_dir
        self._failed_dir = failed_dir
        self._settings = settings
        self._queue: Queue[Path] = Queue()
        self._stop_requested = False

    @property
    def output_dir(self) -> Path:
        """出力先ディレクトリ。"""
        return self._output_dir

    @output_dir.setter
    def output_dir(self, value: Path) -> None:
        self._output_dir = value

    @property
    def failed_dir(self) -> Path:
        """失敗フォルダ。"""
        return self._failed_dir

    @failed_dir.setter
    def failed_dir(self, value: Path) -> None:
        self._failed_dir = value

    @property
    def settings(self) -> AppSettings | None:
        """アプリケーション設定。"""
        return self._settings

    @settings.setter
    def settings(self, value: AppSettings) -> None:
        self._settings = value

    def enqueue(self, image_path: Path) -> None:
        """OCR ジョブをキューに追加する。

        Args:
            image_path: 処理する画像ファイルのパス
        """
        self._queue.put(image_path)

    def request_stop(self) -> None:
        """ワーカーの停止を要求する。"""
        self._stop_requested = True

    def run(self) -> None:
        """ワーカーのメインループ。キューからジョブを取り出して処理する。"""
        logger.info("OCR ワーカーを開始しました")
        while not self._stop_requested:
            try:
                image_path = self._queue.get(timeout=0.5)
            except Empty:
                continue

            self._process_job(image_path)

        logger.info("OCR ワーカーを停止しました")

    def _process_job(self, image_path: Path) -> None:
        """1 つの画像ファイルを OCR 処理し、テンプレートセットを適用して出力する。"""
        file_name = image_path.name
        self.job_started.emit(file_name)
        logger.info(f"OCR 処理を開始: {file_name}")

        # 1. 紐付けられたテンプレートセットを特定
        subfolder_name = image_path.parent.name
        subfolder_to_set = {}
        if self._settings and self._settings.folders:
            subfolder_to_set = self._settings.folders.subfolder_to_set

        template_set_name = subfolder_to_set.get(subfolder_name)
        if not template_set_name:
            logger.info(
                f"スキップ: サブフォルダ '{subfolder_name}' はテンプレートセットと紐付けられていません。"
            )
            # 紐付けがない場合は無視（完了通知などもせず正常終了）
            return

        # 2. テンプレートセット定義の読み込み
        template_set = load_template_set(template_set_name)
        if not template_set:
            error_msg = f"テンプレートセットが見つかりません: {template_set_name}"
            self._handle_failure(image_path, error_msg)
            self.job_failed.emit(file_name, error_msg)
            return

        # 3. OCR 処理実行
        try:
            ocr_result = self._engine.process(image_path)
        except OCRAutomationError as e:
            error_msg = str(e)
            self._handle_failure(image_path, error_msg)
            self.job_failed.emit(file_name, error_msg)
            return
        except Exception as e:
            error_msg = f"予期しないエラー: {e}"
            logger.exception(f"OCR 処理中に予期しないエラーが発生: {file_name}")
            self._handle_failure(image_path, error_msg)
            self.job_failed.emit(file_name, error_msg)
            return

        # 4. 各テンプレートの適用
        from app.core.template import TemplateEngine

        template_engine = TemplateEngine()
        results: list[TemplateApplicationResult] = []
        has_success = False
        has_failure = False

        for entry in template_set.entries:
            if not entry.enabled:
                continue

            template = load_template(entry.template_name)
            if not template:
                msg = f"テンプレート定義が見つかりません: {entry.template_name}"
                logger.error(msg)
                results.append(
                    TemplateApplicationResult(
                        template_name=entry.template_name,
                        status="failed",
                        error_message=msg,
                    )
                )
                has_failure = True
                continue

            # リトライ付き適用・出力
            result = self._apply_template_with_retry(
                ocr_result, entry, template, template_engine
            )
            results.append(result)
            if result.status == "success":
                has_success = True
            else:
                has_failure = True

        # 5. 後処理（部分成功・全成功・全失敗の判定と集約）
        if has_success and not has_failure:
            logger.info(f"ジョブ完了 (全成功): {file_name}")
            success_output = next(
                (str(r.output_file) for r in results if r.status == "success"), ""
            )
            self.job_completed.emit(file_name, success_output)
        elif has_success and has_failure:
            logger.warning(f"ジョブ一部完了 (部分成功): {file_name}")
            failed_templates = [r.template_name for r in results if r.status == "failed"]
            errors = [
                f"{r.template_name}: {r.error_message}"
                for r in results
                if r.status == "failed"
            ]
            error_summary = "\n".join(errors)
            self._handle_partial_failure(image_path, error_summary, failed_templates)

            success_output = next(
                (str(r.output_file) for r in results if r.status == "success"), ""
            )
            self.job_completed.emit(file_name, success_output)
        else:
            logger.error(f"ジョブ失敗 (全失敗): {file_name}")
            errors = [
                f"{r.template_name}: {r.error_message}"
                for r in results
                if r.status == "failed"
            ]
            error_summary = "\n".join(errors)
            self._handle_failure(image_path, error_summary)
            self.job_failed.emit(file_name, "すべてのテンプレートの処理に失敗しました。")

    def _apply_template_with_retry(
        self,
        ocr_result: OCRResult,
        entry: TemplateSetEntry,
        template: Template,
        template_engine: TemplateEngine,
    ) -> TemplateApplicationResult:
        """1つのテンプレートに対し、指数バックオフによるリトライ付きでデータ抽出・出力処理を行う。"""
        # リトライ設定値の取得
        max_retries = 2
        initial_backoff = 1.0
        backoff_multiplier = 3.0
        if self._settings and self._settings.retry:
            max_retries = self._settings.retry.max_retries
            initial_backoff = self._settings.retry.initial_backoff_seconds
            backoff_multiplier = self._settings.retry.backoff_multiplier

        backoff = initial_backoff
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                # フィールド抽出
                mapped_data = template_engine.apply_single(ocr_result, template)

                # 出力先決定
                output_dir = self._output_dir
                if entry.output_subfolder:
                    output_dir = output_dir / entry.output_subfolder
                output_dir.mkdir(parents=True, exist_ok=True)

                # ファイル名決定
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                date_str = datetime.now().strftime("%Y%m%d")
                filename = template.output_filename_pattern.replace("{date}", date_str)
                filename = filename.replace("{timestamp}", timestamp)
                filename = filename.replace("{source_basename}", ocr_result.source_image.stem)
                filename = filename.replace("{template_name}", template.name)

                # 残ったプレースホルダーの安全な除去
                filename = re.sub(r"\{.*?\}", "", filename)
                output_path = output_dir / filename

                # ファイル出力の実行
                from app.core.exporter import ExporterFactory

                exporter = ExporterFactory.create(template.output_format)
                exporter.export(mapped_data, template, output_path)

                logger.info(
                    f"テンプレート適用成功: {template.name} -> {output_path.name} (試行: {attempt + 1})"
                )

                # 自動印刷のトリガー
                if entry.auto_print:
                    self._print_output_file(output_path, entry)

                return TemplateApplicationResult(
                    template_name=template.name,
                    status="success",
                    output_file=output_path,
                    retry_count=attempt,
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    f"テンプレート '{template.name}' 適用失敗 (試行 {attempt + 1}/{max_retries + 1}): {e}"
                )
                if attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= backoff_multiplier

        return TemplateApplicationResult(
            template_name=template.name,
            status="failed",
            error_message=str(last_error),
            retry_count=max_retries,
        )

    def _handle_failure(self, image_path: Path, error_msg: str) -> None:
        """OCR 失敗時、または全テンプレート処理失敗時に元画像をコピーしエラーログを保存する。"""
        logger.error(f"OCR 処理に失敗しました: {image_path.name} - {error_msg}")
        try:
            self._failed_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            dest = self._failed_dir / image_path.name
            if dest.exists():
                dest = self._failed_dir / f"{image_path.stem}_{timestamp}{image_path.suffix}"
            shutil.copy2(image_path, dest)

            error_log_name = f"{image_path.stem}_{timestamp}.error.log"
            error_log_path = self._failed_dir / error_log_name
            error_log_path.write_text(
                f"ファイル: {image_path}\n"
                f"日時: {datetime.now().isoformat()}\n"
                f"エラー: {error_msg}\n",
                encoding="utf-8",
            )
        except Exception:
            logger.exception("失敗フォルダへのコピーに失敗しました")

    def _handle_partial_failure(
        self, image_path: Path, error_msg: str, failed_templates: list[str]
    ) -> None:
        """一部のテンプレートが失敗した場合に元画像をコピーし部分失敗エラーログを保存する。"""
        logger.warning(
            f"一部のテンプレート処理に失敗しました: {image_path.name} - 失敗: {failed_templates}"
        )
        try:
            self._failed_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            dest = self._failed_dir / image_path.name
            if dest.exists():
                dest = self._failed_dir / f"{image_path.stem}_{timestamp}{image_path.suffix}"
            shutil.copy2(image_path, dest)

            error_log_name = f"{image_path.stem}_{timestamp}.partial_error.log"
            error_log_path = self._failed_dir / error_log_name
            error_log_path.write_text(
                f"ファイル: {image_path}\n"
                f"日時: {datetime.now().isoformat()}\n"
                f"失敗テンプレート: {failed_templates}\n"
                f"エラー詳細:\n{error_msg}\n",
                encoding="utf-8",
            )
        except Exception:
            logger.exception("失敗フォルダへの部分失敗ログの保存に失敗しました")

    def _print_output_file(self, output_path: Path, entry: TemplateSetEntry) -> None:
        """生成されたドキュメントファイルを指定プリンタに自動印刷する。"""
        printer_name = entry.printer_name
        copies = 1

        if self._settings and self._settings.printer:
            if not printer_name:
                printer_name = self._settings.printer.default_printer
            copies = self._settings.printer.copies

        try:
            from app.core.printer import get_printer
            printer = get_printer()
            logger.info(
                f"自動印刷を開始します: {output_path.name} -> プリンタ: {printer_name or 'デフォルト'}, 部数: {copies}"
            )
            printer.print_file(output_path, printer_name, copies)
            logger.info(f"自動印刷を送信しました: {output_path.name}")
        except Exception as e:
            # 印刷の失敗はログ出力に留め、ファイル出力は成功しているためジョブ失敗にはしない
            logger.error(f"自動印刷に失敗しました ({output_path.name}): {e}")
