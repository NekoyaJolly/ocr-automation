"""テンプレート適用およびデータ抽出を行うコアモジュール。"""

import logging
import re
from datetime import datetime
from typing import Any

from app.exceptions import TemplateError
from app.models.ocr_result_model import OCRResult
from app.models.template_model import FieldMapping, Template, TemplateSet

logger = logging.getLogger(__name__)


def get_intersection_area(
    box1: tuple[int, int, int, int], box2: tuple[int, int, int, int]
) -> int:
    """2つの境界ボックス（x, y, w, h）の重なり合う面積を計算する。"""
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2

    x_left = max(x1, x2)
    y_top = max(y1, y2)
    x_right = min(x1 + w1, x2 + w2)
    y_bottom = min(y1 + h1, y2 + h2)

    if x_right <= x_left or y_bottom <= y_top:
        return 0

    return (x_right - x_left) * (y_bottom - y_top)


class TemplateEngine:
    """OCR 結果に対してテンプレートの定義を適用し、フィールドごとの値を抽出するクラス。"""

    def apply_single(self, ocr_result: OCRResult, template: Template) -> dict[str, Any]:
        """単一のテンプレートを OCR 結果に適用し、抽出されたデータのディクショナリを返す。

        Args:
            ocr_result: OCR 処理結果
            template: 適用するテンプレート定義

        Returns:
            フィールド名をキー、抽出・変換された値をバリューとする辞書

        Raises:
            TemplateError: テンプレート適用中に致命的なエラーが発生した場合
        """
        logger.info(f"テンプレート適用を開始: {template.name}")
        extracted_data: dict[str, Any] = {}

        for field in template.fields:
            try:
                raw_value = self._extract_field_value(ocr_result, field)
                converted_value = self._convert_value(raw_value, field)
                extracted_data[field.output_label] = converted_value
                logger.debug(
                    f"フィールド抽出完了: {field.output_label} -> {converted_value} (元データ: '{raw_value}')"
                )
            except Exception as e:
                logger.exception(f"フィールド '{field.output_label}' の抽出に失敗しました")
                # フィールド単体のエラーはログに記録し、None として処理を継続（部分成功のため）
                extracted_data[field.output_label] = None

        return extracted_data

    def _extract_field_value(self, ocr_result: OCRResult, field: FieldMapping) -> str:
        """指定されたマッピング方法（位置またはキーワード）で値を抽出する。"""
        if field.extraction_type == "position":
            if not field.bbox:
                logger.warning(f"位置ベース抽出が指定されていますが bbox が未設定です: {field.output_label}")
                return ""
            return self._extract_by_position(ocr_result, field.bbox)
        else:
            return self._extract_by_keyword(ocr_result, field.source_key)

    def _extract_by_position(self, ocr_result: OCRResult, target_bbox: tuple[int, int, int, int]) -> str:
        """指定された矩形領域に重なる OCR ブロックからテキストを抽出する。"""
        best_block = None
        max_intersection = 0

        for block in ocr_result.blocks:
            intersection = get_intersection_area(block.bbox, target_bbox)
            if intersection > max_intersection:
                max_intersection = intersection
                best_block = block

        # 重なりが一定以上ある場合にそのテキストを返す
        if best_block and max_intersection > 0:
            # 簡易的に、重なり面積が最大だったブロックのテキストを採用
            return best_block.text

        return ""

    def _extract_by_keyword(self, ocr_result: OCRResult, source_key: str) -> str:
        """キーワード（または正規表現）を用いて、OCR結果のテキスト全体から値を抽出する。"""
        raw_text = ocr_result.raw_text

        # 1. まず正規表現としてのマッチを試みる (グループ指定がある場合のみ)
        try:
            if "(" in source_key and ")" in source_key:
                pattern = re.compile(source_key)
                match = pattern.search(raw_text)
                if match and match.groups():
                    # グループ指定がある場合は最初のグループを返す
                    return match.group(1).strip()
        except re.error:
            # 正規表現として無効な場合は、通常の文字列検索へフォールバック
            pass

        # 2. 通常の文字列前方一致・部分一致による抽出
        if source_key in raw_text:
            idx = raw_text.find(source_key)
            start = idx + len(source_key)
            suffix_text = raw_text[start:]
            # 最初の改行までのテキストを取得
            line = suffix_text.split("\n")[0]
            # コロン、スペース、イコールなどの区切り文字を除去
            line = re.sub(r"^[\s:：\-\=・]+", "", line)
            return line.strip()

        # 3. 各ブロックごとの部分一致検索（ブロック単位でキーと値がペアになっている場合）
        for block in ocr_result.blocks:
            if source_key in block.text:
                idx = block.text.find(source_key)
                val = block.text[idx + len(source_key) :]
                val = re.sub(r"^[\s:：\-\=・]+", "", val)
                if val.strip():
                    return val.strip()

        return ""

    def _convert_value(self, raw_value: str, field: FieldMapping) -> Any:
        """抽出した文字列を指定されたデータ型に変換し、フォーマットを適用する。"""
        val = raw_value.strip()
        if not val:
            return None

        if field.data_type in ("number", "currency"):
            # 末尾の飾りハイフンを除去
            val = re.sub(r"-$", "", val)
            # カンマ、円記号、通貨記号、スペースなどを除去
            cleaned = re.sub(r"[^\d\.\-]", "", val)
            if not cleaned:
                return None
            try:
                if "." in cleaned:
                    return float(cleaned)
                return int(cleaned)
            except ValueError:
                return val

        elif field.data_type == "date":
            # 日付文字列の正規化とパース
            cleaned = val.replace(" ", "")
            # 代表的なパターン: YYYY/MM/DD, YYYY-MM-DD, YYYY年MM月DD日
            date_patterns = [
                r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})",
                r"(\d{4})(\d{2})(\d{2})",  # YYYYMMDD
            ]
            for pat in date_patterns:
                match = re.search(pat, cleaned)
                if match:
                    try:
                        year = int(match.group(1))
                        month = int(match.group(2))
                        day = int(match.group(3))
                        dt = datetime(year, month, day)

                        if field.format_string:
                            return dt.strftime(field.format_string)
                        return dt.date()
                    except ValueError:
                        pass
            return val

        # デフォルトは文字列
        return val
