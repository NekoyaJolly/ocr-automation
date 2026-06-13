"""アプリケーション設定のデータモデル定義。"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class FolderSettings(BaseModel):
    """フォルダ関連の設定。"""

    input_root: Path | None = Field(default=None, description="入力ルートフォルダ")
    output_root: Path | None = Field(default=None, description="出力ルートフォルダ")
    failed_folder: Path | None = Field(default=None, description="失敗フォルダ")
    subfolder_to_set: dict[str, str] = Field(
        default_factory=dict,
        description="サブフォルダ名 → テンプレートセット名のマッピング",
    )


class PrinterSettings(BaseModel):
    """プリンタ関連の設定。"""

    default_printer: str | None = None
    copies: int = Field(default=1, ge=1)


class RetrySettings(BaseModel):
    """リトライ関連の設定。"""

    max_retries: int = Field(default=2, ge=0)
    initial_backoff_seconds: float = Field(default=1.0, gt=0)
    backoff_multiplier: float = Field(default=3.0, gt=1.0)


class AppSettings(BaseModel):
    """アプリケーション全体の設定。"""

    folders: FolderSettings = Field(default_factory=FolderSettings)
    printer: PrinterSettings = Field(default_factory=PrinterSettings)
    retry: RetrySettings = Field(default_factory=RetrySettings)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
