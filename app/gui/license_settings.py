"""ライセンス設定画面。"""

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.license_manager import LicenseManager
from app.models.license_model import LicenseInfo


class LicenseSettingsWidget(QWidget):
    """ライセンスキーの入力・検証・情報表示を行う画面。"""

    license_verified = Signal(object)  # LicenseInfo

    def __init__(
        self, license_manager: LicenseManager, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._manager = license_manager
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        key_group = QGroupBox("ライセンスキー")
        key_layout = QVBoxLayout(key_group)

        input_row = QHBoxLayout()
        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("OCRA-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX")
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        input_row.addWidget(self._key_input, stretch=1)

        self._toggle_btn = QPushButton("表示")
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.toggled.connect(self._toggle_visibility)
        input_row.addWidget(self._toggle_btn)
        key_layout.addLayout(input_row)

        btn_row = QHBoxLayout()
        self._verify_btn = QPushButton("検証して保存")
        self._verify_btn.clicked.connect(self._verify_key)
        btn_row.addWidget(self._verify_btn)

        self._test_btn = QPushButton("接続テスト")
        self._test_btn.clicked.connect(self._test_connection)
        btn_row.addWidget(self._test_btn)
        btn_row.addStretch()
        key_layout.addLayout(btn_row)
        layout.addWidget(key_group)

        info_group = QGroupBox("ライセンス情報")
        info_layout = QFormLayout(info_group)

        self._company_label = QLabel("—")
        self._status_label = QLabel("—")
        self._expires_label = QLabel("—")
        self._usage_label = QLabel("—")

        info_layout.addRow("契約会社:", self._company_label)
        info_layout.addRow("ステータス:", self._status_label)
        info_layout.addRow("有効期限:", self._expires_label)
        info_layout.addRow("当月利用:", self._usage_label)
        layout.addWidget(info_group)

        layout.addStretch()

    def refresh_info(self) -> None:
        """キャッシュされた情報で表示を更新する。"""
        try:
            if not self._manager.has_key():
                self._status_label.setText("未設定")
                return
            info = self._manager.get_info()
            self._update_display(info)
        except Exception:
            self._status_label.setText("取得失敗")

    def _update_display(self, info: LicenseInfo) -> None:
        self._company_label.setText(info.company_name or "—")
        self._status_label.setText("有効" if info.is_valid else "無効")
        if info.expires_at:
            self._expires_label.setText(info.expires_at.strftime("%Y/%m/%d"))
        else:
            self._expires_label.setText("—")
        self._usage_label.setText(f"{info.used_this_month} / {info.monthly_quota}")

    @Slot()
    def _verify_key(self) -> None:
        key = self._key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "入力エラー", "ライセンスキーを入力してください")
            return

        try:
            info = self._manager.set_key(key)
            self._update_display(info)
            self.license_verified.emit(info)
            QMessageBox.information(self, "成功", "ライセンスキーの検証に成功しました")
        except Exception as e:
            QMessageBox.critical(self, "検証失敗", f"ライセンスキーの検証に失敗しました:\n{e}")

    @Slot()
    def _test_connection(self) -> None:
        try:
            info = self._manager.get_info(force_refresh=True)
            self._update_display(info)
            if info.is_valid:
                QMessageBox.information(self, "接続テスト", "バックエンドへの接続に成功しました")
            else:
                QMessageBox.warning(self, "接続テスト", "接続できましたがライセンスが無効です")
        except Exception as e:
            QMessageBox.critical(self, "接続テスト", f"バックエンドへの接続に失敗しました:\n{e}")

    @Slot(bool)
    def _toggle_visibility(self, checked: bool) -> None:
        if checked:
            self._key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._toggle_btn.setText("隠す")
        else:
            self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._toggle_btn.setText("表示")
