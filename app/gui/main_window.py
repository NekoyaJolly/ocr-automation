"""メインウィンドウ — タブ構成、監視状態表示、開始/停止ボタン。"""

from datetime import datetime

from PySide6.QtCore import QTimer, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.controllers.app_controller import AppController
from app.core.license_manager import LicenseManager
from app.core.ocr_engine import GeminiBackendEngine
from app.gui.folder_settings import FolderSettingsWidget
from app.gui.license_settings import LicenseSettingsWidget
from app.gui.log_viewer import LogViewer
from app.gui.printer_settings import PrinterSettingsWidget
from app.gui.qt_log_handler import attach_controller_logs_to_viewer
from app.gui.review_editor import ReviewEditorDialog
from app.gui.review_queue import ReviewQueueWidget
from app.gui.template_editor import TemplateEditorWidget
from app.gui.template_set_editor import TemplateSetEditorWidget
from app.infrastructure.http_client import HttpClient
from app.infrastructure.keyring_store import KeyringStore
from app.infrastructure.logger import get_logger
from app.infrastructure.settings_store import SettingsStore

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """アプリケーションのメインウィンドウ。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("OCR Automation")
        self.setMinimumSize(900, 650)

        self._settings_store = SettingsStore()
        settings = self._settings_store.load()

        self._http_client = HttpClient(
            base_url=settings.backend.base_url,
            timeout=settings.backend.timeout_seconds,
        )
        self._keyring_store = KeyringStore()
        self._license_manager = LicenseManager(self._keyring_store, self._http_client)
        self._ocr_engine = GeminiBackendEngine(self._http_client)
        self._controller = AppController(
            settings_store=self._settings_store,
            ocr_engine=self._ocr_engine,
            license_manager=self._license_manager,
        )

        self._setup_ui()
        self._setup_statusbar()
        self._load_settings_to_ui()

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_status)
        self._status_timer.start(2000)

    def _setup_ui(self) -> None:
        central = QWidget()
        main_layout = QVBoxLayout(central)

        control_row = QHBoxLayout()
        self._status_indicator = QLabel("● 停止中")
        self._status_indicator.setStyleSheet("font-size: 16px; font-weight: bold; color: #888;")
        control_row.addWidget(self._status_indicator)
        control_row.addStretch()

        self._start_btn = QPushButton("監視開始")
        self._start_btn.setMinimumWidth(120)
        self._start_btn.clicked.connect(self._toggle_watching)
        control_row.addWidget(self._start_btn)

        save_btn = QPushButton("設定保存")
        save_btn.clicked.connect(self._save_settings)
        control_row.addWidget(save_btn)

        main_layout.addLayout(control_row)

        self._tabs = QTabWidget()

        self._log_viewer = LogViewer()
        self._controller_log_emitter = attach_controller_logs_to_viewer(
            self,
            self._log_viewer,
        )
        self._tabs.addTab(self._log_viewer, "ログ")

        self._review_queue = ReviewQueueWidget(self._controller)
        self._tabs.insertTab(1, self._review_queue, "レビュー (0)")
        self._review_queue.open_review_requested.connect(self._open_review_editor)
        self._controller.review_queue_count_changed.connect(self._update_review_tab_title)
        self._update_review_tab_title(self._controller.pending_review_count)

        self._folder_settings = FolderSettingsWidget()
        self._tabs.addTab(self._folder_settings, "フォルダ設定")

        self._license_settings = LicenseSettingsWidget(self._license_manager)
        self._tabs.addTab(self._license_settings, "ライセンス")

        self._template_editor = TemplateEditorWidget()
        self._tabs.addTab(self._template_editor, "テンプレート")

        self._set_editor = TemplateSetEditorWidget()
        self._tabs.addTab(self._set_editor, "テンプレートセット")

        self._printer_settings = PrinterSettingsWidget()
        self._tabs.addTab(self._printer_settings, "プリンタ")

        main_layout.addWidget(self._tabs, stretch=1)
        self.setCentralWidget(central)

    def _setup_statusbar(self) -> None:
        status_bar = QStatusBar()
        self._last_processed_label = QLabel("最終処理: —")
        self._file_count_label = QLabel("処理数: 0")
        status_bar.addPermanentWidget(self._file_count_label)
        status_bar.addPermanentWidget(self._last_processed_label)
        self.setStatusBar(status_bar)
        self._processed_count = 0

    def _load_settings_to_ui(self) -> None:
        settings = self._controller.settings
        available_sets = list(self._controller.template_sets.keys())
        self._folder_settings.load_settings(settings.folders, available_sets)
        self._license_settings.refresh_info()

    @Slot()
    def _toggle_watching(self) -> None:
        if self._controller.is_watching:
            self._stop_watching()
        else:
            self._start_watching()

    def _start_watching(self) -> None:
        self._save_settings()

        if not self._license_manager.has_key():
            QMessageBox.warning(
                self,
                "ライセンス未設定",
                "ライセンスキーを設定してください。\n「ライセンス」タブから入力できます。",
            )
            self._tabs.setCurrentWidget(self._license_settings)
            return

        try:
            ocr_worker = self._controller.start_watching()
            ocr_worker.log_message.connect(self._log_viewer.append_log)
            ocr_worker.job_completed.connect(self._on_job_done)
            ocr_worker.job_failed.connect(self._on_job_done)
            self._update_watching_state(True)
            self._log_viewer.append_log("監視を開始しました")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"監視の開始に失敗しました:\n{e}")

    def _stop_watching(self) -> None:
        self._controller.stop_watching()
        self._update_watching_state(False)
        self._log_viewer.append_log("監視を停止しました")

    def _update_watching_state(self, running: bool) -> None:
        if running:
            self._status_indicator.setText("● 動作中")
            self._status_indicator.setStyleSheet(
                "font-size: 16px; font-weight: bold; color: #2ecc71;"
            )
            self._start_btn.setText("監視停止")
        else:
            self._status_indicator.setText("● 停止中")
            self._status_indicator.setStyleSheet(
                "font-size: 16px; font-weight: bold; color: #888;"
            )
            self._start_btn.setText("監視開始")

    @Slot()
    def _save_settings(self) -> None:
        settings = self._controller.settings
        settings.folders = self._folder_settings.get_settings()
        self._controller.save_settings()
        self._log_viewer.append_log("設定を保存しました")

    @Slot(int)
    def _update_review_tab_title(self, count: int) -> None:
        idx = self._tabs.indexOf(self._review_queue)
        if idx >= 0:
            self._tabs.setTabText(idx, f"レビュー ({count})")

    @Slot(str)
    def _open_review_editor(self, job_id: str) -> None:
        try:
            dlg = ReviewEditorDialog(self._controller, job_id, self)
            dlg.finished.connect(self._review_queue.refresh)
            dlg.show()
        except ValueError as e:
            QMessageBox.warning(self, "レビュー", str(e))

    @Slot(object)
    def _on_job_done(self, job: object) -> None:
        self._processed_count += 1
        self._file_count_label.setText(f"処理数: {self._processed_count}")
        self._last_processed_label.setText(
            f"最終処理: {datetime.now().strftime('%H:%M:%S')}"
        )

    @Slot()
    def _update_status(self) -> None:
        running = self._controller.is_watching
        if running:
            self._status_indicator.setText("● 動作中")
            self._status_indicator.setStyleSheet(
                "font-size: 16px; font-weight: bold; color: #2ecc71;"
            )
        else:
            if self._start_btn.text() == "監視停止":
                self._update_watching_state(False)

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        """ウィンドウ閉じ時にワーカーを停止する。"""
        self._controller.stop_watching()
        self._http_client.close()
        super().closeEvent(event)
