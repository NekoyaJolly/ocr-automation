"""テンプレートエディタパネル。

テンプレートの新規作成・複製・削除・編集を行う。
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
from app.models.template_model import FieldMapping, Template

logger = logging.getLogger(__name__)


class TemplateEditorPanel(QWidget):
    """テンプレートの管理およびフィールドマッピングを編集する UI パネル。"""

    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._current_template: Template | None = None
        self._setup_ui()
        self.refresh_list()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        # 全体を左右に分割するスプリッター
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # --- 左ペイン: テンプレート一覧 ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("テンプレート一覧"))

        self._template_list = QListWidget()
        self._template_list.itemSelectionChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self._template_list)

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

        # テンプレート名
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("テンプレート名:"))
        self._name_edit = QLineEdit()
        name_layout.addWidget(self._name_edit)
        basic_layout.addLayout(name_layout)

        # 説明
        desc_layout = QHBoxLayout()
        desc_layout.addWidget(QLabel("説明:"))
        self._desc_edit = QLineEdit()
        desc_layout.addWidget(self._desc_edit)
        basic_layout.addLayout(desc_layout)

        # 出力形式 & ファイル名パターン
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("出力形式:"))
        self._format_combo = QComboBox()
        self._format_combo.addItems(["txt", "docx", "xlsx", "pdf"])
        self._format_combo.currentTextChanged.connect(self._on_format_changed)
        format_layout.addWidget(self._format_combo)

        format_layout.addWidget(QLabel("ファイル名パターン:"))
        self._pattern_edit = QLineEdit()
        format_layout.addWidget(self._pattern_edit, stretch=1)
        basic_layout.addLayout(format_layout)

        # ベースファイル
        base_layout = QHBoxLayout()
        base_layout.addWidget(QLabel("テンプレートファイル名(オプション):"))
        self._base_edit = QLineEdit()
        base_layout.addWidget(self._base_edit)
        basic_layout.addLayout(base_layout)

        right_layout.addWidget(basic_group)

        # 2. フィールドマッピング
        mapping_group = QGroupBox("フィールドマッピング設定")
        mapping_layout = QVBoxLayout(mapping_group)

        self._mapping_table = QTableWidget()
        self._mapping_table.setColumnCount(7)
        self._mapping_table.setHorizontalHeaderLabels(
            ["出力ラベル", "抽出キー / 正規表現", "抽出方法", "データ型", "書式指定", "Excelセル番地等", "BBox (x,y,w,h)"]
        )
        mapping_layout.addWidget(self._mapping_table)

        # テーブル操作ボタン
        table_btn_layout = QHBoxLayout()
        self._add_row_btn = QPushButton("行追加")
        self._del_row_btn = QPushButton("行削除")
        self._add_row_btn.clicked.connect(self._on_add_row)
        self._del_row_btn.clicked.connect(self._on_del_row)
        table_btn_layout.addWidget(self._add_row_btn)
        table_btn_layout.addWidget(self._del_row_btn)
        table_btn_layout.addStretch()
        mapping_layout.addLayout(table_btn_layout)

        right_layout.addWidget(mapping_group)

        # 保存ボタン
        self._save_btn = QPushButton("保存")
        self._save_btn.clicked.connect(self._on_save)
        self._save_btn.setMinimumHeight(40)
        right_layout.addWidget(self._save_btn)

        splitter.addWidget(self._right_widget)

        # スプリッターの比率設定 (左 30%, 右 70%)
        splitter.setSizes([200, 500])

        # 初期状態は右側非表示
        self._right_widget.setEnabled(False)

    def refresh_list(self) -> None:
        """テンプレート一覧を再読み込みしてリストを更新する。"""
        self._template_list.clear()
        templates = self._controller.get_available_templates()
        for name in templates:
            self._template_list.addItem(name)
        self._right_widget.setEnabled(False)
        self._current_template = None

    @Slot()
    def _on_selection_changed(self) -> None:
        """リスト選択変更時に選択内容をフォームに読み込む。"""
        selected_items = self._template_list.selectedItems()
        if not selected_items:
            self._right_widget.setEnabled(False)
            return

        name = selected_items[0].text()
        template = self._controller.load_template_by_name(name)
        if template:
            self._current_template = template
            self._load_template_to_form(template)
            self._right_widget.setEnabled(True)
            # 保存済みテンプレートの名称変更は不可にする（ファイル名の変更を防ぐため。変更したい場合は複製して作成）
            self._name_edit.setEnabled(False)

    def _load_template_to_form(self, template: Template) -> None:
        """テンプレートモデルをフォーム UI に反映する。"""
        self._name_edit.setText(template.name)
        self._desc_edit.setText(template.description)
        self._format_combo.setCurrentText(template.output_format)
        self._pattern_edit.setText(template.output_filename_pattern)
        self._base_edit.setText(template.template_file or "")

        self._mapping_table.setRowCount(0)
        for field in template.fields:
            self._add_row_with_data(field)

    def _add_row_with_data(self, field: FieldMapping | None = None) -> None:
        """マッピングテーブルに 1 行追加し、必要に応じて初期データを流し込む。"""
        row = self._mapping_table.rowCount()
        self._mapping_table.insertRow(row)

        # 出力ラベル
        label_item = QTableWidgetItem(field.output_label if field else "")
        self._mapping_table.setItem(row, 0, label_item)

        # 抽出キー
        key_item = QTableWidgetItem(field.source_key if field else "")
        self._mapping_table.setItem(row, 1, key_item)

        # 抽出方法コンボボックス
        ext_combo = QComboBox()
        ext_combo.addItems(["keyword", "position"])
        if field:
            ext_combo.setCurrentText(field.extraction_type)
        self._mapping_table.setCellWidget(row, 2, ext_combo)

        # データ型コンボボックス
        type_combo = QComboBox()
        type_combo.addItems(["string", "number", "date", "currency"])
        if field:
            type_combo.setCurrentText(field.data_type)
        self._mapping_table.setCellWidget(row, 3, type_combo)

        # 書式指定
        fmt_item = QTableWidgetItem(field.format_string if (field and field.format_string) else "")
        self._mapping_table.setItem(row, 4, fmt_item)

        # Excelセル番地等
        pos_item = QTableWidgetItem(field.target_position if field else "")
        self._mapping_table.setItem(row, 5, pos_item)

        # BBox
        bbox_str = ""
        if field and field.bbox:
            bbox_str = ",".join(map(str, field.bbox))
        bbox_item = QTableWidgetItem(bbox_str)
        self._mapping_table.setItem(row, 6, bbox_item)

    @Slot()
    def _on_format_changed(self, text: str) -> None:
        """フォーマット変更時にファイル名パターンの拡張子を自動調整する。"""
        pattern = self._pattern_edit.text()
        if not pattern:
            self._pattern_edit.setText(f"{{date}}_{{source_basename}}_output.{text}")

    @Slot()
    def _on_add_row(self) -> None:
        self._add_row_with_data(None)

    @Slot()
    def _on_del_row(self) -> None:
        current_row = self._mapping_table.currentRow()
        if current_row >= 0:
            self._mapping_table.removeRow(current_row)

    @Slot()
    def _on_new(self) -> None:
        """新規テンプレート編集画面を開く。"""
        self._template_list.clearSelection()
        self._current_template = None

        self._name_edit.setText("新規テンプレート")
        self._name_edit.setEnabled(True)
        self._desc_edit.setText("")
        self._format_combo.setCurrentText("txt")
        self._pattern_edit.setText("{date}_{source_basename}_output.txt")
        self._base_edit.setText("")

        self._mapping_table.setRowCount(0)
        self._right_widget.setEnabled(True)
        self._name_edit.setFocus()

    @Slot()
    def _on_copy(self) -> None:
        """選択されているテンプレートを複製する。"""
        if not self._current_template:
            return
        
        # 複製用のコピーを作成
        copied = self._current_template.model_copy(deep=True)
        copied.name = f"{copied.name}_copy"

        self._current_template = copied
        self._load_template_to_form(copied)
        self._name_edit.setEnabled(True)
        self._name_edit.setFocus()
        self._template_list.clearSelection()

    @Slot()
    def _on_delete(self) -> None:
        """選択されているテンプレートを削除する。"""
        selected_items = self._template_list.selectedItems()
        if not selected_items:
            return

        name = selected_items[0].text()
        reply = QMessageBox.question(
            self,
            "削除確認",
            f"テンプレート '{name}' を削除しますか？\n(設定されている YAML ファイルが物理的に削除されます)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._controller.delete_template(name)
                self.refresh_list()
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"削除に失敗しました: {e}")

    @Slot()
    def _on_save(self) -> None:
        """入力フォームの内容を Template モデルとしてバリデーションし保存する。"""
        name = self._name_edit.text().strip()
        if not name or name == "新規テンプレート":
            QMessageBox.warning(self, "警告", "有効なテンプレート名を入力してください。")
            return

        fields = []
        for row in range(self._mapping_table.rowCount()):
            # テーブルセルの値を取得
            label = self._get_item_text(row, 0)
            key = self._get_item_text(row, 1)
            ext_type = self._mapping_table.cellWidget(row, 2).currentText()
            d_type = self._mapping_table.cellWidget(row, 3).currentText()
            fmt = self._get_item_text(row, 4) or None
            pos = self._get_item_text(row, 5)
            bbox_str = self._get_item_text(row, 6)

            if not label:
                QMessageBox.warning(self, "警告", f"{row + 1}行目の出力ラベルが未入力です。")
                return

            bbox = None
            if bbox_str:
                try:
                    parts = list(map(int, bbox_str.split(",")))
                    if len(parts) != 4:
                        raise ValueError
                    bbox = (parts[0], parts[1], parts[2], parts[3])
                except ValueError:
                    QMessageBox.warning(
                        self,
                        "警告",
                        f"{row + 1}行目の bbox 指定形式が不正です。x,y,w,h (整数4つ) で入力してください。",
                    )
                    return

            fields.append(
                FieldMapping(
                    source_key=key,
                    output_label=label,
                    target_position=pos,
                    data_type=d_type,
                    format_string=fmt,
                    extraction_type=ext_type,
                    bbox=bbox,
                )
            )

        # Template モデルの構築
        template = Template(
            name=name,
            description=self._desc_edit.text().strip(),
            output_format=self._format_combo.currentText(),
            output_filename_pattern=self._pattern_edit.text().strip(),
            template_file=self._base_edit.text().strip() or None,
            fields=fields,
        )

        try:
            self._controller.save_template(template)
            QMessageBox.information(self, "成功", "テンプレートを保存しました。")
            # リストを再表示し、新しく保存したアイテムを選択状態にする
            self.refresh_list()
            # リスト内を検索して再選択
            items = self._template_list.findItems(name, Qt.MatchFlag.MatchExactly)
            if items:
                self._template_list.setCurrentItem(items[0])
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"保存に失敗しました:\n{e}")

    def _get_item_text(self, row: int, col: int) -> str:
        item = self._mapping_table.item(row, col)
        return item.text().strip() if item else ""
