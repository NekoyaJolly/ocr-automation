"""フォルダ監視モジュール。

watchdog をラップし、ファイル書き込み完了まで待ってからコールバックを発火する。
"""

import logging
import queue
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".jp2", ".bmp"}
)

_DEFAULT_STABLE_INTERVAL: float = 0.5
_DEFAULT_STABLE_COUNT: int = 3


def is_supported_image(path: Path) -> bool:
    """対応画像形式かどうかを判定する。

    Args:
        path: 判定するファイルパス

    Returns:
        対応画像形式なら True
    """
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def wait_for_stable(
    path: Path,
    check_interval: float = _DEFAULT_STABLE_INTERVAL,
    stable_count: int = _DEFAULT_STABLE_COUNT,
    timeout: float = 30.0,
) -> bool:
    """ファイルの書き込み完了を待つ。

    ファイルサイズが一定回数連続で同じ値（かつ 0 より大きい）になったら
    書き込み完了と判定する。

    Args:
        path: 監視するファイルパス
        check_interval: チェック間隔（秒）
        stable_count: サイズが安定していると判定する連続回数
        timeout: タイムアウト（秒）。超過したら False を返す。

    Returns:
        書き込み完了なら True、ファイル消失またはタイムアウトの場合は False
    """
    deadline = time.monotonic() + timeout
    last_size = -1
    stable = 0
    while stable < stable_count:
        if time.monotonic() > deadline:
            logger.warning(f"書き込み完了待ちがタイムアウトしました: {path}")
            return False
        try:
            current = path.stat().st_size
        except FileNotFoundError:
            return False
        if current == last_size and current > 0:
            stable += 1
        else:
            stable = 0
            last_size = current
        time.sleep(check_interval)
    return True


class _ImageFileHandler(FileSystemEventHandler):
    """画像ファイルの作成・変更イベントを queue に通知するハンドラ。"""

    def __init__(self, event_queue: queue.Queue[Path]) -> None:
        super().__init__()
        self._queue = event_queue
        self._seen: set[str] = set()
        self._lock = threading.Lock()

    def on_created(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def _handle(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(str(event.src_path))
        if not is_supported_image(path):
            return

        key = str(path.resolve())
        with self._lock:
            if key in self._seen:
                return
            self._seen.add(key)

        self._queue.put(path)


class FolderWatcher:
    """watchdog をラップしたフォルダ監視クラス。

    入力フォルダを再帰的に監視し、新しい画像ファイルを検出して
    書き込み完了後にコールバック用の queue に通知する。
    """

    def __init__(
        self,
        watch_dir: Path,
        event_queue: queue.Queue[Path],
        *,
        check_interval: float = _DEFAULT_STABLE_INTERVAL,
        stable_count: int = _DEFAULT_STABLE_COUNT,
    ) -> None:
        """監視を初期化する。

        Args:
            watch_dir: 監視対象のルートフォルダ
            event_queue: 書き込み完了したファイルパスを通知する queue
            check_interval: 書き込み完了チェックの間隔（秒）
            stable_count: サイズ安定と判定する連続回数
        """
        self._watch_dir = watch_dir
        self._event_queue = event_queue
        self._check_interval = check_interval
        self._stable_count = stable_count

        self._raw_queue: queue.Queue[Path] = queue.Queue()
        self._handler = _ImageFileHandler(self._raw_queue)
        self._observer = Observer()
        self._stabilizer_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @property
    def watch_dir(self) -> Path:
        """監視対象のルートフォルダ。"""
        return self._watch_dir

    @property
    def is_running(self) -> bool:
        """監視が動作中かどうか。"""
        return self._observer.is_alive()

    def start(self) -> None:
        """フォルダ監視を開始する。

        Raises:
            FileNotFoundError: 監視対象フォルダが存在しない場合
        """
        if not self._watch_dir.exists():
            raise FileNotFoundError(f"監視対象フォルダが見つかりません: {self._watch_dir}")

        self._stop_event.clear()
        self._observer = Observer()
        self._observer.schedule(self._handler, str(self._watch_dir), recursive=True)
        self._observer.start()

        self._stabilizer_thread = threading.Thread(
            target=self._stabilizer_loop, daemon=True, name="watcher-stabilizer"
        )
        self._stabilizer_thread.start()

        logger.info(f"フォルダ監視を開始しました: {self._watch_dir}")

    def stop(self) -> None:
        """フォルダ監視を停止する。"""
        self._stop_event.set()
        self._observer.stop()
        self._observer.join(timeout=5)
        if self._stabilizer_thread is not None:
            self._stabilizer_thread.join(timeout=5)
            self._stabilizer_thread = None
        logger.info("フォルダ監視を停止しました")

    def _stabilizer_loop(self) -> None:
        """raw_queue からパスを取り出し、書き込み完了を待ってから event_queue に転送する。"""
        while not self._stop_event.is_set():
            try:
                path = self._raw_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if wait_for_stable(path, self._check_interval, self._stable_count):
                logger.debug(f"書き込み完了を確認: {path}")
                self._event_queue.put(path)
            else:
                logger.warning(f"ファイルが書き込み中に消失しました: {path}")
