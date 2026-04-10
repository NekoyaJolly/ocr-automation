"""テンプレートエンジン — テンプレート読み込み・適用ロジック。"""

from pathlib import Path
from typing import Any

import yaml

from app.core.exporter import ExporterFactory
from app.core.ocr_engine import OCREngine
from app.exceptions import TemplateConfigError
from app.infrastructure.logger import get_logger
from app.models.template_model import (
    Template,
    TemplateApplicationResult,
    TemplateSet,
    TemplateSetEntry,
)

logger = get_logger(__name__)


def format_available_keys_hint(keys: list[str], *, max_show: int = 30) -> str:
    """エラーメッセージ用に利用可能キー一覧を整形する。"""
    sorted_keys = sorted(keys)
    if len(sorted_keys) <= max_show:
        return ", ".join(sorted_keys)
    head = ", ".join(sorted_keys[:max_show])
    return f"{head}, … (他 {len(sorted_keys) - max_show} 件)"


def load_template(path: Path) -> Template:
    """YAML ファイルからテンプレートを読み込む。"""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return Template.model_validate(raw)
    except Exception as e:
        raise TemplateConfigError(f"テンプレートの読み込みに失敗: {path} — {e}") from e


def load_template_set(path: Path) -> TemplateSet:
    """YAML ファイルからテンプレートセットを読み込む。"""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return TemplateSet.model_validate(raw)
    except Exception as e:
        raise TemplateConfigError(f"テンプレートセットの読み込みに失敗: {path} — {e}") from e


def load_all_templates(directories: list[Path]) -> dict[str, Template]:
    """複数ディレクトリからテンプレートを一括読み込みする。

    辞書のキーは各 YAML ファイルの名前 (拡張子なしの stem)。
    ``name`` フィールドは GUI 表示用として YAML 内に残す。
    """
    templates: dict[str, Template] = {}
    for dir_path in directories:
        if not dir_path.exists():
            continue
        for yaml_file in sorted(dir_path.glob("*.yaml")):
            try:
                tmpl = load_template(yaml_file)
                stem = yaml_file.stem
                if stem in templates:
                    logger.info(
                        "テンプレートキー '%s' を上書き: %s (既存を置き換え)",
                        stem,
                        yaml_file,
                    )
                templates[stem] = tmpl
            except TemplateConfigError:
                logger.exception("テンプレート読み込みスキップ: %s", yaml_file)
    return templates


def load_all_template_sets(directories: list[Path]) -> dict[str, TemplateSet]:
    """複数ディレクトリからテンプレートセットを一括読み込みする。

    辞書のキーは各 YAML ファイルの名前 (拡張子なしの stem)。
    ``name`` フィールドは GUI 表示用として YAML 内に残す。
    """
    sets: dict[str, TemplateSet] = {}
    for dir_path in directories:
        if not dir_path.exists():
            continue
        for yaml_file in sorted(dir_path.glob("*.yaml")):
            try:
                ts = load_template_set(yaml_file)
                stem = yaml_file.stem
                if stem in sets:
                    logger.info(
                        "テンプレートセットキー '%s' を上書き: %s (既存を置き換え)",
                        stem,
                        yaml_file,
                    )
                sets[stem] = ts
            except TemplateConfigError:
                logger.exception("テンプレートセット読み込みスキップ: %s", yaml_file)
    return sets


class TemplateEngine:
    """テンプレート適用エンジン。"""

    def apply_set(
        self,
        ocr_engine: OCREngine,
        image_path: Path,
        template_set: TemplateSet,
        templates_by_name: dict[str, Template],
        output_root: Path,
        license_key: str,
    ) -> list[TemplateApplicationResult]:
        """セット内の有効な各テンプレートを適用し、結果リストを返す。

        部分成功を許容: 一部テンプレートが失敗しても他は続行する。
        """
        results: list[TemplateApplicationResult] = []
        available = format_available_keys_hint(list(templates_by_name.keys()))

        for entry in template_set.entries:
            if not entry.enabled:
                continue

            template = templates_by_name.get(entry.template_name)
            if template is None:
                results.append(
                    TemplateApplicationResult(
                        template_name=entry.template_name,
                        status="failed",
                        error_message=(
                            f"テンプレートが見つかりません: キー {entry.template_name!r}。"
                            f" 利用可能なテンプレートキー: [{available}]"
                        ),
                    )
                )
                continue

            result = self._apply_single_entry(
                ocr_engine=ocr_engine,
                image_path=image_path,
                entry=entry,
                template=template,
                output_root=output_root,
                license_key=license_key,
            )
            results.append(result)

        return results

    def _apply_single_entry(
        self,
        ocr_engine: OCREngine,
        image_path: Path,
        entry: TemplateSetEntry,
        template: Template,
        output_root: Path,
        license_key: str,
    ) -> TemplateApplicationResult:
        """単一テンプレートエントリを適用する。"""
        entry_key = entry.template_name
        try:
            extracted = self.apply_single(ocr_engine, image_path, template, license_key)

            output_dir = output_root / entry.output_subfolder
            output_dir.mkdir(parents=True, exist_ok=True)

            filename = self._format_filename(template.output_filename_pattern, extracted)
            output_path = output_dir / filename

            exporter = ExporterFactory.create(template.output_format)
            exporter.export(data=extracted, template=template, output_path=output_path)

            logger.info("テンプレート適用成功: %s (%s) → %s", entry_key, template.name, output_path)
            return TemplateApplicationResult(
                template_name=entry_key,
                status="success",
                output_file=output_path,
            )
        except Exception as e:
            logger.exception("テンプレート適用失敗: %s (%s)", entry_key, template.name)
            return TemplateApplicationResult(
                template_name=entry_key,
                status="failed",
                error_message=str(e),
            )

    def apply_single(
        self,
        ocr_engine: OCREngine,
        image_path: Path,
        template: Template,
        license_key: str,
    ) -> dict[str, Any]:
        """単一テンプレート適用 (OCR + field_placements によるデータ整形)。"""
        result = ocr_engine.process(
            image_path=image_path,
            extraction_prompt=template.extraction_prompt,
            response_schema=template.response_schema,
            license_key=license_key,
        )
        return self._map_fields(result.extracted_data, template)

    @staticmethod
    def _map_fields(extracted_data: dict[str, Any], template: Template) -> dict[str, Any]:
        """field_placements に従ってデータを整形する。"""
        mapped: dict[str, Any] = {}
        for fp in template.field_placements:
            value = extracted_data.get(fp.source_key)
            mapped[fp.target] = value
        mapped["__raw__"] = extracted_data
        return mapped

    @staticmethod
    def _format_filename(pattern: str, data: dict[str, Any]) -> str:
        """ファイル名パターンにデータを埋め込む。"""
        raw = data.get("__raw__", {})
        try:
            return pattern.format(**raw)
        except KeyError:
            safe_name = pattern
            for key, val in raw.items():
                safe_name = safe_name.replace(f"{{{key}}}", str(val) if val else "")
            return safe_name
