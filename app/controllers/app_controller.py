"""アプリケーション全体を統括するコントローラ。

watcher → queue → OCRWorker の連携を管理し、GUI に Signal で通知する。
watchdog スレッドと Qt イベントループの疎結合を QTimer ポーリングで実現する。
"""

import logging
import queue
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from app.controllers.ocr_worker import OCRWorker
from app.core.ocr_engine import OCREngine
from app.core.watcher import FolderWatcher
from app.models.settings_model import AppSettings
from app.models.template_model import Template, TemplateSet
import yaml

logger = logging.getLogger(__name__)


class AppController(QObject):
    """アプリ全体の状態管理と Worker 統括。

    Signals:
        monitoring_started: 監視開始時に発火
        monitoring_stopped: 監視停止時に発火
        job_started(str): OCR 開始時にファイル名を通知
        job_completed(str, str): OCR 完了時に (ファイル名, 出力パス) を通知
        job_failed(str, str): OCR 失敗時に (ファイル名, エラーメッセージ) を通知
        log_message(str, str): ログ通知 (level, message)
        error_occurred(str): 致命的エラーメッセージ
    """

    monitoring_started = Signal()
    monitoring_stopped = Signal()
    job_started = Signal(str)
    job_completed = Signal(str, str)
    job_failed = Signal(str, str)
    log_message = Signal(str, str)
    error_occurred = Signal(str)

    _POLL_INTERVAL_MS = 100

    def __init__(self, settings: AppSettings, ocr_engine: OCREngine) -> None:
        """コントローラを初期化する。

        Args:
            settings: アプリケーション設定
            ocr_engine: OCR エンジンインスタンス
        """
        super().__init__()
        self._settings = settings
        self._ocr_engine = ocr_engine

        self._watcher: FolderWatcher | None = None
        self._ocr_worker: OCRWorker | None = None
        self._file_queue: queue.Queue[Path] = queue.Queue()
        self._processed_paths: set[str] = set()

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self._POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_queue)

        self._is_monitoring = False

    @property
    def is_monitoring(self) -> bool:
        """監視中かどうか。"""
        return self._is_monitoring

    @property
    def settings(self) -> AppSettings:
        """現在のアプリケーション設定。"""
        return self._settings

    @settings.setter
    def settings(self, value: AppSettings) -> None:
        self._settings = value

    def start_monitoring(self) -> None:
        """フォルダ監視と OCR ワーカーを開始する。

        Raises:
            error_occurred Signal: フォルダが未設定の場合
        """
        folders = self._settings.folders
        if not folders.input_root or not folders.output_root or not folders.failed_folder:
            self.error_occurred.emit(
                "入力フォルダ・出力フォルダ・失敗フォルダを全て設定してください。"
            )
            return

        input_root = folders.input_root
        output_root = folders.output_root
        failed_folder = folders.failed_folder

        for d in [input_root, output_root, failed_folder]:
            d.mkdir(parents=True, exist_ok=True)

        try:
            self._file_queue = queue.Queue()
            self._processed_paths.clear()

            self._watcher = FolderWatcher(input_root, self._file_queue)
            self._watcher.start()

            self._ocr_worker = OCRWorker(
                self._ocr_engine, output_root, failed_folder, self._settings
            )
            self._ocr_worker.job_started.connect(self.job_started)
            self._ocr_worker.job_completed.connect(self.job_completed)
            self._ocr_worker.job_failed.connect(self.job_failed)
            self._ocr_worker.start()

            self._poll_timer.start()
            self._is_monitoring = True
            self.monitoring_started.emit()
            logger.info("監視を開始しました")
        except Exception as e:
            logger.exception("監視の開始に失敗しました")
            self.error_occurred.emit(f"監視の開始に失敗しました: {e}")
            self.stop_monitoring()

    def stop_monitoring(self) -> None:
        """フォルダ監視と OCR ワーカーを停止する。"""
        self._poll_timer.stop()

        if self._watcher is not None:
            try:
                self._watcher.stop()
            except Exception:
                logger.exception("watcher 停止中にエラー")
            self._watcher = None

        if self._ocr_worker is not None:
            self._ocr_worker.request_stop()
            self._ocr_worker.wait(5000)
            self._ocr_worker = None

        self._is_monitoring = False
        self.monitoring_stopped.emit()
        logger.info("監視を停止しました")

    def update_folders(self, settings: AppSettings) -> None:
        """フォルダ設定を更新する。監視中の場合は OCRWorker のパスも更新する。

        Args:
            settings: 更新された設定
        """
        self._settings = settings

        if self._ocr_worker is not None and settings.folders.output_root:
            self._ocr_worker.output_dir = settings.folders.output_root
        if self._ocr_worker is not None and settings.folders.failed_folder:
            self._ocr_worker.failed_dir = settings.folders.failed_folder
        if self._ocr_worker is not None:
            self._ocr_worker.settings = settings

    def _poll_queue(self) -> None:
        """QTimer から呼ばれ、file_queue を消化して OCRWorker に渡す。"""
        batch_limit = 10
        for _ in range(batch_limit):
            try:
                path = self._file_queue.get_nowait()
            except queue.Empty:
                break

            resolved = str(path.resolve())
            if resolved in self._processed_paths:
                logger.debug(f"処理済みファイルをスキップ: {path.name}")
                continue

            self._processed_paths.add(resolved)
            logger.info(f"新しい画像を検出: {path.name}")
            if self._ocr_worker is not None:
                self._ocr_worker.enqueue(path)

    def get_available_templates(self) -> list[str]:
        """利用可能なテンプレート名（拡張子なし）のリストを取得する。"""
        from app.infrastructure.paths import get_user_templates_dir

        templates = set()
        # 1. ユーザーフォルダからスキャン
        u_dir = get_user_templates_dir()
        if u_dir.exists():
            for p in u_dir.glob("*.yaml"):
                templates.add(p.stem)
        # 2. プロジェクト内蔵フォルダからスキャン
        p_dir = Path(__file__).resolve().parent.parent.parent / "templates"
        if p_dir.exists():
            for p in p_dir.glob("*.yaml"):
                templates.add(p.stem)

        return sorted(list(templates))

    def load_template_by_name(self, name: str) -> Template | None:
        """指定された名前のテンプレート定義をロードする。"""
        from app.controllers.ocr_worker import load_template
        return load_template(name)

    def save_template(self, template: Template) -> None:
        """テンプレートをユーザー定義テンプレートフォルダに保存する。"""
        from app.infrastructure.paths import get_user_templates_dir

        u_dir = get_user_templates_dir()
        u_dir.mkdir(parents=True, exist_ok=True)
        file_path = u_dir / f"{template.name}.yaml"
        
        data = template.model_dump()
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        logger.info(f"テンプレートを保存しました: {file_path}")

    def delete_template(self, name: str) -> None:
        """指定されたテンプレートファイルを削除する。"""
        from app.infrastructure.paths import get_user_templates_dir

        file_path = get_user_templates_dir() / f"{name}.yaml"
        if file_path.exists():
            file_path.unlink()
            logger.info(f"テンプレートを削除しました: {file_path}")

    def get_available_template_sets(self) -> list[str]:
        """利用可能なテンプレートセット名（拡張子なし）のリストを取得する。"""
        from app.infrastructure.paths import get_user_template_sets_dir

        sets = set()
        # 1. ユーザーフォルダ
        u_dir = get_user_template_sets_dir()
        if u_dir.exists():
            for p in u_dir.glob("*.yaml"):
                sets.add(p.stem)
        # 2. プロジェクトフォルダ
        p_dir = Path(__file__).resolve().parent.parent.parent / "template_sets"
        if p_dir.exists():
            for p in p_dir.glob("*.yaml"):
                sets.add(p.stem)

        return sorted(list(sets))

    def load_template_set_by_name(self, name: str) -> TemplateSet | None:
        """指定された名前のテンプレートセット定義をロードする。"""
        from app.controllers.ocr_worker import load_template_set
        return load_template_set(name)

    def save_template_set(self, template_set: TemplateSet) -> None:
        """テンプレートセットをユーザー定義テンプレートセットフォルダに保存する。"""
        from app.infrastructure.paths import get_user_template_sets_dir

        u_dir = get_user_template_sets_dir()
        u_dir.mkdir(parents=True, exist_ok=True)
        file_path = u_dir / f"{template_set.name}.yaml"
        
        data = template_set.model_dump()
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        logger.info(f"テンプレートセットを保存しました: {file_path}")

    def delete_template_set(self, name: str) -> None:
        """指定されたテンプレートセットファイルを削除する。"""
        from app.infrastructure.paths import get_user_template_sets_dir

        file_path = get_user_template_sets_dir() / f"{name}.yaml"
        if file_path.exists():
            file_path.unlink()
            logger.info(f"テンプレートセットを削除しました: {file_path}")
