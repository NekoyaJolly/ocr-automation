"""データモデルのユニットテスト。"""

from pathlib import Path

from app.models.job_model import Job, JobStatus
from app.models.license_model import LicenseInfo
from app.models.ocr_result_model import OCRResult
from app.models.settings_model import AppSettings, FolderSettings
from app.models.template_model import (
    FieldPlacement,
    Template,
    TemplateApplicationResult,
    TemplateSet,
    TemplateSetEntry,
)


class TestAppSettings:
    def test_default_settings(self):
        settings = AppSettings()
        assert settings.log_level == "INFO"
        assert settings.retry.max_retries == 2
        assert settings.backend.timeout_seconds == 30.0

    def test_folder_settings_defaults(self):
        fs = FolderSettings()
        assert "入力" in str(fs.input_root)
        assert "出力" in str(fs.output_root)

    def test_roundtrip_json(self):
        settings = AppSettings()
        data = settings.model_dump(mode="json")
        restored = AppSettings.model_validate(data)
        assert restored.log_level == settings.log_level


class TestOCRResult:
    def test_basic(self):
        result = OCRResult(
            source_image=Path("/tmp/test.jpg"),
            extracted_data={"invoice_no": "INV-001"},
        )
        assert result.extracted_data["invoice_no"] == "INV-001"
        assert result.processing_time_ms == 0


class TestTemplate:
    def test_template_creation(self):
        t = Template(
            name="テスト",
            output_format="txt",
            output_filename_pattern="{invoice_no}.txt",
            extraction_prompt="テスト用プロンプト",
            response_schema={"type": "object"},
            field_placements=[
                FieldPlacement(source_key="invoice_no", target="B2", display_name="番号"),
            ],
        )
        assert t.name == "テスト"
        assert len(t.field_placements) == 1

    def test_template_set(self):
        ts = TemplateSet(
            name="テストセット",
            entries=[
                TemplateSetEntry(
                    template_name="テスト",
                    output_subfolder="output",
                ),
            ],
        )
        assert len(ts.entries) == 1
        assert ts.entries[0].auto_print is False

    def test_application_result_success(self):
        r = TemplateApplicationResult(
            template_name="テスト",
            status="success",
            output_file=Path("/tmp/output.txt"),
        )
        assert r.status == "success"

    def test_application_result_failed(self):
        r = TemplateApplicationResult(
            template_name="テスト",
            status="failed",
            error_message="テストエラー",
            retry_count=2,
        )
        assert r.retry_count == 2


class TestJob:
    def test_job_default_status(self):
        job = Job(
            job_id="test-001",
            source_file=Path("/tmp/test.jpg"),
            template_set_name="test_set",
        )
        assert job.status == JobStatus.PENDING
        assert job.completed_at is None


class TestLicenseInfo:
    def test_valid_license(self):
        info = LicenseInfo(
            company_name="テスト株式会社",
            is_valid=True,
            monthly_quota=1000,
            used_this_month=50,
        )
        assert info.is_valid
        assert info.monthly_quota - info.used_this_month == 950
