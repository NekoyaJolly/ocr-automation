"""テンプレート関連のデータモデル。"""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class FieldPlacement(BaseModel):
    """抽出されたフィールドを出力フォーマットのどこに配置するか。"""

    source_key: str
    target: str  # xlsx: "B2", docx: "{{invoice_no}}", pdf: form field name
    format_string: str | None = None
    expand: Literal["none", "rows", "cols"] = "none"


class Template(BaseModel):
    """単一テンプレート定義。"""

    name: str
    description: str = ""
    output_format: Literal["txt", "docx", "xlsx", "pdf"]
    output_filename_pattern: str  # 例: "{invoice_no}_{date}.xlsx"
    base_template_file: str | None = None

    extraction_prompt: str
    response_schema: dict[str, Any]
    field_placements: list[FieldPlacement] = Field(default_factory=list)


class TemplateSetEntry(BaseModel):
    """テンプレートセット内の 1 テンプレートエントリ。"""

    template_name: str
    enabled: bool = True
    output_subfolder: str
    auto_print: bool = False
    printer_name: str | None = None


class TemplateSet(BaseModel):
    """テンプレートセット定義。"""

    name: str
    description: str = ""
    entries: list[TemplateSetEntry] = Field(default_factory=list)


class TemplateApplicationResult(BaseModel):
    """テンプレート適用の結果。"""

    template_name: str
    status: Literal["success", "failed"]
    output_file: Path | None = None
    error_message: str | None = None
    retry_count: int = 0
