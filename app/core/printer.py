"""印刷機能 — 抽象インターフェース + OS 別実装。"""

import platform
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from app.exceptions import PrintError
from app.infrastructure.logger import get_logger

logger = get_logger(__name__)


class Printer(ABC):
    """印刷の抽象インターフェース。"""

    @abstractmethod
    def print_file(
        self,
        file_path: Path,
        printer_name: str | None = None,
        copies: int = 1,
    ) -> None:
        """ファイルをプリンタに送信する。"""
        ...

    @abstractmethod
    def list_printers(self) -> list[str]:
        """システムに登録されているプリンタ一覧を返す。"""
        ...

    @abstractmethod
    def get_default_printer(self) -> str | None:
        """デフォルトプリンタ名を返す。"""
        ...


class WindowsPrinter(Printer):
    """Windows 用プリンタ実装 (pywin32)。"""

    def print_file(
        self,
        file_path: Path,
        printer_name: str | None = None,
        copies: int = 1,
    ) -> None:
        try:
            import win32api  # type: ignore[import-not-found]
            import win32print  # type: ignore[import-not-found]

            if printer_name:
                win32print.SetDefaultPrinter(printer_name)

            for _ in range(copies):
                win32api.ShellExecute(0, "print", str(file_path), None, ".", 0)

            logger.info("印刷送信: %s (プリンタ: %s, 部数: %d)", file_path, printer_name, copies)
        except ImportError:
            raise PrintError("pywin32 がインストールされていません") from None
        except Exception as e:
            raise PrintError(f"印刷に失敗しました: {e}") from e

    def list_printers(self) -> list[str]:
        try:
            import win32print  # type: ignore[import-not-found]

            printers = win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            )
            return [p[2] for p in printers]
        except ImportError:
            return []

    def get_default_printer(self) -> str | None:
        try:
            import win32print  # type: ignore[import-not-found]

            return win32print.GetDefaultPrinter()
        except (ImportError, RuntimeError):
            return None


class MacPrinter(Printer):
    """macOS 用プリンタ実装 (subprocess + lp)。"""

    def print_file(
        self,
        file_path: Path,
        printer_name: str | None = None,
        copies: int = 1,
    ) -> None:
        if not file_path.exists():
            raise PrintError(f"ファイルが見つかりません: {file_path}")

        cmd = ["lp"]
        if printer_name:
            cmd.extend(["-d", printer_name])
        cmd.extend(["-n", str(copies)])
        cmd.append(str(file_path))

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                raise PrintError(f"lp コマンドエラー: {result.stderr}")
            logger.info("印刷送信: %s (プリンタ: %s, 部数: %d)", file_path, printer_name, copies)
        except subprocess.TimeoutExpired:
            raise PrintError("印刷コマンドがタイムアウトしました") from None
        except FileNotFoundError:
            raise PrintError("lp コマンドが見つかりません") from None

    def list_printers(self) -> list[str]:
        try:
            result = subprocess.run(
                ["lpstat", "-p"], capture_output=True, text=True, timeout=10
            )
            printers: list[str] = []
            for line in result.stdout.strip().split("\n"):
                if line.startswith("printer "):
                    parts = line.split()
                    if len(parts) >= 2:
                        printers.append(parts[1])
            return printers
        except Exception:
            return []

    def get_default_printer(self) -> str | None:
        try:
            result = subprocess.run(
                ["lpstat", "-d"], capture_output=True, text=True, timeout=10
            )
            line = result.stdout.strip()
            if ":" in line:
                return line.split(":")[-1].strip()
            return None
        except Exception:
            return None


def create_printer() -> Printer:
    """現在の OS に応じた Printer インスタンスを生成する。"""
    system = platform.system()
    if system == "Windows":
        return WindowsPrinter()
    return MacPrinter()
