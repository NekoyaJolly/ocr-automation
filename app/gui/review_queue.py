"""レビュー待ちジョブ一覧。"""

from __future__ import annotations

from functools import partial

from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.app_controller import AppController
from app.models.job_model import ReviewStatus


class ReviewQueueWidget(QWidget):
    """レビュー待ち一覧。行の「開く」で編集ダイアログへ。"""

    open_review_requested = Signal(str)

    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["ファイル名", "テンプレートセット", "レビュー理由", "作成時刻", "状態", ""]
        )
        hdr = self._table.horizontalHeader()
        rtc = QHeaderView.ResizeMode.ResizeToContents
        hdr.setSectionResizeMode(0, rtc)
        hdr.setSectionResizeMode(1, rtc)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, rtc)
        hdr.setSectionResizeMode(4, rtc)
        hdr.setSectionResizeMode(5, rtc)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout = QVBoxLayout(self)
        layout.addWidget(self._table)

        self._controller.review_queue_count_changed.connect(self._on_count_changed)

    def showEvent(self, event: QShowEvent) -> None:  # type: ignore[override]
        super().showEvent(event)
        self.refresh()

    @Slot(int)
    def _on_count_changed(self, _n: int) -> None:
        self.refresh()

    def refresh(self) -> None:
        jobs = self._controller.get_review_jobs()
        self._table.setRowCount(len(jobs))
        for row, job in enumerate(jobs):
            self._table.setItem(row, 0, QTableWidgetItem(job.source_file.name))
            self._table.setItem(row, 1, QTableWidgetItem(job.template_set_name))
            reasons = "\n".join(job.review_reasons[:5])
            if len(job.review_reasons) > 5:
                reasons += "\n…"
            self._table.setItem(row, 2, QTableWidgetItem(reasons))
            self._table.setItem(
                row,
                3,
                QTableWidgetItem(job.created_at.strftime("%Y-%m-%d %H:%M")),
            )
            self._table.setItem(row, 4, QTableWidgetItem(_review_status_label(job.review_status)))

            open_btn = QPushButton("開く")
            open_btn.clicked.connect(partial(self.open_review_requested.emit, job.job_id))
            cell = QWidget()
            h = QHBoxLayout(cell)
            h.setContentsMargins(2, 2, 2, 2)
            h.addWidget(open_btn)
            self._table.setCellWidget(row, 5, cell)


def _review_status_label(status: ReviewStatus) -> str:
    return {
        ReviewStatus.PENDING: "待ち",
        ReviewStatus.IN_REVIEW: "確認中",
        ReviewStatus.NOT_REQUIRED: "—",
        ReviewStatus.APPROVED: "承認済",
        ReviewStatus.REJECTED: "却下",
    }.get(status, str(status))
