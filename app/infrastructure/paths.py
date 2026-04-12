"""OS 別のデータディレクトリ管理。"""

import platform
from pathlib import Path


def get_app_data_dir() -> Path:
    """アプリケーションデータの保存先ディレクトリを返す。

    Returns:
        Windows: %APPDATA%/OCRAutomation/
        macOS: ~/Library/Application Support/OCRAutomation/
        Linux: ~/.local/share/OCRAutomation/
    """
    system = platform.system()
    if system == "Windows":
        base = Path.home() / "AppData" / "Roaming"
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"

    app_dir = base / "OCRAutomation"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_settings_path() -> Path:
    """settings.json のパスを返す。"""
    return get_app_data_dir() / "settings.json"


def get_log_dir() -> Path:
    """ログディレクトリのパスを返す。"""
    log_dir = get_app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_user_templates_dir() -> Path:
    """ユーザー作成テンプレートの保存先を返す。"""
    tmpl_dir = get_app_data_dir() / "templates"
    tmpl_dir.mkdir(parents=True, exist_ok=True)
    return tmpl_dir


def get_user_template_sets_dir() -> Path:
    """ユーザー作成テンプレートセットの保存先を返す。"""
    sets_dir = get_app_data_dir() / "template_sets"
    sets_dir.mkdir(parents=True, exist_ok=True)
    return sets_dir


def get_review_jobs_dir() -> Path:
    """レビュー待ちジョブ JSON の保存先を返す。"""
    review_dir = get_app_data_dir() / "review_jobs"
    review_dir.mkdir(parents=True, exist_ok=True)
    return review_dir


def get_review_history_dir() -> Path:
    """承認・却下レビュー履歴 JSON のルートディレクトリを返す。

    実データは YYYY-MM サブフォルダ配下に配置する。
    """
    hist_dir = get_app_data_dir() / "review_history"
    hist_dir.mkdir(parents=True, exist_ok=True)
    return hist_dir
