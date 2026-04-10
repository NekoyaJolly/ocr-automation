"""フォルダ監視 — watchdog をラップし、ファイル書き込み完了まで待ってからイベントを発火。"""

import time
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from app.infrastructure.logger import get_logger

logger = get_logger(__name__)

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".jp2", ".bmp", ".pdf"}
STABILITY_CHECK_INTERVAL = 0.5  # 秒
STABILITY_CHECK_COUNT = 3


class _NewFileHandler(FileSystemEventHandler):
    """新規ファイル作成イベントを処理するハンドラ。"""

    def __init__(self, callback: Callable[[Path], None]) -> None:
        super().__init__()
        self._callback = callback

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return
        if self._wait_for_write_completion(path):
            logger.info("新規ファイル検知 (書き込み完了): %s", path)
            self._callback(path)

    @staticmethod
    def _wait_for_write_completion(path: Path, timeout: float = 30.0) -> bool:
        """ファイルサイズが安定するまで待つ。"""
        start = time.time()
        prev_size = -1
        stable_count = 0
        while time.time() - start < timeout:
            try:
                current_size = path.stat().st_size
            except OSError:
                return False
            if current_size == prev_size and current_size > 0:
                stable_count += 1
                if stable_count >= STABILITY_CHECK_COUNT:
                    return True
            else:
                stable_count = 0
            prev_size = current_size
            time.sleep(STABILITY_CHECK_INTERVAL)
        logger.warning("ファイル書き込み完了待ちタイムアウト: %s", path)
        return False


class FolderWatcher:
    """入力フォルダを再帰的に監視し、新規画像ファイルをコールバックで通知する。"""

    def __init__(self, watch_dir: Path, on_new_file: Callable[[Path], None]) -> None:
        self._watch_dir = watch_dir
        self._handler = _NewFileHandler(on_new_file)
        self._observer = Observer()

    def start(self) -> None:
        """監視を開始する。"""
        self._watch_dir.mkdir(parents=True, exist_ok=True)
        self._observer.schedule(self._handler, str(self._watch_dir), recursive=True)
        self._observer.start()
        logger.info("フォルダ監視を開始: %s", self._watch_dir)

    def stop(self) -> None:
        """監視を停止する。"""
        self._observer.stop()
        self._observer.join(timeout=5)
        logger.info("フォルダ監視を停止: %s", self._watch_dir)

    @property
    def is_running(self) -> bool:
        """監視中かどうかを返す。"""
        return self._observer.is_alive()
