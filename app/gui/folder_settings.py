"""フォルダ設定画面。"""

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.models.settings_model import FolderSettings


class FolderPathSelector(QWidget):
    """フォルダパス選択ウィジェット。"""

    path_changed = Signal(str)

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel(label))
        self._edit = QLineEdit()
        self._edit.setReadOnly(True)
        layout.addWidget(self._edit, stretch=1)

        browse_btn = QPushButton("参照...")
        browse_btn.clicked.connect(self._browse)
        layout.addWidget(browse_btn)

        open_btn = QPushButton("開く")
        open_btn.clicked.connect(self._open_folder)
        layout.addWidget(open_btn)

    def get_path(self) -> str:
        return self._edit.text()

    def set_path(self, path: str) -> None:
        self._edit.setText(path)

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "フォルダを選択")
        if folder:
            self._edit.setText(folder)
            self.path_changed.emit(folder)

    def _open_folder(self) -> None:
        path = self._edit.text()
        if path and Path(path).exists():
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
            elif sys.platform == "win32":
                subprocess.Popen(["explorer", path])


class SubfolderMappingWidget(QWidget):
    """サブフォルダ → テンプレートセット割り当てウィジェット。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._rows: list[tuple[QLabel, QComboBox]] = []
        self._available_sets: list[str] = []

    def set_available_sets(self, set_names: list[str]) -> None:
        self._available_sets = set_names

    def refresh(self, input_root: Path, current_mapping: dict[str, str]) -> None:
        """入力ルート配下のサブフォルダを列挙して UI に反映する。"""
        for label, combo in self._rows:
            label.deleteLater()
            combo.deleteLater()
        self._rows.clear()

        if not input_root.exists():
            return

        subfolders = sorted(
            [d.name for d in input_root.iterdir() if d.is_dir()],
        )

        for sf in subfolders:
            row = QHBoxLayout()
            label = QLabel(sf)
            combo = QComboBox()
            combo.addItem("(未設定)")
            combo.addItems(self._available_sets)

            current = current_mapping.get(sf, "")
            if current and current in self._available_sets:
                combo.setCurrentText(current)

            row.addWidget(label)
            row.addWidget(combo, stretch=1)

            container = QWidget()
            container.setLayout(row)
            self._layout.addWidget(container)
            self._rows.append((label, combo))

    def get_mapping(self, input_root: Path) -> dict[str, str]:
        """現在の割り当てを辞書で返す。"""
        mapping: dict[str, str] = {}
        subfolders = sorted(
            [d.name for d in input_root.iterdir() if d.is_dir()]
        ) if input_root.exists() else []

        for i, sf in enumerate(subfolders):
            if i < len(self._rows):
                _, combo = self._rows[i]
                val = combo.currentText()
                if val != "(未設定)":
                    mapping[sf] = val
        return mapping


class FolderSettingsWidget(QWidget):
    """フォルダ設定画面全体。"""

    settings_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        folder_group = QGroupBox("フォルダ設定")
        folder_layout = QVBoxLayout(folder_group)

        self._input_root = FolderPathSelector("入力ルート:")
        self._output_root = FolderPathSelector("出力ルート:")
        self._failed_folder = FolderPathSelector("失敗フォルダ:")
        self._processed_folder = FolderPathSelector("処理済みフォルダ:")

        folder_layout.addWidget(self._input_root)
        folder_layout.addWidget(self._output_root)
        folder_layout.addWidget(self._failed_folder)
        folder_layout.addWidget(self._processed_folder)
        layout.addWidget(folder_group)

        mapping_group = QGroupBox("サブフォルダ → テンプレートセット割り当て")
        mapping_layout = QVBoxLayout(mapping_group)

        self._mapping = SubfolderMappingWidget()
        scroll = QScrollArea()
        scroll.setWidget(self._mapping)
        scroll.setWidgetResizable(True)
        mapping_layout.addWidget(scroll)

        refresh_btn = QPushButton("サブフォルダ一覧を更新")
        refresh_btn.clicked.connect(self._refresh_subfolders)
        mapping_layout.addWidget(refresh_btn)

        layout.addWidget(mapping_group, stretch=1)

    def load_settings(
        self, folder_settings: FolderSettings, available_sets: list[str]
    ) -> None:
        """設定値を UI に反映する。"""
        self._input_root.set_path(str(folder_settings.input_root))
        self._output_root.set_path(str(folder_settings.output_root))
        self._failed_folder.set_path(str(folder_settings.failed_folder))
        self._processed_folder.set_path(str(folder_settings.processed_folder))
        self._mapping.set_available_sets(available_sets)
        self._mapping.refresh(
            folder_settings.input_root, folder_settings.subfolder_to_set
        )

    def get_settings(self) -> FolderSettings:
        """UI の現在値から FolderSettings を構築して返す。"""
        input_root = Path(self._input_root.get_path())
        return FolderSettings(
            input_root=input_root,
            output_root=Path(self._output_root.get_path()),
            failed_folder=Path(self._failed_folder.get_path()),
            processed_folder=Path(self._processed_folder.get_path()),
            subfolder_to_set=self._mapping.get_mapping(input_root),
        )

    def _refresh_subfolders(self) -> None:
        input_root = Path(self._input_root.get_path())
        if input_root.exists():
            self._mapping.refresh(input_root, {})
