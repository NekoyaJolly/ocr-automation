"""PrintWorker — QThread で自動印刷を処理するワーカー。"""

import queue
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.core.printer import Printer
from app.infrastructure.logger import get_logger

logger = get_logger(__name__)


class PrintJob:
    """印刷ジョブ。"""

    def __init__(
        self,
        file_path: Path,
        printer_name: str | None = None,
        copies: int = 1,
    ) -> None:
        self.file_path = file_path
        self.printer_name = printer_name
        self.copies = copies


class PrintWorker(QThread):
    """バックグラウンドで印刷処理を行うワーカースレッド。

    Signals:
        print_completed: 印刷完了 (file_path)。
        print_failed: 印刷失敗 (file_path, error)。
        log_message: ログ (message)。
    """

    print_completed = Signal(str)
    print_failed = Signal(str, str)
    log_message = Signal(str)

    def __init__(
        self,
        print_queue: "queue.Queue[PrintJob]",
        printer: Printer,
    ) -> None:
        super().__init__()
        self._queue = print_queue
        self._printer = printer
        self._running = True

    def run(self) -> None:
        """印刷キューからジョブを取り出して処理するメインループ。"""
        logger.info("PrintWorker 開始")
        while self._running:
            try:
                job = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                self._printer.print_file(
                    job.file_path,
                    printer_name=job.printer_name,
                    copies=job.copies,
                )
                self.print_completed.emit(str(job.file_path))
                self.log_message.emit(f"印刷完了: {job.file_path.name}")
            except Exception as e:
                self.print_failed.emit(str(job.file_path), str(e))
                self.log_message.emit(f"印刷失敗: {job.file_path.name} — {e}")

        logger.info("PrintWorker 停止")

    def stop(self) -> None:
        """ワーカーを停止する。"""
        self._running = False
