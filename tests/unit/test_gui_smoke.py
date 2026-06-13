"""GUI スモークテスト。

pytest-qt を使用して、メインウィンドウが起動・終了できることを確認する。
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pytestqt.qtbot import QtBot

from app.controllers.app_controller import AppController
from app.gui.folder_settings import FolderSettingsPanel
from app.gui.log_viewer import LogViewer
from app.gui.main_window import MainWindow
from app.gui.template_editor import TemplateEditorPanel
from app.gui.template_set_editor import TemplateSetEditorPanel
from app.gui.printer_settings import PrinterSettingsPanel
from app.infrastructure.settings_store import SettingsStore
from app.models.settings_model import AppSettings


@pytest.fixture
def settings() -> AppSettings:
    return AppSettings()


@pytest.fixture
def mock_controller(settings: AppSettings) -> AppController:
    mock_engine = MagicMock()
    controller = AppController(settings, mock_engine)
    return controller


@pytest.fixture
def settings_store(tmp_path: Path) -> SettingsStore:
    return SettingsStore(path=tmp_path / "settings.json")


class TestMainWindow:
    """MainWindow のスモークテスト。"""

    def test_window_opens_and_closes(
        self,
        qtbot: QtBot,
        mock_controller: AppController,
        settings_store: SettingsStore,
        settings: AppSettings,
    ) -> None:
        """メインウィンドウが起動して閉じられることを確認。"""
        window = MainWindow(mock_controller, settings_store, settings)
        qtbot.addWidget(window)
        window.show()
        assert window.isVisible()
        window.close()

    def test_window_has_tabs(
        self,
        qtbot: QtBot,
        mock_controller: AppController,
        settings_store: SettingsStore,
        settings: AppSettings,
    ) -> None:
        """メインウィンドウにタブが存在することを確認。"""
        window = MainWindow(mock_controller, settings_store, settings)
        qtbot.addWidget(window)
        assert window._tabs.count() == 5

    def test_start_stop_buttons_initial_state(
        self,
        qtbot: QtBot,
        mock_controller: AppController,
        settings_store: SettingsStore,
        settings: AppSettings,
    ) -> None:
        """初期状態で開始ボタンが有効、停止ボタンが無効であることを確認。"""
        window = MainWindow(mock_controller, settings_store, settings)
        qtbot.addWidget(window)
        assert window._start_btn.isEnabled()
        assert not window._stop_btn.isEnabled()


class TestLogViewer:
    """LogViewer のスモークテスト。"""

    def test_append_and_clear(self, qtbot: QtBot) -> None:
        """ログの追加とクリアが動作することを確認。"""
        viewer = LogViewer()
        qtbot.addWidget(viewer)

        viewer.append_log("INFO", "テストメッセージ")
        assert "テストメッセージ" in viewer._text_edit.toPlainText()

        viewer.clear_log()
        assert viewer._text_edit.toPlainText() == ""


class TestFolderSettingsPanel:
    """FolderSettingsPanel のスモークテスト。"""

    def test_panel_creates(self, qtbot: QtBot, settings: AppSettings) -> None:
        """パネルが生成されることを確認。"""
        panel = FolderSettingsPanel(settings)
        qtbot.addWidget(panel)
        assert panel._input_row["label"].text() == "（未設定）"

    def test_panel_shows_existing_settings(self, qtbot: QtBot) -> None:
        """既存設定がラベルに反映されることを確認。"""
        from app.models.settings_model import FolderSettings

        s = AppSettings(
            folders=FolderSettings(
                input_root=Path("/test/input"),
                output_root=Path("/test/output"),
                failed_folder=Path("/test/failed"),
            )
        )
        panel = FolderSettingsPanel(s)
        qtbot.addWidget(panel)
        assert "/test/input" in panel._input_row["label"].text()
        assert "/test/output" in panel._output_row["label"].text()
        assert "/test/failed" in panel._failed_row["label"].text()


class TestTemplateEditorPanel:
    """TemplateEditorPanel のスモークテスト。"""

    def test_panel_creates(self, qtbot: QtBot, mock_controller: AppController) -> None:
        panel = TemplateEditorPanel(mock_controller)
        qtbot.addWidget(panel)
        assert panel._template_list is not None
        assert not panel._right_widget.isEnabled()


class TestTemplateSetEditorPanel:
    """TemplateSetEditorPanel のスモークテスト。"""

    def test_panel_creates(self, qtbot: QtBot, mock_controller: AppController) -> None:
        panel = TemplateSetEditorPanel(mock_controller)
        qtbot.addWidget(panel)
        assert panel._set_list is not None
        assert not panel._right_widget.isEnabled()


class TestPrinterSettingsPanel:
    """PrinterSettingsPanel のスモークテスト。"""

    def test_panel_creates(self, qtbot: QtBot, settings: AppSettings) -> None:
        panel = PrinterSettingsPanel(settings)
        qtbot.addWidget(panel)
        assert panel._printer_combo is not None
        assert panel._copies_spin.value() == 1
