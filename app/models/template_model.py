"""テンプレートおよびテンプレートセットのデータモデル定義。"""

from typing import Literal

from pydantic import BaseModel, Field


class FieldMapping(BaseModel):
    """OCR 結果からターゲットドキュメントへの 1 項目のマッピング定義。"""

    source_key: str = Field(description="OCR 出力から値を特定するためのキー（項目名やキーワード）")
    output_label: str = Field(description="出力フォーマット上でのラベル名")
    target_position: str = Field(description="出力先での位置（Excel のセル番地 'B2' や Word のプレースホルダー '{{company_name}}' など）")
    data_type: Literal["string", "number", "date", "currency"] = Field(default="string", description="データの種類。パースやフォーマットに影響する")
    format_string: str | None = Field(default=None, description="出力フォーマット指定（例: 'YYYY/MM/DD', '¥#,##0'）")
    extraction_type: Literal["position", "keyword"] = Field(default="keyword", description="値の抽出方法。位置ベースかキーワードベースか")
    bbox: tuple[int, int, int, int] | None = Field(default=None, description="位置ベース抽出時の画像上での座標範囲 (x, y, width, height)")


class Template(BaseModel):
    """単一の出力ドキュメントの生成ルールを定義するテンプレートモデル。"""

    name: str = Field(description="テンプレートの一意な名称")
    description: str = Field(default="", description="テンプレートの説明")
    output_format: Literal["txt", "docx", "xlsx", "pdf"] = Field(description="出力ファイルの形式")
    output_filename_pattern: str = Field(description="出力ファイル名の命名パターン（例: '{date}_{source_basename}_invoice.xlsx'）")
    template_file: str | None = Field(default=None, description="ベースとなる Word/Excel のテンプレートファイル名。resources/templates/ から検索")
    fields: list[FieldMapping] = Field(default_factory=list, description="マッピングするフィールド of リスト")


class TemplateSetEntry(BaseModel):
    """テンプレートセット内で有効化されるテンプレートの設定情報。"""

    template_name: str = Field(description="参照する Template の名前")
    enabled: bool = Field(default=True, description="このテンプレートを適用するかどうか")
    output_subfolder: str = Field(default="", description="出力ルートフォルダ配下の保存先サブフォルダ名")
    auto_print: bool = Field(default=False, description="出力時に自動印刷を行うかどうか")
    printer_name: str | None = Field(default=None, description="使用するプリンタ名。None の場合はデフォルトプリンタを使用")


class TemplateSet(BaseModel):
    """1つの OCR 結果に対して適用する、複数のテンプレートをまとめたセット定義。"""

    name: str = Field(description="テンプレートセットの一意な名称")
    description: str = Field(default="", description="セットの説明")
    entries: list[TemplateSetEntry] = Field(default_factory=list, description="セットに含まれるテンプレートエントリのリスト")
