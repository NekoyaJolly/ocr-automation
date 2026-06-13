"""Phase 3 用の OCRWorker ユニットテスト。"""

import shutil
import time
from pathlib import Path
import pytest
import yaml

from app.controllers.ocr_worker import OCRWorker, load_template_set, load_template
from app.core.ocr_engine import OCREngine
from app.core.exporter import ExporterFactory
from app.models.ocr_result_model import OCRBlock, OCRResult
from app.models.settings_model import AppSettings, FolderSettings, RetrySettings
from app.models.template_model import Template, TemplateSet, TemplateSetEntry, FieldMapping


class MockOCREngine(OCREngine):
    """テスト用のモック OCR エンジン。"""
    def __init__(self, return_result: OCRResult | None = None) -> None:
        self.return_result = return_result
        self.called = False

    def process(self, image_path: Path) -> OCRResult:
        self.called = True
        if self.return_result:
            # 入力画像パスを設定し直して返す
            self.return_result.source_image = image_path
            return self.return_result
        return OCRResult(
            source_image=image_path,
            blocks=[OCRBlock(text="テスト請求書: INV-999", bbox=(10, 10, 100, 30))],
            raw_text="テスト請求書: INV-999",
        )


@pytest.fixture
def mock_template_files(tmp_path, monkeypatch):
    """テスト用のテンプレートYAMLファイルを一時ディレクトリに配置し、検索パスを置き換える。"""
    user_templates_dir = tmp_path / "user_templates"
    user_template_sets_dir = tmp_path / "user_template_sets"
    user_templates_dir.mkdir(parents=True)
    user_template_sets_dir.mkdir(parents=True)

    # テンプレート定義
    template_data = {
        "name": "テスト用テンプレート",
        "description": "テスト",
        "output_format": "txt",
        "output_filename_pattern": "{source_basename}_out.txt",
        "fields": [
            {
                "source_key": "テスト請求書",
                "output_label": "請求書番号",
                "target_position": "",
                "data_type": "string",
                "extraction_type": "keyword",
            }
        ]
    }
    
    # テンプレートセット定義
    template_set_data = {
        "name": "テスト用セット",
        "description": "テストセット",
        "entries": [
            {
                "template_name": "test_tmpl",
                "enabled": True,
                "output_subfolder": "sub_out",
                "auto_print": False,
                "printer_name": None,
            }
        ]
    }

    t_file = user_templates_dir / "test_tmpl.yaml"
    s_file = user_template_sets_dir / "test_set.yaml"

    with open(t_file, "w", encoding="utf-8") as f:
        yaml.dump(template_data, f)
        
    with open(s_file, "w", encoding="utf-8") as f:
        yaml.dump(template_set_data, f)

    # パス解決の関数を一時的に monkeypatch で差し替える
    monkeypatch.setattr("app.infrastructure.paths.get_user_templates_dir", lambda: user_templates_dir)
    monkeypatch.setattr("app.infrastructure.paths.get_user_template_sets_dir", lambda: user_template_sets_dir)

    return {
        "templates_dir": user_templates_dir,
        "template_sets_dir": user_template_sets_dir,
    }


def test_load_template_and_set(mock_template_files):
    tmpl = load_template("test_tmpl")
    assert tmpl is not None
    assert tmpl.name == "テスト用テンプレート"

    tset = load_template_set("test_set")
    assert tset is not None
    assert tset.entries[0].template_name == "test_tmpl"


def test_ocr_worker_process_job_success(tmp_path, mock_template_files):
    # ディレクトリ準備
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    failed_dir = tmp_path / "failed"

    # 監視サブフォルダの作成（"納品書" -> "test_set" を適用）
    sub_input_dir = input_dir / "納品書"
    sub_input_dir.mkdir(parents=True)
    image_path = sub_input_dir / "invoice_image.png"
    image_path.write_text("dummy image content")

    # 設定モデルの構築
    settings = AppSettings(
        folders=FolderSettings(
            input_root=input_dir,
            output_root=output_dir,
            failed_folder=failed_dir,
            subfolder_to_set={"納品書": "test_set"}
        ),
        retry=RetrySettings(max_retries=1, initial_backoff_seconds=0.1)
    )

    engine = MockOCREngine()
    worker = OCRWorker(engine, output_dir, failed_dir, settings)

    # 処理実行
    worker._process_job(image_path)

    # 検証：出力サブフォルダに出力ファイルが作成されていること
    expected_out = output_dir / "sub_out" / "invoice_image_out.txt"
    assert expected_out.exists()
    content = expected_out.read_text(encoding="utf-8")
    assert "請求書番号: INV-999" in content


def test_ocr_worker_process_job_retry_and_partial_failure(tmp_path, mock_template_files, monkeypatch):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    failed_dir = tmp_path / "failed"

    sub_input_dir = input_dir / "納品書"
    sub_input_dir.mkdir(parents=True)
    image_path = sub_input_dir / "invoice_image.png"
    image_path.write_text("dummy image content")

    # 2つのテンプレートを持つテンプレートセットに変更
    template_set_data = {
        "name": "テスト用セット",
        "entries": [
            {
                "template_name": "test_tmpl",  # 成功する
                "enabled": True,
                "output_subfolder": "success_out",
                "auto_print": False,
                "printer_name": None,
            },
            {
                "template_name": "fail_tmpl",  # 失敗する
                "enabled": True,
                "output_subfolder": "fail_out",
                "auto_print": False,
                "printer_name": None,
            }
        ]
    }
    
    # 失敗するテンプレートの定義
    fail_template_data = {
        "name": "失敗テンプレート",
        "output_format": "xlsx",  # openpyxl 処理などで失敗させやすい
        "output_filename_pattern": "{source_basename}_fail.xlsx",
        "fields": []
    }

    with open(mock_template_files["template_sets_dir"] / "test_set.yaml", "w", encoding="utf-8") as f:
        yaml.dump(template_set_data, f)
    with open(mock_template_files["templates_dir"] / "fail_tmpl.yaml", "w", encoding="utf-8") as f:
        yaml.dump(fail_template_data, f)

    # エクスポーターで意図的にエラーを起こすようにモックする
    class FailingExporter:
        def export(self, *args, **kwargs):
            raise RuntimeError("書き込みエラー")

    # docx/xlsx などを利用できない、またはエラーを起こす
    original_create = ExporterFactory.create
    monkeypatch.setattr("app.core.exporter.ExporterFactory.create", 
                        lambda fmt: FailingExporter() if fmt == "xlsx" else original_create(fmt))

    settings = AppSettings(
        folders=FolderSettings(
            input_root=input_dir,
            output_root=output_dir,
            failed_folder=failed_dir,
            subfolder_to_set={"納品書": "test_set"}
        ),
        retry=RetrySettings(max_retries=1, initial_backoff_seconds=0.01)  # テスト高速化
    )

    engine = MockOCREngine()
    worker = OCRWorker(engine, output_dir, failed_dir, settings)

    # 処理実行
    worker._process_job(image_path)

    # 検証: 部分成功
    # 1. 成功したテンプレートファイルは出力されている
    assert (output_dir / "success_out" / "invoice_image_out.txt").exists()
    # 2. 失敗したテンプレートファイルは出力されていない
    assert not (output_dir / "fail_out" / "invoice_image_fail.xlsx").exists()
    # 3. 元画像が失敗フォルダに退避されている
    assert (failed_dir / "invoice_image.png").exists()
    # 4. 部分失敗ログが生成されている
    partial_logs = list(failed_dir.glob("*.partial_error.log"))
    assert len(partial_logs) == 1
    log_content = partial_logs[0].read_text(encoding="utf-8")
    assert "失敗テンプレート" in log_content
    assert "書き込みエラー" in log_content
