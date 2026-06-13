"""プリンタ設定パネル。

システムのプリンタ一覧を表示し、デフォルトプリンタや印刷部数を選択・設定する。
"""

import logging
from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.printer import get_printer
from app.models.settings_model import AppSettings

logger = logging.getLogger(__name__)


class PrinterSettingsPanel(QWidget):
    """デフォルトプリンタや部数を設定するための UI パネル。

    Signals:
        settings_changed(AppSettings): 設定が変更されたときに発火する。
    """

    settings_changed = Signal(object)

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._setup_ui()
        self._load_from_settings()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        group = QGroupBox("デフォルト印刷設定")
        form_layout = QFormLayout(group)

        # プリンタ選択コンボボックス
        self._printer_combo = QComboBox()
        self._printer_combo.setMinimumWidth(250)
        self._printer_combo.currentTextChanged.connect(self._on_settings_edited)

        # 更新ボタン付きの水平レイアウト
        printer_layout = QHBoxLayout()
        printer_layout.addWidget(self._printer_combo, stretch=1)

        self._refresh_btn = QPushButton("再スキャン")
        self._refresh_btn.setFixedWidth(80)
        self._refresh_btn.clicked.connect(self._on_refresh_printers)
        printer_layout.addWidget(self._refresh_btn)

        form_layout.addRow("デフォルトプリンタ:", printer_layout)

        # 印刷部数スピンボックス
        self._copies_spin = QSpinBox()
        self._copies_spin.setRange(1, 99)
        self._copies_spin.setFixedWidth(80)
        self._copies_spin.valueChanged.connect(self._on_settings_edited)
        form_layout.addRow("印刷部数:", self._copies_spin)

        layout.addWidget(group)
        layout.addStretch()

        # 初回のプリンタスキャンを実行
        self._refresh_printer_list()

    def _refresh_printer_list(self) -> None:
        """システムからプリンタ一覧を取得してコンボボックスに設定する。"""
        self._printer_combo.blockSignals(True)
        self._printer_combo.clear()

        # システムプリンタ一覧を取得
        printer = get_printer()
        printers = printer.list_printers()

        self._printer_combo.addItem("（システムデフォルト）", "")
        for name in printers:
            self._printer_combo.addItem(name, name)

        self._printer_combo.blockSignals(False)

    def _load_from_settings(self) -> None:
        """設定オブジェクトから値を読み込み UI に反映する。"""
        self._printer_combo.blockSignals(True)
        self._copies_spin.blockSignals(True)

        # デフォルトプリンタ
        default_p = self._settings.printer.default_printer
        if default_p:
            index = self._printer_combo.findData(default_p)
            if index >= 0:
                self._printer_combo.setCurrentIndex(index)
            else:
                # 登録されているがシステムに見つからないプリンタの場合、一時的に追加して選択
                self._printer_combo.addItem(f"{default_p} (オフライン)", default_p)
                self._printer_combo.setCurrentIndex(self._printer_combo.count() - 1)
        else:
            self._printer_combo.setCurrentIndex(0)

        # 印刷部数
        self._copies_spin.setValue(self._settings.printer.copies)

        self._printer_combo.blockSignals(False)
        self._copies_spin.blockSignals(False)

    def update_settings(self, settings: AppSettings) -> None:
        """外部から設定が更新された場合に反映する。"""
        self._settings = settings
        self._load_from_settings()

    @Slot()
    def _on_refresh_printers(self) -> None:
        """プリンタの再スキャンを実行し、既存の選択状態を維持する。"""
        current_data = self._printer_combo.currentData()
        self._refresh_printer_list()
        if current_data:
            index = self._printer_combo.findData(current_data)
            if index >= 0:
                self._printer_combo.setCurrentIndex(index)
        else:
            self._printer_combo.setCurrentIndex(0)

    @Slot()
    def _on_settings_edited(self) -> None:
        """UI が変更されたときに設定モデルを更新しシグナルを発火する。"""
        printer_data = self._printer_combo.currentData()
        # 空文字の場合は None (システムデフォルト) とする
        self._settings.printer.default_printer = printer_data if printer_data != "" else None
        self._settings.printer.copies = self._copies_spin.value()

        self.settings_changed.emit(self._settings)
