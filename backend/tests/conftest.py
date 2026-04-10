"""pytest 共通設定。

lifespan で常に Gemini クライアントを初期化するため、テストではダミー API キーを付与する。
"""

import os

import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _test_gemini_api_key_and_clear_settings_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """各テスト前に Settings キャッシュをクリアし、未設定ならダミー Gemini キーを設定する。"""
    get_settings.cache_clear()
    if not (os.environ.get("BACKEND_GEMINI_API_KEY") or "").strip():
        monkeypatch.setenv("BACKEND_GEMINI_API_KEY", "test-dummy-gemini-key-for-pytest")
    yield
    get_settings.cache_clear()
