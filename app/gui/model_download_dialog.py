"""OCRモデルの自動ダウンロード進捗を表示するGUIダイアログ。"""

import sys
from PySide6.QtCore import QThread, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QMessageBox,
)


class ModelDownloadWorker(QThread):
    """バックグラウンドでモデルをダウンロードするスレッド。"""

    progress_signal = Signal(str, int, int)
    finished_signal = Signal()
    error_signal = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.is_cancelled = False

    def run(self) -> None:
        try:
            def callback(filename: str, downloaded: int, total: int) -> None:
                if self.is_cancelled:
                    raise InterruptedError("ダウンロードがキャンセルされました。")
                self.progress_signal.emit(filename, downloaded, total)

            from app.core.model_manager import ModelManager
            ModelManager.download_models(progress_callback=callback)
            self.finished_signal.emit()
        except InterruptedError:
            # キャンセル時は静かに終了
            pass
        except Exception as e:
            self.error_signal.emit(str(e))

    def cancel(self) -> None:
        """ダウンロードを中断する。"""
        self.is_cancelled = True


class ModelDownloadDialog(QDialog):
    """モデルダウンロードのプログレスダイアログ。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("OCRモデルのセットアップ")
        self.setFixedSize(450, 180)
        self.setModal(True)

        self._worker = ModelDownloadWorker()
        self._worker.progress_signal.connect(self._on_progress)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.error_signal.connect(self._on_error)

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.info_label = QLabel(
            "OCR機能に必要な推論モデル（ONNX形式、計約150MB）を\n"
            "インターネットからダウンロードしています。\n"
            "※初回起動時のみ実行されます。しばらくお待ちください。",
            self
        )
        layout.addWidget(self.info_label)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("準備中...", self)
        layout.addWidget(self.status_label)

        self.cancel_button = QPushButton("キャンセル", self)
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button)

    def start_download(self) -> bool:
        """ダウンロードを開始し、ダイアログを開く。完了時に True、失敗/キャンセル時に False を返す。"""
        self._worker.start()
        # exec() を呼び出してモーダルダイアログを開始
        result = self.exec()
        return result == QDialog.Accepted

    @Slot(str, int, int)
    def _on_progress(self, filename: str, downloaded: int, total: int) -> None:
        percent = int(downloaded / total * 100) if total > 0 else 0
        self.progress_bar.setValue(percent)

        downloaded_mb = downloaded / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        self.status_label.setText(
            f"ダウンロード中: {filename}\n"
            f"進捗: {downloaded_mb:.2f} MB / {total_mb:.2f} MB ({percent}%)"
        )

    @Slot()
    def _on_finished(self) -> None:
        self.accept()

    @Slot(str)
    def _on_error(self, message: str) -> None:
        QMessageBox.critical(
            self,
            "ダウンロードエラー",
            f"モデルのダウンロード中にエラーが発生しました:\n{message}\n\n"
            "インターネット接続を確認し、再度アプリを起動してください。"
        )
        self.reject()

    def reject(self) -> None:
        """ダイアログのキャンセル処理（ウィンドウを閉じる、またはキャンセルボタン押下）。"""
        if self._worker.isRunning():
            reply = QMessageBox.question(
                self,
                "確認",
                "ダウンロードを中止しますか？\n（OCRモデルが未完了の場合、アプリは起動できません）",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._worker.cancel()
                self._worker.wait()  # スレッドが終了するのを待つ
                super().reject()
        else:
            super().reject()
