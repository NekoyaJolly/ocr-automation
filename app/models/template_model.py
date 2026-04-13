"""テンプレート関連のデータモデル。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class FieldPlacement(BaseModel):
    """抽出されたフィールドを出力フォーマットのどこに配置するか。"""

    source_key: str
    target: str  # xlsx: "B2", docx: "{{invoice_no}}", pdf: form field name
    display_name: str | None = None
    format_string: str | None = None
    expand: Literal["none", "rows", "cols"] = "none"
    required_for_review: bool = False


class Template(BaseModel):
    """単一テンプレート定義。"""

    name: str
    description: str = ""
    output_format: Literal["txt", "docx", "xlsx", "pdf"]
    output_filename_pattern: str  # 例: "{invoice_no}_{date}.xlsx"
    base_template_file: str | None = None

    industry_preset: str | None = None
    industry_context: str = ""
    custom_extraction_instructions: str = ""
    """ユーザー追加指示 (新形式 YAML)。extraction_prompt より優先。"""

    extraction_prompt: str = ""
    """後方互換・GUI 用。未使用時は空。custom と同期する。"""

    response_schema: dict[str, Any]
    field_placements: list[FieldPlacement] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_extraction_prompt(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        ep = out.get("extraction_prompt")
        cu = out.get("custom_extraction_instructions") or ""
        if ep and str(ep).strip() and not str(cu).strip():
            out["custom_extraction_instructions"] = str(ep).strip()
        return out

    @model_validator(mode="after")
    def _sync_prompt_strings(self) -> Template:
        """GUI が参照する extraction_prompt と custom を双方向で埋める。"""
        c = self.custom_extraction_instructions.strip()
        e = self.extraction_prompt.strip()
        if c and not e:
            object.__setattr__(self, "extraction_prompt", c)
        elif e and not c:
            object.__setattr__(self, "custom_extraction_instructions", e)
        return self


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
