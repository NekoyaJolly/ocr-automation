"""フォルダ設定パネル。

入力ルート・出力ルート・失敗フォルダの 3 つのフォルダパスを選択・表示する。
メインウィンドウ内のタブとして配置される。
"""

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.settings_model import AppSettings


class FolderSettingsPanel(QWidget):
    """フォルダ設定パネル。

    Signals:
        settings_changed(AppSettings): フォルダが変更されたときに発火
    """

    settings_changed = Signal(object)

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        """パネルを初期化する。

        Args:
            settings: 現在のアプリケーション設定
        """
        super().__init__(parent)
        self._settings = settings
        self._setup_ui()
        self._load_from_settings()

    def _setup_ui(self) -> None:
        """UI を構築する。"""
        layout = QVBoxLayout(self)

        self._input_row = self._create_folder_row("入力ルートフォルダ")
        self._output_row = self._create_folder_row("出力ルートフォルダ")
        self._failed_row = self._create_folder_row("失敗フォルダ")

        layout.addWidget(self._input_row["group"])
        layout.addWidget(self._output_row["group"])
        layout.addWidget(self._failed_row["group"])
        layout.addStretch()

    def _create_folder_row(self, label_text: str) -> dict:
        """フォルダ選択行を 1 つ作成する。

        Returns:
            group, label, select_btn, open_btn を持つ dict
        """
        group = QGroupBox(label_text)
        h_layout = QHBoxLayout(group)

        path_label = QLabel("（未設定）")
        path_label.setMinimumWidth(300)

        select_btn = QPushButton("選択...")
        select_btn.setFixedWidth(80)
        select_btn.clicked.connect(lambda: self._on_select_folder(label_text, path_label))

        open_btn = QPushButton("開く")
        open_btn.setFixedWidth(60)
        open_btn.clicked.connect(lambda: self._on_open_folder(path_label.text()))

        h_layout.addWidget(path_label, stretch=1)
        h_layout.addWidget(select_btn)
        h_layout.addWidget(open_btn)

        return {
            "group": group,
            "label": path_label,
            "select_btn": select_btn,
            "open_btn": open_btn,
        }

    def _load_from_settings(self) -> None:
        """設定から各フォルダパスを読み込んでラベルに反映する。"""
        folders = self._settings.folders
        if folders.input_root:
            self._input_row["label"].setText(str(folders.input_root))
        if folders.output_root:
            self._output_row["label"].setText(str(folders.output_root))
        if folders.failed_folder:
            self._failed_row["label"].setText(str(folders.failed_folder))

    def update_settings(self, settings: AppSettings) -> None:
        """外部から設定オブジェクトを更新する。

        Args:
            settings: 新しい設定
        """
        self._settings = settings
        self._load_from_settings()

    def _on_select_folder(self, folder_type: str, path_label: QLabel) -> None:
        """フォルダ選択ダイアログを表示する。"""
        current = path_label.text()
        start_dir = current if current != "（未設定）" else ""

        selected = QFileDialog.getExistingDirectory(
            self,
            f"{folder_type}を選択",
            start_dir,
        )
        if not selected:
            return

        path_label.setText(selected)
        self._apply_to_settings()

    def _apply_to_settings(self) -> None:
        """UI の状態を設定オブジェクトに反映して Signal を発火する。"""
        input_text = self._input_row["label"].text()
        output_text = self._output_row["label"].text()
        failed_text = self._failed_row["label"].text()

        self._settings.folders.input_root = (
            Path(input_text) if input_text != "（未設定）" else None
        )
        self._settings.folders.output_root = (
            Path(output_text) if output_text != "（未設定）" else None
        )
        self._settings.folders.failed_folder = (
            Path(failed_text) if failed_text != "（未設定）" else None
        )

        self.settings_changed.emit(self._settings)

    @staticmethod
    def _on_open_folder(path_text: str) -> None:
        """OS のファイルマネージャでフォルダを開く。"""
        if path_text == "（未設定）":
            return
        folder = Path(path_text)
        if not folder.exists():
            return

        match sys.platform:
            case "win32":
                import os
                os.startfile(str(folder))  # noqa: S606
            case "darwin":
                subprocess.Popen(["open", str(folder)])  # noqa: S603, S607
            case _:
                subprocess.Popen(["xdg-open", str(folder)])  # noqa: S603, S607
