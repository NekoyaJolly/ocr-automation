"""プリンタ制御モジュール。

OS ごとの印刷処理を抽象化し、プリンタ一覧取得およびファイルの印刷を実行する。
"""

import logging
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)

# pywin32 の遅延インポート用
win32print = None
win32api = None
if sys.platform == "win32":
    try:
        import win32api
        import win32print
    except ImportError:
        logger.warning("win32print / win32api がインストールされていません。WindowsPrinter はダミー動作になります。")


class Printer(ABC):
    """プリンタ制御の抽象基底クラス。"""

    @abstractmethod
    def list_printers(self) -> list[str]:
        """システムに登録されているプリンタの一覧を取得する。

        Returns:
            プリンタ名（文字列）のリスト。
        """
        ...

    @abstractmethod
    def print_file(
        self, file_path: Path, printer_name: str | None = None, copies: int = 1
    ) -> None:
        """指定されたファイルを印刷する。

        Args:
            file_path: 印刷対象のファイルパス。
            printer_name: 送信先プリンタ名。None の場合はシステムのデフォルトプリンタを使用。
            copies: 印刷部数。
        """
        ...


class MacPrinter(Printer):
    """macOS 向けの Printer 実装 (lp/lpstat コマンドを使用)。"""

    def list_printers(self) -> list[str]:
        try:
            res = subprocess.run(
                ["lpstat", "-p"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            printers = []
            for line in res.stdout.splitlines():
                if line.startswith("printer "):
                    parts = line.split()
                    if len(parts) >= 2:
                        printers.append(parts[1])
            return sorted(printers)
        except Exception as e:
            logger.warning(f"macOS プリンタ一覧の取得に失敗しました: {e}")
            return []

    def print_file(
        self, file_path: Path, printer_name: str | None = None, copies: int = 1
    ) -> None:
        if not file_path.exists():
            raise FileNotFoundError(f"印刷対象ファイルが見つかりません: {file_path}")

        cmd = ["lp", "-n", str(copies)]
        if printer_name:
            cmd.extend(["-d", printer_name])
        cmd.append(str(file_path))

        try:
            logger.info(f"macOS 印刷コマンド実行: {' '.join(cmd)}")
            subprocess.run(cmd, check=True, timeout=10)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"lp コマンドの実行に失敗しました: {e}") from e


class WindowsPrinter(Printer):
    """Windows 向けの Printer 実装 (pywin32 を使用)。"""

    def list_printers(self) -> list[str]:
        if win32print is None:
            logger.warning("win32print が利用できないため、空のプリンタ一覧を返します。")
            return []

        try:
            # ローカル接続およびネットワーク接続のプリンタ一覧を取得
            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            printers_info = win32print.EnumPrinters(flags, None, 1)
            printers = [info[2] for info in printers_info]
            return sorted(printers)
        except Exception as e:
            logger.warning(f"Windows プリンタ一覧の取得に失敗しました: {e}")
            return []

    def print_file(
        self, file_path: Path, printer_name: str | None = None, copies: int = 1
    ) -> None:
        if win32api is None or win32print is None:
            raise RuntimeError("win32api / win32print が利用できないため、印刷を実行できません。")

        if not file_path.exists():
            raise FileNotFoundError(f"印刷対象ファイルが見つかりません: {file_path}")

        old_printer = None
        if printer_name:
            try:
                # 一時的にデフォルトプリンタを変更して ShellExecute 経由の印刷先を制御
                old_printer = win32print.GetDefaultPrinter()
                win32print.SetDefaultPrinter(printer_name)
            except Exception as e:
                logger.error(f"Windows デフォルトプリンタの設定変更に失敗しました: {e}")

        try:
            for i in range(copies):
                logger.info(
                    f"Windows 印刷実行: {file_path.name} (プリンタ: {printer_name or 'デフォルト'}, 部数: {i+1}/{copies})"
                )
                # "print" 動詞でファイルを関連付けソフトで印刷
                win32api.ShellExecute(0, "print", str(file_path), None, ".", 0)
                if copies > 1:
                    time.sleep(1.0)
        except Exception as e:
            raise RuntimeError(f"Windows 印刷処理に失敗しました: {e}") from e
        finally:
            if old_printer:
                try:
                    win32print.SetDefaultPrinter(old_printer)
                except Exception:
                    pass


class DummyPrinter(Printer):
    """テストおよびフォールバック用のダミープリンタ実装。"""

    def list_printers(self) -> list[str]:
        return ["Dummy_Printer_1", "Dummy_Printer_2"]

    def print_file(
        self, file_path: Path, printer_name: str | None = None, copies: int = 1
    ) -> None:
        logger.info(
            f"[DUMMY PRINT] ファイル印刷を実行しました:\n"
            f"  パス: {file_path}\n"
            f"  送信先プリンタ: {printer_name or 'デフォルトプリンタ'}\n"
            f"  印刷部数: {copies}"
        )


def get_printer() -> Printer:
    """現在の OS およびライブラリ環境に適合する Printer インスタンスを取得する。"""
    if sys.platform == "darwin":
        # Mac 環境で lpstat が動作する場合のみ MacPrinter
        try:
            res = subprocess.run(["which", "lpstat"], capture_output=True, text=True)
            if res.returncode == 0:
                return MacPrinter()
        except Exception:
            pass
    elif sys.platform == "win32":
        if win32print is not None and win32api is not None:
            return WindowsPrinter()

    # フォールバック
    return DummyPrinter()
