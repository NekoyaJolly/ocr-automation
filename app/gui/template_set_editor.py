"""テンプレートセットエディタパネル。

テンプレートセット（複数のテンプレートと出力・印刷設定の組み合わせ）の新規作成・複製・削除・編集を行う。
"""

import logging
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.app_controller import AppController
from app.models.template_model import TemplateSet, TemplateSetEntry

logger = logging.getLogger(__name__)


class TemplateSetEditorPanel(QWidget):
    """テンプレートセットの管理および紐付け設定を編集する UI パネル。"""

    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._current_set: TemplateSet | None = None
        self._setup_ui()
        self.refresh_list()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        # 左右スプリッター
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # --- 左ペイン: セット一覧 ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("テンプレートセット一覧"))

        self._set_list = QListWidget()
        self._set_list.itemSelectionChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self._set_list)

        # 操作ボタン
        btn_layout = QHBoxLayout()
        self._new_btn = QPushButton("新規")
        self._copy_btn = QPushButton("複製")
        self._delete_btn = QPushButton("削除")

        self._new_btn.clicked.connect(self._on_new)
        self._copy_btn.clicked.connect(self._on_copy)
        self._delete_btn.clicked.connect(self._on_delete)

        btn_layout.addWidget(self._new_btn)
        btn_layout.addWidget(self._copy_btn)
        btn_layout.addWidget(self._delete_btn)
        left_layout.addLayout(btn_layout)

        splitter.addWidget(left_widget)

        # --- 右ペイン: 編集フォーム ---
        self._right_widget = QWidget()
        right_layout = QVBoxLayout(self._right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 1. 基本設定
        basic_group = QGroupBox("基本設定")
        basic_layout = QVBoxLayout(basic_group)

        # セット名
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("セット名:"))
        self._name_edit = QLineEdit()
        name_layout.addWidget(self._name_edit)
        basic_layout.addLayout(name_layout)

        # 説明
        desc_layout = QHBoxLayout()
        desc_layout.addWidget(QLabel("説明:"))
        self._desc_edit = QLineEdit()
        desc_layout.addWidget(self._desc_edit)
        basic_layout.addLayout(desc_layout)

        right_layout.addWidget(basic_group)

        # 2. テンプレートエントリリスト
        entries_group = QGroupBox("適用テンプレートと個別設定")
        entries_layout = QVBoxLayout(entries_group)

        self._entries_table = QTableWidget()
        self._entries_table.setColumnCount(5)
        self._entries_table.setHorizontalHeaderLabels(
            ["適用するテンプレート", "有効", "出力先サブフォルダ", "自動印刷", "使用プリンタ(空でデフォルト)"]
        )
        entries_layout.addWidget(self._entries_table)

        # 操作ボタン
        table_btn_layout = QHBoxLayout()
        self._add_row_btn = QPushButton("テンプレート追加")
        self._del_row_btn = QPushButton("削除")
        self._add_row_btn.clicked.connect(self._on_add_row)
        self._del_row_btn.clicked.connect(self._on_del_row)
        table_btn_layout.addWidget(self._add_row_btn)
        table_btn_layout.addWidget(self._del_row_btn)
        table_btn_layout.addStretch()
        entries_layout.addLayout(table_btn_layout)

        right_layout.addWidget(entries_group)

        # 保存ボタン
        self._save_btn = QPushButton("保存")
        self._save_btn.clicked.connect(self._on_save)
        self._save_btn.setMinimumHeight(40)
        right_layout.addWidget(self._save_btn)

        splitter.addWidget(self._right_widget)

        splitter.setSizes([200, 500])

        self._right_widget.setEnabled(False)

    def refresh_list(self) -> None:
        """セット一覧を再読み込みしてリストを更新する。"""
        self._set_list.clear()
        sets = self._controller.get_available_template_sets()
        for name in sets:
            self._set_list.addItem(name)
        self._right_widget.setEnabled(False)
        self._current_set = None

    @Slot()
    def _on_selection_changed(self) -> None:
        """選択変更時にフォームにロード。"""
        selected_items = self._set_list.selectedItems()
        if not selected_items:
            self._right_widget.setEnabled(False)
            return

        name = selected_items[0].text()
        tset = self._controller.load_template_set_by_name(name)
        if tset:
            self._current_set = tset
            self._load_set_to_form(tset)
            self._right_widget.setEnabled(True)
            self._name_edit.setEnabled(False)  # 既存セットの名前変更は不可

    def _load_set_to_form(self, tset: TemplateSet) -> None:
        """モデルをフォームに反映。"""
        self._name_edit.setText(tset.name)
        self._desc_edit.setText(tset.description)

        self._entries_table.setRowCount(0)
        for entry in tset.entries:
            self._add_row_with_data(entry)

    def _add_row_with_data(self, entry: TemplateSetEntry | None = None) -> None:
        """エントリーテーブルに 1 行追加。"""
        row = self._entries_table.rowCount()
        self._entries_table.insertRow(row)

        # 適用テンプレート選択コンボボックス
        tmpl_combo = QComboBox()
        templates = self._controller.get_available_templates()
        tmpl_combo.addItems(templates)
        if entry:
            tmpl_combo.setCurrentText(entry.template_name)
        self._entries_table.setCellWidget(row, 0, tmpl_combo)

        # 有効チェックボックス
        enabled_item = QTableWidgetItem()
        enabled_item.setFlags(enabled_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        is_checked = entry.enabled if entry else True
        enabled_item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
        self._entries_table.setItem(row, 1, enabled_item)

        # 出力先サブフォルダ
        subfolder_item = QTableWidgetItem(entry.output_subfolder if entry else "")
        self._entries_table.setItem(row, 2, subfolder_item)

        # 自動印刷チェックボックス
        print_item = QTableWidgetItem()
        print_item.setFlags(print_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        is_print = entry.auto_print if entry else False
        print_item.setCheckState(Qt.CheckState.Checked if is_print else Qt.CheckState.Unchecked)
        self._entries_table.setItem(row, 3, print_item)

        # 使用プリンタ
        printer_item = QTableWidgetItem(entry.printer_name if (entry and entry.printer_name) else "")
        self._entries_table.setItem(row, 4, printer_item)

    @Slot()
    def _on_add_row(self) -> None:
        templates = self._controller.get_available_templates()
        if not templates:
            QMessageBox.warning(self, "警告", "利用可能なテンプレートがありません。先にテンプレートを作成してください。")
            return
        self._add_row_with_data(None)

    @Slot()
    def _on_del_row(self) -> None:
        current_row = self._entries_table.currentRow()
        if current_row >= 0:
            self._entries_table.removeRow(current_row)

    @Slot()
    def _on_new(self) -> None:
        templates = self._controller.get_available_templates()
        if not templates:
            QMessageBox.warning(self, "警告", "利用可能なテンプレートがありません。先にテンプレートを作成してください。")
            return

        self._set_list.clearSelection()
        self._current_set = None

        self._name_edit.setText("新規テンプレートセット")
        self._name_edit.setEnabled(True)
        self._desc_edit.setText("")

        self._entries_table.setRowCount(0)
        self._right_widget.setEnabled(True)
        self._name_edit.setFocus()

    @Slot()
    def _on_copy(self) -> None:
        if not self._current_set:
            return

        copied = self._current_set.model_copy(deep=True)
        copied.name = f"{copied.name}_copy"

        self._current_set = copied
        self._load_set_to_form(copied)
        self._name_edit.setEnabled(True)
        self._name_edit.setFocus()
        self._set_list.clearSelection()

    @Slot()
    def _on_delete(self) -> None:
        selected_items = self._set_list.selectedItems()
        if not selected_items:
            return

        name = selected_items[0].text()
        reply = QMessageBox.question(
            self,
            "削除確認",
            f"テンプレートセット '{name}' を削除しますか？\n(設定されている YAML ファイルが物理的に削除されます)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._controller.delete_template_set(name)
                self.refresh_list()
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"削除に失敗しました: {e}")

    @Slot()
    def _on_save(self) -> None:
        name = self._name_edit.text().strip()
        if not name or name == "新規テンプレートセット":
            QMessageBox.warning(self, "警告", "有効なテンプレートセット名を入力してください。")
            return

        if self._entries_table.rowCount() == 0:
            QMessageBox.warning(self, "警告", "セットに含めるテンプレートを 1 つ以上登録してください。")
            return

        entries = []
        for row in range(self._entries_table.rowCount()):
            # テーブルの値を取得
            tmpl_name = self._entries_table.cellWidget(row, 0).currentText()
            enabled = self._entries_table.item(row, 1).checkState() == Qt.CheckState.Checked
            subfolder = self._get_item_text(row, 2)
            auto_print = self._entries_table.item(row, 3).checkState() == Qt.CheckState.Checked
            printer = self._get_item_text(row, 4) or None

            if not tmpl_name:
                QMessageBox.warning(self, "警告", f"{row + 1}行目のテンプレートが選択されていません。")
                return

            entries.append(
                TemplateSetEntry(
                    template_name=tmpl_name,
                    enabled=enabled,
                    output_subfolder=subfolder,
                    auto_print=auto_print,
                    printer_name=printer,
                )
            )

        # TemplateSet モデル構築
        tset = TemplateSet(
            name=name,
            description=self._desc_edit.text().strip(),
            entries=entries,
        )

        try:
            self._controller.save_template_set(tset)
            QMessageBox.information(self, "成功", "テンプレートセットを保存しました。")
            self.refresh_list()
            items = self._set_list.findItems(name, Qt.MatchFlag.MatchExactly)
            if items:
                self._set_list.setCurrentItem(items[0])
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"保存に失敗しました:\n{e}")

    def _get_item_text(self, row: int, col: int) -> str:
        item = self._entries_table.item(row, col)
        return item.text().strip() if item else ""
