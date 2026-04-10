"""Gemini API クライアントの初期化。"""

from google import genai

from app.core.config import get_settings, load_secret


def create_gemini_client() -> genai.Client:
    """Gemini API クライアントを生成する。

    環境変数 ``BACKEND_GEMINI_API_KEY`` (Settings.gemini_api_key) を優先し、
    未設定の場合は Secret Manager から取得する。
    いずれからも有効なキーが得られない場合は RuntimeError を投げる。
    """
    settings = get_settings()

    api_key = (settings.gemini_api_key or "").strip()
    if api_key:
        return genai.Client(api_key=api_key)

    try:
        secret_key = load_secret(
            settings.gemini_api_key_secret_name,
            settings.project_id,
        )
    except Exception as e:
        raise RuntimeError(
            "Gemini API key could not be loaded: set BACKEND_GEMINI_API_KEY or "
            "configure Google Cloud Secret Manager (BACKEND_GEMINI_API_KEY_SECRET_NAME)."
        ) from e

    secret_key = (secret_key or "").strip()
    if not secret_key:
        raise RuntimeError(
            "Gemini API key could not be loaded: set BACKEND_GEMINI_API_KEY or "
            "configure Google Cloud Secret Manager (BACKEND_GEMINI_API_KEY_SECRET_NAME)."
        )

    return genai.Client(api_key=secret_key)
