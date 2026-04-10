"""create_gemini_client のユニットテスト。"""

from unittest.mock import MagicMock

import pytest

from app.core import gemini_client
from app.core.config import get_settings
from app.core.gemini_client import create_gemini_client


def test_create_gemini_client_uses_env_key_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """環境変数 (Settings.gemini_api_key) が設定されていれば Secret Manager を呼ばない。"""
    monkeypatch.setenv("BACKEND_GEMINI_API_KEY", "env-key-123")
    get_settings.cache_clear()

    mock_client_ctor = MagicMock(return_value=MagicMock(name="Client"))
    monkeypatch.setattr(gemini_client.genai, "Client", mock_client_ctor)

    called: list[tuple] = []

    def _no_secret(*_args: object, **_kwargs: object) -> str:
        called.append(("load_secret",))
        return "should-not-use"

    monkeypatch.setattr(gemini_client, "load_secret", _no_secret)

    create_gemini_client()

    mock_client_ctor.assert_called_once_with(api_key="env-key-123")
    assert not called


def test_create_gemini_client_uses_secret_manager_when_env_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """環境変数が空のとき load_secret の結果で Client を生成する (Secret Manager 経路)。"""
    # OS 環境を空にし、.env のキーより優先させる (delenv だけだと .env が残る)
    monkeypatch.setenv("BACKEND_GEMINI_API_KEY", "")
    get_settings.cache_clear()

    mock_client_ctor = MagicMock(return_value=MagicMock(name="Client"))
    monkeypatch.setattr(gemini_client.genai, "Client", mock_client_ctor)

    def _fake_load_secret(secret_name: str, project_id: str) -> str:
        assert secret_name
        assert project_id
        return "key-from-secret-manager"

    monkeypatch.setattr(gemini_client, "load_secret", _fake_load_secret)

    create_gemini_client()

    mock_client_ctor.assert_called_once_with(api_key="key-from-secret-manager")


def test_create_gemini_client_raises_when_secret_manager_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """環境変数なしかつ load_secret が例外のとき RuntimeError。"""
    monkeypatch.setenv("BACKEND_GEMINI_API_KEY", "")
    get_settings.cache_clear()

    def _boom(_secret_name: str, _project_id: str) -> str:
        raise PermissionError("no access")

    monkeypatch.setattr(gemini_client, "load_secret", _boom)

    with pytest.raises(RuntimeError, match="Gemini API key could not be loaded"):
        create_gemini_client()


def test_create_gemini_client_raises_when_secret_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """環境変数なしかつ Secret Manager が空文字のとき RuntimeError。"""
    monkeypatch.setenv("BACKEND_GEMINI_API_KEY", "")
    get_settings.cache_clear()

    monkeypatch.setattr(
        gemini_client,
        "load_secret",
        lambda _n, _p: "",
    )

    with pytest.raises(RuntimeError, match="Gemini API key could not be loaded"):
        create_gemini_client()


def test_create_gemini_client_whitespace_env_falls_back_to_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """環境変数が空白のみのときは Secret Manager 経路にフォールバックする。"""
    monkeypatch.setenv("BACKEND_GEMINI_API_KEY", "   ")
    get_settings.cache_clear()

    mock_client_ctor = MagicMock(return_value=MagicMock(name="Client"))
    monkeypatch.setattr(gemini_client.genai, "Client", mock_client_ctor)
    monkeypatch.setattr(
        gemini_client,
        "load_secret",
        lambda _n, _p: "sm-key",
    )

    create_gemini_client()
    mock_client_ctor.assert_called_once_with(api_key="sm-key")
