"""OCR エンジン — 抽象インターフェース + GeminiBackendEngine 実装。"""

import base64
import mimetypes
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.exceptions import BackendUnreachableError, OCREngineError
from app.infrastructure.http_client import HttpClient
from app.infrastructure.logger import get_logger
from app.models.ocr_result_model import OCRResult

logger = get_logger(__name__)


class OCREngine(ABC):
    """OCR エンジンの抽象インターフェース。"""

    @abstractmethod
    def process(
        self,
        image_path: Path,
        extraction_prompt: str,
        response_schema: dict[str, Any],
        license_key: str,
    ) -> OCRResult:
        """画像から構造化データを抽出する。

        Args:
            image_path: 入力画像のパス。
            extraction_prompt: Gemini への指示プロンプト。
            response_schema: JSON Schema (Gemini structured output)。
            license_key: ライセンスキー。

        Returns:
            OCRResult: 抽出結果。
        """
        ...


class GeminiBackendEngine(OCREngine):
    """バックエンド API 経由で Gemini を呼び出す OCR エンジン実装。"""

    def __init__(self, http_client: HttpClient) -> None:
        self._http = http_client

    def process(
        self,
        image_path: Path,
        extraction_prompt: str,
        response_schema: dict[str, Any],
        license_key: str,
    ) -> OCRResult:
        """バックエンドに画像を送信し、構造化抽出結果を受け取る。"""
        image_b64 = self._encode_image(image_path)
        mime_type = self._detect_mime(image_path)

        payload = {
            "image_base64": image_b64,
            "image_mime_type": mime_type,
            "extraction_prompt": extraction_prompt,
            "response_schema": response_schema,
        }
        headers = {"X-License-Key": license_key}

        try:
            response = self._http.post(
                "/api/v1/ocr/extract",
                json_data=payload,
                headers=headers,
            )
        except Exception as e:
            raise BackendUnreachableError(f"バックエンド通信エラー: {e}") from e

        try:
            body = response.json()
        except Exception as e:
            raise OCREngineError(f"レスポンスのパースに失敗: {e}") from e

        return OCRResult(
            source_image=image_path,
            extracted_data=body.get("data", {}),
            raw_response=body,
            processing_time_ms=body.get("processing_time_ms", 0),
        )

    @staticmethod
    def _encode_image(path: Path) -> str:
        """画像を base64 エンコードする。"""
        return base64.b64encode(path.read_bytes()).decode("ascii")

    @staticmethod
    def _detect_mime(path: Path) -> str:
        """ファイル拡張子から MIME タイプを推定する。"""
        mime, _ = mimetypes.guess_type(str(path))
        return mime or "application/octet-stream"
