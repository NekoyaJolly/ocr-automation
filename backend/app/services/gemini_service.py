"""Gemini API を使った OCR + 構造化抽出サービス。"""

import base64
import json
import time
from typing import Any

import structlog
from google import genai
from google.genai import types

from app.core.exceptions import GeminiError

logger = structlog.get_logger()


class ExtractResult:
    """Gemini 抽出結果。"""

    def __init__(
        self,
        data: dict[str, Any],
        input_tokens: int,
        output_tokens: int,
        processing_time_ms: int,
        model_used: str,
    ) -> None:
        self.data = data
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.processing_time_ms = processing_time_ms
        self.model_used = model_used


class GeminiService:
    """Gemini に画像を送って構造化抽出を行うサービス。"""

    def __init__(self, client: genai.Client, model_name: str) -> None:
        self._client = client
        self._model = model_name

    async def extract(
        self,
        image_base64: str,
        image_mime_type: str,
        extraction_prompt: str,
        response_schema: dict[str, Any],
    ) -> ExtractResult:
        """画像から構造化データを抽出する。

        Args:
            image_base64: 画像の base64 エンコード文字列。
            image_mime_type: MIME タイプ。
            extraction_prompt: 抽出指示プロンプト。
            response_schema: JSON Schema。

        Returns:
            ExtractResult: 抽出結果。

        Raises:
            GeminiError: API 呼び出し失敗。
        """
        try:
            image_bytes = base64.b64decode(image_base64)
            image_part = types.Part.from_bytes(data=image_bytes, mime_type=image_mime_type)

            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                thinking_config=types.ThinkingConfig(thinking_level="low"),
                temperature=0.0,
            )

            start = time.time()
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=[image_part, extraction_prompt],
                config=config,
            )
            elapsed_ms = int((time.time() - start) * 1000)

            data = json.loads(response.text)

            input_tokens = 0
            output_tokens = 0
            if response.usage_metadata:
                input_tokens = response.usage_metadata.prompt_token_count or 0
                output_tokens = response.usage_metadata.candidates_token_count or 0

            return ExtractResult(
                data=data,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                processing_time_ms=elapsed_ms,
                model_used=self._model,
            )
        except Exception as e:
            logger.exception("Gemini API 呼び出しに失敗", error=str(e))
            raise GeminiError(f"Gemini API error: {e}") from e
