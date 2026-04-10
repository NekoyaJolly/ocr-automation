"""アプリケーション設定のデータモデル。"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class FolderSettings(BaseModel):
    """フォルダ設定。"""

    input_root: Path = Path.home() / "OCR" / "入力"
    output_root: Path = Path.home() / "OCR" / "出力"
    failed_folder: Path = Path.home() / "OCR" / "失敗"
    processed_folder: Path = Path.home() / "OCR" / "処理済み"
    subfolder_to_set: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "入力ルート直下のサブフォルダ名 → テンプレートセット YAML のファイル名(stem)。"
            "例: 納品書 → default_set (= template_sets/default_set.yaml)"
        ),
    )


class PrinterSettings(BaseModel):
    """プリンタ設定。"""

    default_printer: str | None = None
    copies: int = 1
    auto_print_enabled: bool = False


class RetrySettings(BaseModel):
    """リトライ設定。"""

    max_retries: int = 2
    initial_backoff_seconds: float = 1.0
    backoff_multiplier: float = 3.0


class BackendSettings(BaseModel):
    """バックエンド接続設定。"""

    base_url: str = "https://ocr-backend.example.run.app"
    timeout_seconds: float = 30.0


class AppSettings(BaseModel):
    """アプリケーション全体の設定。"""

    folders: FolderSettings = Field(default_factory=FolderSettings)
    printer: PrinterSettings = Field(default_factory=PrinterSettings)
    retry: RetrySettings = Field(default_factory=RetrySettings)
    backend: BackendSettings = Field(default_factory=BackendSettings)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
