"""core/watcher.py のユニットテスト。"""

import queue
import time
from pathlib import Path

import pytest

from app.core.watcher import (
    FolderWatcher,
    is_supported_image,
    wait_for_stable,
)


class TestIsSupportedImage:
    """is_supported_image のテスト。"""

    @pytest.mark.parametrize(
        "filename",
        ["test.jpg", "test.jpeg", "test.png", "test.tiff", "test.tif", "test.jp2", "test.bmp"],
    )
    def test_supported_formats(self, filename: str) -> None:
        assert is_supported_image(Path(filename)) is True

    @pytest.mark.parametrize(
        "filename",
        ["test.pdf", "test.txt", "test.docx", "test.svg", ".jpg"],
    )
    def test_unsupported_formats(self, filename: str) -> None:
        assert is_supported_image(Path(filename)) is False

    def test_case_insensitive(self) -> None:
        assert is_supported_image(Path("test.JPG")) is True
        assert is_supported_image(Path("test.Png")) is True


class TestWaitForStable:
    """wait_for_stable のテスト。"""

    def test_stable_file(self, tmp_path: Path) -> None:
        """既に書き込み完了しているファイルに対して True を返す。"""
        f = tmp_path / "test.jpg"
        f.write_bytes(b"x" * 100)
        result = wait_for_stable(f, check_interval=0.05, stable_count=2)
        assert result is True

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """存在しないファイルに対して False を返す。"""
        result = wait_for_stable(tmp_path / "nope.jpg", check_interval=0.05, stable_count=2)
        assert result is False

    def test_empty_file_returns_false(self, tmp_path: Path) -> None:
        """空ファイルはサイズ 0 のままなのでタイムアウトして False を返す。"""
        f = tmp_path / "empty.jpg"
        f.write_bytes(b"")
        result = wait_for_stable(f, check_interval=0.05, stable_count=3, timeout=0.5)
        assert result is False


class TestFolderWatcher:
    """FolderWatcher のテスト。"""

    def test_start_nonexistent_dir(self, tmp_path: Path) -> None:
        """存在しないフォルダで start すると FileNotFoundError。"""
        q: queue.Queue[Path] = queue.Queue()
        watcher = FolderWatcher(tmp_path / "nonexistent", q)
        with pytest.raises(FileNotFoundError):
            watcher.start()

    def test_detect_new_image_file(self, tmp_path: Path) -> None:
        """画像ファイルの追加を検知できることを確認。"""
        event_queue: queue.Queue[Path] = queue.Queue()
        watcher = FolderWatcher(
            tmp_path,
            event_queue,
            check_interval=0.05,
            stable_count=2,
        )
        watcher.start()
        try:
            time.sleep(0.3)

            test_file = tmp_path / "test_image.jpg"
            test_file.write_bytes(b"\xff\xd8\xff" + b"x" * 100)

            detected = None
            for _ in range(40):
                try:
                    detected = event_queue.get(timeout=0.2)
                    break
                except queue.Empty:
                    continue

            assert detected is not None
            assert detected.name == "test_image.jpg"
        finally:
            watcher.stop()

    def test_ignores_non_image_file(self, tmp_path: Path) -> None:
        """非画像ファイルは無視されることを確認。"""
        event_queue: queue.Queue[Path] = queue.Queue()
        watcher = FolderWatcher(
            tmp_path,
            event_queue,
            check_interval=0.05,
            stable_count=2,
        )
        watcher.start()
        try:
            time.sleep(0.3)

            (tmp_path / "readme.txt").write_text("hello")
            time.sleep(1.0)

            assert event_queue.empty()
        finally:
            watcher.stop()

    def test_recursive_detection(self, tmp_path: Path) -> None:
        """サブフォルダ内の画像も検知されることを確認。"""
        sub = tmp_path / "sub"
        sub.mkdir()
        event_queue: queue.Queue[Path] = queue.Queue()
        watcher = FolderWatcher(
            tmp_path,
            event_queue,
            check_interval=0.05,
            stable_count=2,
        )
        watcher.start()
        try:
            time.sleep(0.3)

            test_file = sub / "nested.png"
            test_file.write_bytes(b"\x89PNG" + b"x" * 100)

            detected = None
            for _ in range(40):
                try:
                    detected = event_queue.get(timeout=0.2)
                    break
                except queue.Empty:
                    continue

            assert detected is not None
            assert detected.name == "nested.png"
        finally:
            watcher.stop()
