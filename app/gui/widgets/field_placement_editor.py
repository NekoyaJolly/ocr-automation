"""フィールド配置の編集ウィジェット。"""

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.template_model import FieldPlacement


class FieldPlacementEditor(QWidget):
    """テンプレートの field_placements を編集するテーブルウィジェット。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ["source_key", "target", "format_string", "expand"]
        )
        header = self._table.horizontalHeader()
        if header:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("行追加")
        add_btn.clicked.connect(self._add_row)
        btn_row.addWidget(add_btn)
        remove_btn = QPushButton("行削除")
        remove_btn.clicked.connect(self._remove_row)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def load_placements(self, placements: list[FieldPlacement]) -> None:
        """フィールド配置リストをテーブルに読み込む。"""
        self._table.setRowCount(0)
        for fp in placements:
            self._add_row_data(fp)

    def get_placements(self) -> list[FieldPlacement]:
        """テーブルの現在値から FieldPlacement リストを返す。"""
        placements: list[FieldPlacement] = []
        for row in range(self._table.rowCount()):
            source = self._get_cell(row, 0)
            target = self._get_cell(row, 1)
            fmt = self._get_cell(row, 2) or None
            expand = self._get_cell(row, 3) or "none"
            if source and target:
                placements.append(
                    FieldPlacement(
                        source_key=source,
                        target=target,
                        format_string=fmt,
                        expand=expand,  # type: ignore[arg-type]
                    )
                )
        return placements

    def clear(self) -> None:
        """テーブルをクリアする。"""
        self._table.setRowCount(0)

    @Slot()
    def _add_row(self) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)

    def _add_row_data(self, fp: FieldPlacement) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(fp.source_key))
        self._table.setItem(row, 1, QTableWidgetItem(fp.target))
        self._table.setItem(row, 2, QTableWidgetItem(fp.format_string or ""))
        self._table.setItem(row, 3, QTableWidgetItem(fp.expand))

    @Slot()
    def _remove_row(self) -> None:
        current = self._table.currentRow()
        if current >= 0:
            self._table.removeRow(current)

    def _get_cell(self, row: int, col: int) -> str:
        item = self._table.item(row, col)
        return item.text().strip() if item else ""
