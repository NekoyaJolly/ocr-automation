"""GeminiService のユニットテスト。"""

import base64
from unittest.mock import AsyncMock, MagicMock

import pytest
from google.genai import types

from app.services.gemini_service import GeminiService


@pytest.mark.asyncio
async def test_extract_passes_model_and_thinking_config_medium() -> None:
    """モデル名が API に渡り、thinking_level=medium と temperature=0.0 が設定される。"""
    mock_response = MagicMock()
    mock_response.text = '{"x": 1}'
    mock_response.usage_metadata = None

    generate_mock = AsyncMock(return_value=mock_response)
    client = MagicMock()
    client.aio.models.generate_content = generate_mock

    model_id = "gemini-3.1-pro-preview"
    svc = GeminiService(client, model_id, thinking_level="medium")

    img_b64 = base64.b64encode(b"\xff\xd8\xff").decode("ascii")
    await svc.extract(
        image_base64=img_b64,
        image_mime_type="image/jpeg",
        extraction_prompt="extract",
        response_schema={"type": "object"},
    )

    generate_mock.assert_awaited_once()
    kwargs = generate_mock.await_args.kwargs
    assert kwargs["model"] == model_id

    cfg: types.GenerateContentConfig = kwargs["config"]
    assert cfg.temperature == 0.0
    assert cfg.response_mime_type == "application/json"
    assert cfg.thinking_config is not None
    assert cfg.thinking_config.thinking_level == types.ThinkingLevel.MEDIUM


@pytest.mark.asyncio
async def test_extract_respects_custom_thinking_level_low() -> None:
    mock_response = MagicMock()
    mock_response.text = "{}"
    mock_response.usage_metadata = None

    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    svc = GeminiService(client, "m", thinking_level="low")
    await svc.extract(
        image_base64=base64.b64encode(b"x").decode(),
        image_mime_type="image/jpeg",
        extraction_prompt="p",
        response_schema={"type": "object"},
    )
    call_kw = client.aio.models.generate_content.await_args.kwargs
    cfg: types.GenerateContentConfig = call_kw["config"]
    assert cfg.thinking_config.thinking_level == types.ThinkingLevel.LOW


@pytest.mark.asyncio
async def test_extract_result_model_used_matches_settings_model() -> None:
    """ExtractResult.model_used は Settings から渡したモデル名 (コンストラクタ引数) と一致する。"""
    mock_response = MagicMock()
    mock_response.text = "{}"
    mock_response.usage_metadata = None

    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    custom = "custom-model-from-env"
    svc = GeminiService(client, custom)
    result = await svc.extract(
        image_base64=base64.b64encode(b"x").decode(),
        image_mime_type="image/jpeg",
        extraction_prompt="p",
        response_schema={"type": "object"},
    )
    assert result.model_used == custom
