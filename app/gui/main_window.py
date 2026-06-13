"""メインウィンドウ。

アプリケーションの中心となるウィンドウ。
ツールバー（開始/停止ボタン + 状態表示）とタブ（設定/ログ）で構成される。
"""

import logging

from PySide6.QtCore import Qt, Slot, Signal, QThread, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.controllers.app_controller import AppController
from app.gui.folder_settings import FolderSettingsPanel
from app.gui.log_viewer import LogViewer
from app.gui.template_editor import TemplateEditorPanel
from app.gui.template_set_editor import TemplateSetEditorPanel
from app.gui.printer_settings import PrinterSettingsPanel
from app.infrastructure.logger import add_signal_handler
from app.infrastructure.settings_store import SettingsStore
from app.models.settings_model import AppSettings

logger = logging.getLogger(__name__)

_WINDOW_TITLE = "OCR Automation"
_WINDOW_MIN_WIDTH = 700
_WINDOW_MIN_HEIGHT = 480


class UpdateCheckWorker(QThread):
    """バックグラウンドでアップデートを確認するスレッド。"""

    update_found = Signal(dict)

    def run(self) -> None:
        try:
            from app.core.updater import check_for_update
            info = check_for_update()
            if info:
                self.update_found.emit(info)
        except Exception:
            pass  # バックグラウンド処理のエラーは無視


class MainWindow(QMainWindow):
    """アプリケーションのメインウィンドウ。"""

    def __init__(
        self,
        controller: AppController,
        settings_store: SettingsStore,
        settings: AppSettings,
    ) -> None:
        """メインウィンドウを初期化する。

        Args:
            controller: アプリケーションコントローラ
            settings_store: 設定永続化ストア
            settings: 現在のアプリケーション設定
        """
        super().__init__()
        self._controller = controller
        self._settings_store = settings_store
        self._settings = settings

        self.setWindowTitle(_WINDOW_TITLE)
        self.setMinimumSize(_WINDOW_MIN_WIDTH, _WINDOW_MIN_HEIGHT)

        self._setup_ui()
        self._connect_signals()
        self._setup_log_bridge()

        # バックグラウンドでのアップデート確認
        self._update_worker = UpdateCheckWorker(self)
        self._update_worker.update_found.connect(self._show_update_dialog)
        QTimer.singleShot(2000, self._update_worker.start)

    def _setup_ui(self) -> None:
        """UI を構築する。"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # --- ツールバー領域 ---
        toolbar_layout = QHBoxLayout()

        self._start_btn = QPushButton("開始")
        self._start_btn.setFixedWidth(100)
        self._stop_btn = QPushButton("停止")
        self._stop_btn.setFixedWidth(100)
        self._stop_btn.setEnabled(False)

        self._status_label = QLabel("状態: 停止中")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        toolbar_layout.addWidget(self._start_btn)
        toolbar_layout.addWidget(self._stop_btn)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self._status_label)

        main_layout.addLayout(toolbar_layout)

        # --- タブ領域 ---
        self._tabs = QTabWidget()

        self._folder_panel = FolderSettingsPanel(self._settings)
        self._template_panel = TemplateEditorPanel(self._controller)
        self._template_set_panel = TemplateSetEditorPanel(self._controller)
        self._printer_panel = PrinterSettingsPanel(self._settings)
        self._log_viewer = LogViewer()

        self._tabs.addTab(self._folder_panel, "設定")
        self._tabs.addTab(self._template_panel, "テンプレート")
        self._tabs.addTab(self._template_set_panel, "テンプレートセット")
        self._tabs.addTab(self._printer_panel, "プリンタ設定")
        self._tabs.addTab(self._log_viewer, "ログ")

        main_layout.addWidget(self._tabs)

    def _connect_signals(self) -> None:
        """Signal/Slot を接続する。"""
        self._start_btn.clicked.connect(self._on_start)
        self._stop_btn.clicked.connect(self._on_stop)

        self._folder_panel.settings_changed.connect(self._on_settings_changed)
        self._printer_panel.settings_changed.connect(self._on_settings_changed)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._controller.monitoring_started.connect(self._on_monitoring_started)
        self._controller.monitoring_stopped.connect(self._on_monitoring_stopped)
        self._controller.job_started.connect(self._on_job_started)
        self._controller.job_completed.connect(self._on_job_completed)
        self._controller.job_failed.connect(self._on_job_failed)
        self._controller.error_occurred.connect(self._on_error)

    def _setup_log_bridge(self) -> None:
        """Python logging → LogViewer への橋渡しを設定する。"""
        self._log_handler = add_signal_handler(self._log_viewer.append_log)

    # --- ボタンハンドラ ---

    @Slot()
    def _on_start(self) -> None:
        self._controller.start_monitoring()

    @Slot()
    def _on_stop(self) -> None:
        self._controller.stop_monitoring()

    # --- Controller Signal ハンドラ ---

    @Slot()
    def _on_monitoring_started(self) -> None:
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status_label.setText("状態: 監視中")
        self._template_panel.setEnabled(False)
        self._template_set_panel.setEnabled(False)
        self._printer_panel.setEnabled(False)
        self._tabs.setCurrentWidget(self._log_viewer)

    @Slot()
    def _on_monitoring_stopped(self) -> None:
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status_label.setText("状態: 停止中")
        self._template_panel.setEnabled(True)
        self._template_set_panel.setEnabled(True)
        self._printer_panel.setEnabled(True)

    @Slot(int)
    def _on_tab_changed(self, index: int) -> None:
        """タブ切り替え時にエディタの一覧リストを最新の状態に更新する。"""
        if self._tabs.widget(index) == self._template_panel:
            self._template_panel.refresh_list()
        elif self._tabs.widget(index) == self._template_set_panel:
            self._template_set_panel.refresh_list()

    @Slot(str)
    def _on_job_started(self, file_name: str) -> None:
        self._status_label.setText(f"状態: 処理中 - {file_name}")

    @Slot(str, str)
    def _on_job_completed(self, file_name: str, output_path: str) -> None:
        self._status_label.setText("状態: 監視中")

    @Slot(str, str)
    def _on_job_failed(self, file_name: str, error_msg: str) -> None:
        self._status_label.setText("状態: 監視中")

    @Slot(str)
    def _on_error(self, message: str) -> None:
        QMessageBox.warning(self, "エラー", message)

    # --- Settings ハンドラ ---

    @Slot(object)
    def _on_settings_changed(self, settings: AppSettings) -> None:
        self._settings = settings
        self._controller.update_folders(settings)
        self._folder_panel.update_settings(settings)
        self._printer_panel.update_settings(settings)
        self._settings_store.save(settings)
        logger.info("設定を保存しました")

    # --- ウィンドウイベント ---

    def closeEvent(self, event: QCloseEvent) -> None:
        """ウィンドウ閉じる際に監視を停止する。"""
        if self._controller.is_monitoring:
            self._controller.stop_monitoring()

        root = logging.getLogger()
        root.removeHandler(self._log_handler)
        event.accept()

    @Slot(dict)
    def _show_update_dialog(self, update_info: dict) -> None:
        from app.gui.update_dialog import UpdateDialog
        dialog = UpdateDialog(update_info, self)
        dialog.exec()
