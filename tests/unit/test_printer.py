"""プリンタ制御モジュールのユニットテスト。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.core.printer import DummyPrinter, MacPrinter, WindowsPrinter, get_printer


def test_get_printer():
    printer = get_printer()
    assert printer is not None
    # どの環境でも何かしらの Printer インスタンスが返る
    assert isinstance(printer, (MacPrinter, WindowsPrinter, DummyPrinter))


def test_dummy_printer():
    printer = DummyPrinter()
    # プリンタ一覧の取得
    printers = printer.list_printers()
    assert len(printers) >= 2
    assert "Dummy_Printer_1" in printers

    # 印刷処理（エラーにならずにログ出力されること）
    printer.print_file(Path("dummy_path.txt"), "Dummy_Printer_1", copies=2)


@patch("subprocess.run")
def test_mac_printer_list_printers(mock_run):
    # lpstat -p の出力を模倣
    mock_run.return_value = MagicMock(
        stdout="printer HP_LaserJet_400 is idle. enabled since ...\nprinter Canon_MX490 is disabled.",
        returncode=0,
    )

    printer = MacPrinter()
    printers = printer.list_printers()
    
    assert len(printers) == 2
    assert "HP_LaserJet_400" in printers
    assert "Canon_MX490" in printers
    mock_run.assert_called_once_with(
        ["lpstat", "-p"], capture_output=True, text=True, check=True, timeout=5
    )


@patch("subprocess.run")
def test_mac_printer_print_file(mock_run, tmp_path):
    mock_file = tmp_path / "print_target.txt"
    mock_file.write_text("hello", encoding="utf-8")

    printer = MacPrinter()
    printer.print_file(mock_file, "HP_LaserJet_400", copies=3)

    mock_run.assert_called_once_with(
        ["lp", "-n", "3", "-d", "HP_LaserJet_400", str(mock_file)],
        check=True,
        timeout=10,
    )


def test_windows_printer_no_pywin32(monkeypatch):
    # win32print/win32api が利用不可の場合のテスト
    monkeypatch.setattr("app.core.printer.win32print", None)
    monkeypatch.setattr("app.core.printer.win32api", None)

    printer = WindowsPrinter()
    assert printer.list_printers() == []

    with pytest.raises(RuntimeError, match="利用できないため"):
        printer.print_file(Path("dummy.txt"))
