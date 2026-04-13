"""テンプレートセットエディタ画面。"""

import traceback
from pathlib import Path

import yaml
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.template import load_template_set
from app.infrastructure.logger import get_logger
from app.infrastructure.paths import get_user_template_sets_dir
from app.models.template_model import TemplateSet, TemplateSetEntry

logger = get_logger(__name__)


class TemplateSetEditorWidget(QWidget):
    """テンプレートセットの作成・編集・削除を行うエディタ画面。"""

    set_saved = Signal(str)

    def __init__(
        self,
        available_templates: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._available_templates = available_templates or []
        self._setup_ui()
        self._refresh_list()

    def set_available_templates(self, names: list[str]) -> None:
        self._available_templates = names

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)

        splitter = QSplitter()

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("セット一覧"))
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self._list, stretch=1)

        btn_row = QHBoxLayout()
        new_btn = QPushButton("新規")
        new_btn.clicked.connect(self._new_set)
        btn_row.addWidget(new_btn)
        del_btn = QPushButton("削除")
        del_btn.clicked.connect(self._delete_set)
        btn_row.addWidget(del_btn)
        left_layout.addLayout(btn_row)

        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        basic_group = QGroupBox("セット基本情報")
        basic_layout = QVBoxLayout(basic_group)
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("名前:"))
        self._name_edit = QLineEdit()
        name_row.addWidget(self._name_edit, stretch=1)
        basic_layout.addLayout(name_row)
        desc_row = QHBoxLayout()
        desc_row.addWidget(QLabel("説明:"))
        self._desc_edit = QLineEdit()
        desc_row.addWidget(self._desc_edit, stretch=1)
        basic_layout.addLayout(desc_row)
        right_layout.addWidget(basic_group)

        entries_group = QGroupBox("エントリ (テンプレート)")
        entries_layout = QVBoxLayout(entries_group)

        self._entries_table = QTableWidget(0, 5)
        self._entries_table.setHorizontalHeaderLabels([
            "テンプレート名", "有効", "出力サブフォルダ", "自動印刷", "プリンタ"
        ])
        entries_layout.addWidget(self._entries_table, stretch=1)

        entry_btn_row = QHBoxLayout()
        add_entry_btn = QPushButton("エントリ追加")
        add_entry_btn.clicked.connect(self._add_entry_row)
        entry_btn_row.addWidget(add_entry_btn)
        rm_entry_btn = QPushButton("エントリ削除")
        rm_entry_btn.clicked.connect(self._remove_entry_row)
        entry_btn_row.addWidget(rm_entry_btn)
        entry_btn_row.addStretch()
        entries_layout.addLayout(entry_btn_row)

        right_layout.addWidget(entries_group, stretch=1)

        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save_set)
        right_layout.addWidget(save_btn)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

    def _refresh_list(self) -> None:
        self._list.clear()
        sets_dir = get_user_template_sets_dir()
        bundled_dir = Path(__file__).parent.parent.parent / "template_sets"

        for d in [bundled_dir, sets_dir]:
            if not d.exists():
                continue
            for f in sorted(d.glob("*.yaml")):
                try:
                    ts = load_template_set(f)
                    item = QListWidgetItem(ts.name)
                    item.setData(256, str(f))
                    self._list.addItem(item)
                except Exception:
                    pass

    @Slot()
    def _on_selection_changed(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        path = Path(item.data(256))
        try:
            ts = load_template_set(path)
            self._load_to_form(ts)
        except Exception as e:
            logger.exception("テンプレートセットの読み込みに失敗しました: %s", path)
            box = QMessageBox(self)
            box.setWindowTitle("読み込みエラー")
            box.setIcon(QMessageBox.Icon.Warning)
            box.setText(str(e))
            box.setInformativeText(
                "「詳細を表示」から全文をコピーできます。"
                " ログタブ・%APPDATA%\\OCRAutomation\\logs\\ にも記録されます。"
            )
            box.setDetailedText(traceback.format_exc())
            box.exec()

    def _load_to_form(self, ts: TemplateSet) -> None:
        self._name_edit.setText(ts.name)
        self._desc_edit.setText(ts.description)
        self._entries_table.setRowCount(0)
        for entry in ts.entries:
            self._add_entry_data(entry)

    def _add_entry_data(self, entry: TemplateSetEntry) -> None:
        row = self._entries_table.rowCount()
        self._entries_table.insertRow(row)
        self._entries_table.setItem(row, 0, QTableWidgetItem(entry.template_name))
        enabled_item = QTableWidgetItem()
        enabled_item.setCheckState(
            Qt.CheckState.Checked if entry.enabled else Qt.CheckState.Unchecked
        )
        self._entries_table.setItem(row, 1, enabled_item)
        self._entries_table.setItem(row, 2, QTableWidgetItem(entry.output_subfolder))
        print_item = QTableWidgetItem()
        print_item.setCheckState(
            Qt.CheckState.Checked if entry.auto_print else Qt.CheckState.Unchecked
        )
        self._entries_table.setItem(row, 3, print_item)
        self._entries_table.setItem(row, 4, QTableWidgetItem(entry.printer_name or ""))

    @Slot()
    def _add_entry_row(self) -> None:
        self._add_entry_data(TemplateSetEntry(
            template_name="", output_subfolder=""
        ))

    @Slot()
    def _remove_entry_row(self) -> None:
        current = self._entries_table.currentRow()
        if current >= 0:
            self._entries_table.removeRow(current)

    def _get_entries(self) -> list[TemplateSetEntry]:
        entries: list[TemplateSetEntry] = []
        for row in range(self._entries_table.rowCount()):
            name_item = self._entries_table.item(row, 0)
            enabled_item = self._entries_table.item(row, 1)
            sub_item = self._entries_table.item(row, 2)
            print_item = self._entries_table.item(row, 3)
            printer_item = self._entries_table.item(row, 4)

            tname = name_item.text().strip() if name_item else ""
            if not tname:
                continue

            entries.append(TemplateSetEntry(
                template_name=tname,
                enabled=(
                    enabled_item.checkState() == Qt.CheckState.Checked
                    if enabled_item
                    else True
                ),
                output_subfolder=sub_item.text().strip() if sub_item else "",
                auto_print=(
                    print_item.checkState() == Qt.CheckState.Checked
                    if print_item
                    else False
                ),
                printer_name=printer_item.text().strip() or None if printer_item else None,
            ))
        return entries

    @Slot()
    def _save_set(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "名前を入力してください")
            return

        ts = TemplateSet(
            name=name,
            description=self._desc_edit.text(),
            entries=self._get_entries(),
        )

        out_dir = get_user_template_sets_dir()
        safe_name = name.replace("/", "_").replace("\\", "_")
        path = out_dir / f"{safe_name}.yaml"

        data = ts.model_dump(mode="json")
        path.write_text(
            yaml.dump(data, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
        self.set_saved.emit(name)
        self._refresh_list()
        QMessageBox.information(self, "保存完了", f"セットを保存しました: {path.name}")

    @Slot()
    def _new_set(self) -> None:
        self._name_edit.clear()
        self._desc_edit.clear()
        self._entries_table.setRowCount(0)

    @Slot()
    def _delete_set(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        path = Path(item.data(256))
        reply = QMessageBox.question(self, "削除確認", f"{item.text()} を削除しますか?")
        if reply == QMessageBox.StandardButton.Yes:
            try:
                path.unlink()
                self._refresh_list()
            except Exception as e:
                QMessageBox.warning(self, "削除エラー", str(e))
