"""レビュー編集ダイアログ — 画像プレビューと抽出値の修正。"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.controllers.app_controller import AppController
from app.core.review_rules import source_keys_for_review_presence_marker
from app.core.template import TemplateEngine
from app.models.template_model import Template


class ZoomPanGraphicsView(QGraphicsView):
    """ズーム (ホイール) ・パン (ドラッグ) 付きプレビュー。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def wheelEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self.scale(factor, factor)

    def fit_content(self) -> None:
        self.resetTransform()
        r = self.scene().itemsBoundingRect()
        if r.isValid() and not r.isEmpty():
            self.fitInView(r, Qt.AspectRatioMode.KeepAspectRatio)

    def reset_zoom_100(self) -> None:
        self.resetTransform()


class ImagePreviewPane(QWidget):
    """QGraphicsView ベースの画像プレビュー (フィット / 100%)。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._view = ZoomPanGraphicsView(self)
        self._view.setScene(self._scene)

        fit_btn = QPushButton("フィット表示")
        fit_btn.clicked.connect(self._view.fit_content)
        pct_btn = QPushButton("100%表示")
        pct_btn.clicked.connect(self._view.reset_zoom_100)

        bar = QHBoxLayout()
        bar.addWidget(fit_btn)
        bar.addWidget(pct_btn)
        bar.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(bar)
        layout.addWidget(self._view, stretch=1)

    def load_path(self, path: Path) -> None:
        self._scene.clear()
        pix = QPixmap(str(path))
        if pix.isNull():
            self._scene.addText("プレビューを表示できません (非対応形式の可能性)")
            return
        self._scene.addPixmap(pix)
        self._view.fit_content()


class ReviewEditorDialog(QDialog):
    """非モーダル。開いている間もワーカーは停止しない。"""

    def __init__(
        self,
        controller: AppController,
        job_id: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("レビュー編集")
        self.setModal(False)
        self.resize(1100, 720)

        self._controller = controller
        self._job_id = job_id
        self._job = controller.get_review_job(job_id)
        if self._job is None:
            raise ValueError(f"ジョブが見つかりません: {job_id}")

        controller.mark_job_open_in_review(job_id)

        self._template_key: str | None = None
        self._template: Template | None = None
        self._field_widgets: dict[str, QLineEdit | QTextEdit] = {}

        self._preview = ImagePreviewPane()
        self._preview.load_path(self._job.source_file)

        self._template_combo = QComboBox()
        self._template_combo.currentIndexChanged.connect(self._on_template_changed)

        self._reasons_label = QLabel()
        self._reasons_label.setWordWrap(True)
        self._reasons_label.setText("\n".join(self._job.review_reasons) or "—")

        self._errors_label = QLabel()
        self._errors_label.setWordWrap(True)
        self._errors_label.setStyleSheet("color: #c0392b;")

        self._form_host = QWidget()
        self._form_layout = QFormLayout(self._form_host)

        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setWidget(self._form_host)

        right = QVBoxLayout()
        right.addWidget(QLabel("テンプレート"))
        right.addWidget(self._template_combo)
        reasons_box = QGroupBox("レビュー理由")
        rb_layout = QVBoxLayout(reasons_box)
        rb_layout.addWidget(self._reasons_label)
        right.addWidget(reasons_box)
        right.addWidget(form_scroll, stretch=1)
        right.addWidget(self._errors_label)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._on_save)
        approve_btn = QPushButton("承認して出力")
        approve_btn.clicked.connect(self._on_approve)
        reject_btn = QPushButton("却下")
        reject_btn.clicked.connect(self._on_reject)
        close_btn = QPushButton("閉じる")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(approve_btn)
        btn_row.addWidget(reject_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        right.addLayout(btn_row)

        main = QHBoxLayout(self)
        left_box = QGroupBox("元画像")
        left_layout = QVBoxLayout(left_box)
        left_layout.addWidget(self._preview)
        main.addWidget(left_box, stretch=1)
        main.addLayout(right, stretch=1)

        self._populate_template_combo()

    def _populate_template_combo(self) -> None:
        keys = sorted(self._job.normalized_result.keys())
        for k in keys:
            self._template_combo.addItem(k, k)
        if keys:
            self._template_combo.setCurrentIndex(0)

    def _on_template_changed(self, index: int) -> None:
        if index < 0:
            return
        key = self._template_combo.itemData(index)
        if not isinstance(key, str):
            return
        if self._template_key is not None and self._template_key != key:
            self._persist_current_template()
        self._load_template(key)

    def _load_template(self, template_key: str) -> None:
        self._template_key = template_key
        self._template = self._controller.templates.get(template_key)
        while self._form_layout.rowCount():
            self._form_layout.removeRow(0)
        self._field_widgets.clear()

        if self._template is None:
            self._form_layout.addRow(QLabel("テンプレート定義が見つかりません"))
            return

        mapped = self._current_mapped_for_key(template_key)
        raw = mapped.get("__raw__", {})
        if not isinstance(raw, dict):
            raw = {}

        marked_for_review = source_keys_for_review_presence_marker(self._template)
        display_by_key: dict[str, str] = {}
        for fp in self._template.field_placements:
            if fp.display_name and fp.source_key not in display_by_key:
                display_by_key[fp.source_key] = fp.display_name

        schema = self._template.response_schema
        prop_keys: list[str] = []
        props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        if isinstance(props, dict):
            prop_keys = list(props.keys())

        ordered_keys: list[str] = []
        for pk in prop_keys:
            if pk not in ordered_keys:
                ordered_keys.append(pk)
        for k in sorted(raw.keys()):
            if k != "__raw__" and k not in ordered_keys:
                ordered_keys.append(k)

        for key in ordered_keys:
            val = raw.get(key)
            base_label = display_by_key.get(key, key)
            label = f"{base_label} *" if key in marked_for_review else base_label
            if isinstance(val, list | dict):
                te = QTextEdit()
                te.setPlainText(json.dumps(val, ensure_ascii=False, indent=2))
                te.setMinimumHeight(80)
                self._form_layout.addRow(label, te)
                self._field_widgets[key] = te
            else:
                le = QLineEdit("" if val is None else str(val))
                self._form_layout.addRow(label, le)
                self._field_widgets[key] = le

    def _current_mapped_for_key(self, template_key: str) -> dict[str, Any]:
        job = self._controller.get_review_job(self._job_id)
        assert job is not None
        if template_key in job.user_corrected_result:
            return copy.deepcopy(job.user_corrected_result[template_key])
        return copy.deepcopy(job.normalized_result.get(template_key, {}))

    def _persist_current_template(self) -> None:
        if self._job is None or self._template_key is None or self._template is None:
            return
        job = self._controller.get_review_job(self._job_id)
        if job is None:
            return
        raw = self._read_raw_from_widgets()
        mapped = TemplateEngine._map_fields(raw, self._template)
        job.user_corrected_result[self._template_key] = mapped

    def _read_raw_from_widgets(self) -> dict[str, Any]:
        if self._template is None:
            return {}
        raw: dict[str, Any] = {}
        for key, w in self._field_widgets.items():
            if isinstance(w, QLineEdit):
                raw[key] = w.text()
            elif isinstance(w, QTextEdit):
                text = w.toPlainText().strip()
                if not text:
                    raw[key] = [] if key in self._guess_array_keys() else {}
                else:
                    try:
                        raw[key] = json.loads(text)
                    except json.JSONDecodeError:
                        raw[key] = text
        return raw

    def _guess_array_keys(self) -> set[str]:
        props = self._template.response_schema.get("properties") if self._template else {}
        if not isinstance(props, dict):
            return set()
        return {k for k, v in props.items() if isinstance(v, dict) and v.get("type") == "array"}

    def _on_save(self) -> None:
        self._persist_current_template()
        job = self._controller.get_review_job(self._job_id)
        if job:
            self._controller.save_review_job(job)
        self._errors_label.clear()
        QMessageBox.information(self, "保存", "保存しました。")

    def _on_approve(self) -> None:
        self._persist_current_template()
        job = self._controller.get_review_job(self._job_id)
        if job is None:
            return
        self._controller.save_review_job(job)
        ok, msg = self._controller.approve_review(self._job_id, None)
        if ok:
            QMessageBox.information(self, "承認", "承認して出力しました。")
            self.accept()
        else:
            self._errors_label.setText(msg)

    def _on_reject(self) -> None:
        reason, ok = QInputDialog.getText(self, "却下", "却下理由 (任意):")
        if not ok:
            return
        self._persist_current_template()
        job = self._controller.get_review_job(self._job_id)
        if job:
            self._controller.save_review_job(job)
        rok, rmsg = self._controller.reject_review(self._job_id, reason)
        if rok:
            QMessageBox.information(self, "却下", "却下して失敗フォルダへ移動しました。")
            self.accept()
        else:
            QMessageBox.warning(self, "エラー", rmsg)
