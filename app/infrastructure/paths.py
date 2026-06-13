"""OS 別のアプリケーションデータパス解決モジュール。"""

import sys
from pathlib import Path


APP_NAME = "OCRAutomation"


def get_app_data_dir() -> Path:
    """OS に応じたアプリケーションデータディレクトリを返す。

    Returns:
        アプリケーション設定・ログ等を格納するディレクトリパス

    Raises:
        NotImplementedError: サポート外の OS の場合
    """
    match sys.platform:
        case "win32":
            import os

            appdata = os.environ.get("APPDATA")
            if appdata:
                base = Path(appdata)
            else:
                base = Path.home() / "AppData" / "Roaming"
            return base / APP_NAME
        case "darwin":
            return Path.home() / "Library" / "Application Support" / APP_NAME
        case _:
            return Path.home() / f".{APP_NAME.lower()}"


def get_settings_path() -> Path:
    """設定ファイル (settings.json) のパスを返す。"""
    return get_app_data_dir() / "settings.json"


def get_log_dir() -> Path:
    """ログファイルディレクトリのパスを返す。"""
    return get_app_data_dir() / "logs"


def get_user_templates_dir() -> Path:
    """ユーザー作成テンプレートディレクトリのパスを返す。"""
    return get_app_data_dir() / "templates"


def get_user_template_sets_dir() -> Path:
    """ユーザー作成テンプレートセットディレクトリのパスを返す。"""
    return get_app_data_dir() / "template_sets"


def ensure_app_dirs() -> None:
    """アプリケーションに必要な全ディレクトリを作成する。"""
    for dir_path in [
        get_app_data_dir(),
        get_log_dir(),
        get_user_templates_dir(),
        get_user_template_sets_dir(),
    ]:
        dir_path.mkdir(parents=True, exist_ok=True)
