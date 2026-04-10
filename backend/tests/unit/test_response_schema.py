"""バンドル response_schema が GenerateContentConfig で受理されることの検証。"""

from pathlib import Path

import pytest
import yaml
from google.genai import types


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "yaml_name",
    ["default_invoice.yaml", "default_receipt.yaml"],
)
def test_bundled_template_response_schema_accepted_by_genai(yaml_name: str) -> None:
    path = _repo_root() / "templates" / yaml_name
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    schema = raw["response_schema"]

    cfg = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0.0,
    )
    assert cfg.response_schema is not None
