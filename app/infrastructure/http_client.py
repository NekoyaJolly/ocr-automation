"""バックエンド API への HTTP クライアント (httpx ベース)。"""

import os

import httpx

from app.infrastructure.logger import get_logger

logger = get_logger(__name__)

DEFAULT_BACKEND_URL = os.environ.get(
    "BACKEND_BASE_URL", "https://ocr-backend.example.run.app"
)


class HttpClient:
    """バックエンド API との通信を担当する。

    Args:
        base_url: バックエンド API のベース URL。
        timeout: リクエストタイムアウト秒数。
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BACKEND_URL,
        timeout: float = 30.0,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={"User-Agent": "OCRAutomation/0.1.0"},
        )

    def post(
        self,
        path: str,
        *,
        json_data: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """POST リクエストを送信する。

        Args:
            path: エンドポイントパス (例: /api/v1/ocr/extract)。
            json_data: リクエストボディ (JSON)。
            headers: 追加ヘッダ。

        Returns:
            httpx.Response オブジェクト。

        Raises:
            httpx.HTTPStatusError: 4xx/5xx レスポンス。
        """
        response = self._client.post(path, json=json_data, headers=headers or {})
        response.raise_for_status()
        return response

    def get(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """GET リクエストを送信する。"""
        response = self._client.get(path, headers=headers or {})
        response.raise_for_status()
        return response

    def close(self) -> None:
        """HTTP クライアントを閉じる。"""
        self._client.close()
