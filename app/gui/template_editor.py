"""テンプレートエディタ画面。"""

import json
from pathlib import Path

import yaml
from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.core.template import load_template
from app.gui.widgets.field_placement_editor import FieldPlacementEditor
from app.infrastructure.logger import get_logger
from app.infrastructure.paths import get_user_templates_dir
from app.models.template_model import Template

logger = get_logger(__name__)


class TemplateEditorWidget(QWidget):
    """テンプレートの作成・編集・削除を行うエディタ画面。"""

    template_saved = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_template: Template | None = None
        self._setup_ui()
        self._refresh_list()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)

        splitter = QSplitter()

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("テンプレート一覧"))
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self._list, stretch=1)

        btn_row = QHBoxLayout()
        new_btn = QPushButton("新規")
        new_btn.clicked.connect(self._new_template)
        btn_row.addWidget(new_btn)
        dup_btn = QPushButton("複製")
        dup_btn.clicked.connect(self._duplicate_template)
        btn_row.addWidget(dup_btn)
        del_btn = QPushButton("削除")
        del_btn.clicked.connect(self._delete_template)
        btn_row.addWidget(del_btn)
        left_layout.addLayout(btn_row)

        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        basic_group = QGroupBox("基本設定")
        basic_form = QFormLayout(basic_group)
        self._name_edit = QLineEdit()
        self._desc_edit = QLineEdit()
        self._format_combo = QComboBox()
        self._format_combo.addItems(["txt", "docx", "xlsx", "pdf"])
        self._filename_edit = QLineEdit()
        self._filename_edit.setPlaceholderText("{invoice_no}_{date}.xlsx")
        self._base_file_edit = QLineEdit()
        self._base_file_edit.setPlaceholderText("(空 = 新規作成)")

        basic_form.addRow("名前:", self._name_edit)
        basic_form.addRow("説明:", self._desc_edit)
        basic_form.addRow("出力形式:", self._format_combo)
        basic_form.addRow("ファイル名パターン:", self._filename_edit)
        basic_form.addRow("ベーステンプレート:", self._base_file_edit)
        right_layout.addWidget(basic_group)

        prompt_group = QGroupBox("抽出プロンプト")
        prompt_layout = QVBoxLayout(prompt_group)
        self._prompt_edit = QPlainTextEdit()
        self._prompt_edit.setPlaceholderText("Gemini への指示文を入力...")
        prompt_layout.addWidget(self._prompt_edit)
        right_layout.addWidget(prompt_group)

        schema_group = QGroupBox("JSON Schema")
        schema_layout = QVBoxLayout(schema_group)
        self._schema_edit = QPlainTextEdit()
        self._schema_edit.setPlaceholderText('{"type": "object", "properties": {...}}')
        schema_layout.addWidget(self._schema_edit)
        right_layout.addWidget(schema_group)

        placement_group = QGroupBox("フィールド配置")
        placement_layout = QVBoxLayout(placement_group)
        self._placement_editor = FieldPlacementEditor()
        placement_layout.addWidget(self._placement_editor)
        right_layout.addWidget(placement_group)

        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save_template)
        right_layout.addWidget(save_btn)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

    def _refresh_list(self) -> None:
        self._list.clear()
        tmpl_dir = get_user_templates_dir()
        bundled_dir = Path(__file__).parent.parent.parent / "templates"

        for d in [bundled_dir, tmpl_dir]:
            if not d.exists():
                continue
            for f in sorted(d.glob("*.yaml")):
                try:
                    t = load_template(f)
                    item = QListWidgetItem(t.name)
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
            tmpl = load_template(path)
            self._load_to_form(tmpl)
            self._current_template = tmpl
        except Exception as e:
            QMessageBox.warning(self, "読み込みエラー", str(e))

    def _load_to_form(self, t: Template) -> None:
        self._name_edit.setText(t.name)
        self._desc_edit.setText(t.description)
        self._format_combo.setCurrentText(t.output_format)
        self._filename_edit.setText(t.output_filename_pattern)
        self._base_file_edit.setText(t.base_template_file or "")
        self._prompt_edit.setPlainText(t.extraction_prompt)
        self._schema_edit.setPlainText(
            json.dumps(t.response_schema, ensure_ascii=False, indent=2)
        )
        self._placement_editor.load_placements(t.field_placements)

    def _form_to_template(self) -> Template:
        schema_text = self._schema_edit.toPlainText()
        try:
            schema = json.loads(schema_text) if schema_text.strip() else {}
        except json.JSONDecodeError:
            schema = yaml.safe_load(schema_text) or {}

        return Template(
            name=self._name_edit.text(),
            description=self._desc_edit.text(),
            output_format=self._format_combo.currentText(),
            output_filename_pattern=self._filename_edit.text(),
            base_template_file=self._base_file_edit.text() or None,
            extraction_prompt=self._prompt_edit.toPlainText(),
            response_schema=schema,
            field_placements=self._placement_editor.get_placements(),
        )

    @Slot()
    def _save_template(self) -> None:
        try:
            tmpl = self._form_to_template()
        except Exception as e:
            QMessageBox.warning(self, "入力エラー", str(e))
            return

        if not tmpl.name:
            QMessageBox.warning(self, "入力エラー", "名前を入力してください")
            return

        out_dir = get_user_templates_dir()
        safe_name = tmpl.name.replace("/", "_").replace("\\", "_")
        path = out_dir / f"{safe_name}.yaml"

        data = tmpl.model_dump(mode="json")
        path.write_text(
            yaml.dump(data, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
        self.template_saved.emit(tmpl.name)
        self._refresh_list()
        QMessageBox.information(self, "保存完了", f"テンプレートを保存しました: {path.name}")

    @Slot()
    def _new_template(self) -> None:
        self._name_edit.clear()
        self._desc_edit.clear()
        self._filename_edit.clear()
        self._base_file_edit.clear()
        self._prompt_edit.clear()
        self._schema_edit.clear()
        self._placement_editor.clear()
        self._current_template = None

    @Slot()
    def _duplicate_template(self) -> None:
        if self._current_template is None:
            return
        self._name_edit.setText(self._current_template.name + " (コピー)")

    @Slot()
    def _delete_template(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        path = Path(item.data(256))
        reply = QMessageBox.question(
            self, "削除確認", f"{item.text()} を削除しますか?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                path.unlink()
                self._refresh_list()
            except Exception as e:
                QMessageBox.warning(self, "削除エラー", str(e))
