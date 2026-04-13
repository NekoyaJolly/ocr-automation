"""industry_presets の単体テスト。"""

import pytest

from app.core.industry_presets import INDUSTRY_PRESETS, get_industry_preset


def test_general_preset_has_role():
    p = get_industry_preset("general")
    assert "事務" in p["role"] or "アシスタント" in p["role"]


@pytest.mark.parametrize(
    "key",
    ["construction", "restaurant", "retail", "manufacturing"],
)
def test_skeleton_presets_exist(key: str):
    assert key in INDUSTRY_PRESETS
    assert "role" in INDUSTRY_PRESETS[key]


def test_unknown_key_falls_back_to_general():
    p = get_industry_preset("no_such_industry")
    assert p == INDUSTRY_PRESETS["general"]
