"""出力フォーマット — 抽象 Exporter + 各フォーマット実装。"""

import json
from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, ClassVar

from app.exceptions import ExportError
from app.infrastructure.logger import get_logger
from app.models.template_model import Template

logger = get_logger(__name__)

# Windows のメモ帳・Excel で UTF-8 を誤検出しないよう TXT は BOM 付きで書き出す。
TXT_ENCODING = "utf-8-sig"

# 空ブックへ直接書き込む xlsx で日本語表示を安定させる。ベーステンプレ読込時は既存スタイルを尊重。
_JP_CELL_FONT: Any = None


def _jp_cell_font() -> Any:
    global _JP_CELL_FONT
    if _JP_CELL_FONT is None:
        from openpyxl.styles import Font

        _JP_CELL_FONT = Font(name="Meiryo", size=11)
    return _JP_CELL_FONT


def _normalize_excel_scalar(value: Any) -> Any:
    """openpyxl へ渡すスカラーを正規化する。文字列・数値・日付はそのまま保持。"""
    if value is None:
        return None
    if isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime | date):
        return value
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


class Exporter(ABC):
    """出力エクスポーターの抽象インターフェース。"""

    @abstractmethod
    def export(self, data: dict[str, Any], template: Template, output_path: Path) -> None:
        """データをファイルに出力する。

        Args:
            data: field_placements で整形済みのデータ。
            template: テンプレート定義。
            output_path: 出力先パス。
        """
        ...


class TxtExporter(Exporter):
    """シンプルな key: value テキスト出力。"""

    def export(self, data: dict[str, Any], template: Template, output_path: Path) -> None:
        raw = data.get("__raw__", data)
        lines: list[str] = []
        for key, value in raw.items():
            if key == "__raw__":
                continue
            if isinstance(value, list):
                lines.append(f"{key}:")
                for i, item in enumerate(value):
                    lines.append(f"  [{i + 1}] {item}")
            else:
                lines.append(f"{key}: {value}")
        output_path.write_text("\n".join(lines), encoding=TXT_ENCODING)
        logger.info("TXT 出力完了: %s", output_path)


class DocxExporter(Exporter):
    """python-docx でテンプレート docx にプレースホルダを置換して出力。"""

    def export(self, data: dict[str, Any], template: Template, output_path: Path) -> None:
        from docx import Document

        raw = data.get("__raw__", {})

        base_path = (
            Path(template.base_template_file) if template.base_template_file else None
        )
        doc = (
            Document(str(base_path))
            if base_path and base_path.exists()
            else Document()
        )

        for paragraph in doc.paragraphs:
            for fp in template.field_placements:
                placeholder = fp.target  # e.g. "{{invoice_no}}"
                value = raw.get(fp.source_key)
                if placeholder in paragraph.text and value is not None:
                    paragraph.text = paragraph.text.replace(placeholder, str(value))

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for fp in template.field_placements:
                        placeholder = fp.target
                        value = raw.get(fp.source_key)
                        if placeholder in cell.text and value is not None:
                            cell.text = cell.text.replace(placeholder, str(value))

        doc.save(str(output_path))
        logger.info("DOCX 出力完了: %s", output_path)


class XlsxExporter(Exporter):
    """openpyxl でセル単位に値を書き込む。"""

    def export(self, data: dict[str, Any], template: Template, output_path: Path) -> None:
        from openpyxl import Workbook, load_workbook

        raw = data.get("__raw__", {})

        base_path = (
            Path(template.base_template_file) if template.base_template_file else None
        )
        from_workbook = bool(base_path and base_path.exists())
        wb = load_workbook(str(base_path)) if from_workbook else Workbook()
        apply_jp_font = not from_workbook

        ws = wb.active
        if ws is None:
            ws = wb.create_sheet()

        for fp in template.field_placements:
            value = raw.get(fp.source_key)
            if value is None:
                continue

            if fp.expand == "rows" and isinstance(value, list):
                self._expand_rows(ws, fp.target, value, apply_jp_font)
            elif fp.expand == "cols" and isinstance(value, list):
                self._expand_cols(ws, fp.target, value, apply_jp_font)
            else:
                cell = ws[fp.target]
                cell.value = _normalize_excel_scalar(value)
                if apply_jp_font:
                    cell.font = _jp_cell_font()

        wb.save(str(output_path))
        logger.info("XLSX 出力完了: %s", output_path)

    @staticmethod
    def _expand_rows(
        ws: Any, start_cell: str, items: list[Any], apply_jp_font: bool
    ) -> None:
        """配列を縦方向に展開する。"""
        from openpyxl.utils.cell import column_index_from_string, coordinate_from_string

        col_letter, row_num = coordinate_from_string(start_cell)
        col_idx = column_index_from_string(col_letter)
        font = _jp_cell_font() if apply_jp_font else None

        for i, item in enumerate(items):
            if isinstance(item, dict):
                for j, (_, val) in enumerate(item.items()):
                    c = ws.cell(
                        row=row_num + i,
                        column=col_idx + j,
                        value=_normalize_excel_scalar(val),
                    )
                    if font is not None:
                        c.font = font
            else:
                c = ws.cell(
                    row=row_num + i,
                    column=col_idx,
                    value=_normalize_excel_scalar(item),
                )
                if font is not None:
                    c.font = font

    @staticmethod
    def _expand_cols(
        ws: Any, start_cell: str, items: list[Any], apply_jp_font: bool
    ) -> None:
        """配列を横方向に展開する。"""
        from openpyxl.utils.cell import column_index_from_string, coordinate_from_string

        col_letter, row_num = coordinate_from_string(start_cell)
        col_idx = column_index_from_string(col_letter)
        font = _jp_cell_font() if apply_jp_font else None

        for i, item in enumerate(items):
            if isinstance(item, dict):
                for j, (_, val) in enumerate(item.items()):
                    c = ws.cell(
                        row=row_num + j,
                        column=col_idx + i,
                        value=_normalize_excel_scalar(val),
                    )
                    if font is not None:
                        c.font = font
            else:
                c = ws.cell(
                    row=row_num,
                    column=col_idx + i,
                    value=_normalize_excel_scalar(item),
                )
                if font is not None:
                    c.font = font


class PdfExporter(Exporter):
    """pypdf でテンプレート PDF のフォームフィールドに値を書き込む。"""

    def export(self, data: dict[str, Any], template: Template, output_path: Path) -> None:
        raw = data.get("__raw__", {})

        if not template.base_template_file:
            self._create_simple_pdf(raw, template, output_path)
            return

        base_path = Path(template.base_template_file)
        if not base_path.exists():
            self._create_simple_pdf(raw, template, output_path)
            return

        from pypdf import PdfReader, PdfWriter

        reader = PdfReader(str(base_path))
        writer = PdfWriter()
        writer.append_pages_from_reader(reader)

        field_values: dict[str, str] = {}
        for fp in template.field_placements:
            value = raw.get(fp.source_key)
            if value is not None:
                field_values[fp.target] = str(value)

        if field_values:
            for page_num in range(len(writer.pages)):
                writer.update_page_form_field_values(writer.pages[page_num], field_values)

        with open(output_path, "wb") as f:
            writer.write(f)

        logger.info("PDF 出力完了: %s", output_path)

    @staticmethod
    def _create_simple_pdf(
        raw: dict[str, Any], template: Template, output_path: Path
    ) -> None:
        """ベーステンプレートなしの場合、シンプルなテキスト PDF を生成。"""
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(str(output_path), pagesize=A4)
        _width, height = A4
        y = height - 50

        try:
            pdfmetrics.registerFont(TTFont("IPAGothic", "ipag.ttf"))
            c.setFont("IPAGothic", 12)
        except Exception:
            c.setFont("Helvetica", 12)

        for fp in template.field_placements:
            value = raw.get(fp.source_key)
            if value is not None:
                c.drawString(50, y, f"{fp.source_key}: {value}")
                y -= 20
                if y < 50:
                    c.showPage()
                    y = height - 50

        c.save()
        logger.info("PDF (テキスト) 出力完了: %s", output_path)


class ExporterFactory:
    """出力フォーマットに応じた Exporter を生成する。"""

    _exporters: ClassVar[dict[str, type[Exporter]]] = {
        "txt": TxtExporter,
        "docx": DocxExporter,
        "xlsx": XlsxExporter,
        "pdf": PdfExporter,
    }

    @classmethod
    def create(cls, format_name: str) -> Exporter:
        """フォーマット名から Exporter インスタンスを生成する。"""
        exporter_cls = cls._exporters.get(format_name)
        if exporter_cls is None:
            raise ExportError(f"未対応の出力フォーマット: {format_name}")
        return exporter_cls()

    @classmethod
    def supported_formats(cls) -> list[str]:
        """サポートされているフォーマット一覧を返す。"""
        return list(cls._exporters.keys())
