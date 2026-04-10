"""プリンタ設定画面。"""

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.printer import Printer, create_printer
from app.models.settings_model import PrinterSettings


class PrinterSettingsWidget(QWidget):
    """プリンタ設定画面。"""

    settings_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._printer: Printer = create_printer()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        printer_group = QGroupBox("プリンタ")
        printer_layout = QVBoxLayout(printer_group)

        select_row = QHBoxLayout()
        select_row.addWidget(QLabel("デフォルトプリンタ:"))
        self._printer_combo = QComboBox()
        select_row.addWidget(self._printer_combo, stretch=1)
        refresh_btn = QPushButton("更新")
        refresh_btn.clicked.connect(self._refresh_printers)
        select_row.addWidget(refresh_btn)
        printer_layout.addLayout(select_row)

        self._auto_print_check = QCheckBox("自動印刷を有効にする")
        printer_layout.addWidget(self._auto_print_check)

        copies_row = QHBoxLayout()
        copies_row.addWidget(QLabel("部数:"))
        self._copies_spin = QSpinBox()
        self._copies_spin.setMinimum(1)
        self._copies_spin.setMaximum(99)
        copies_row.addWidget(self._copies_spin)
        copies_row.addStretch()
        printer_layout.addLayout(copies_row)

        layout.addWidget(printer_group)

        test_btn = QPushButton("テスト印刷")
        test_btn.clicked.connect(self._test_print)
        layout.addWidget(test_btn)

        layout.addStretch()

    def load_settings(self, settings: PrinterSettings) -> None:
        self._refresh_printers()
        if settings.default_printer:
            idx = self._printer_combo.findText(settings.default_printer)
            if idx >= 0:
                self._printer_combo.setCurrentIndex(idx)
        self._auto_print_check.setChecked(settings.auto_print_enabled)
        self._copies_spin.setValue(settings.copies)

    def get_settings(self) -> PrinterSettings:
        return PrinterSettings(
            default_printer=self._printer_combo.currentText() or None,
            copies=self._copies_spin.value(),
            auto_print_enabled=self._auto_print_check.isChecked(),
        )

    @Slot()
    def _refresh_printers(self) -> None:
        self._printer_combo.clear()
        printers = self._printer.list_printers()
        self._printer_combo.addItems(printers)
        default = self._printer.get_default_printer()
        if default:
            idx = self._printer_combo.findText(default)
            if idx >= 0:
                self._printer_combo.setCurrentIndex(idx)

    @Slot()
    def _test_print(self) -> None:
        QMessageBox.information(
            self, "テスト印刷", "テスト印刷機能は実プリンタ接続後にお試しください"
        )
