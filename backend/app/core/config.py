"""環境変数・Secret Manager からの設定読み込み。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """バックエンドアプリケーション設定。"""

    project_id: str = "ocr-automation-dev"
    firestore_database: str = "(default)"
    gemini_api_key_secret_name: str = "gemini-api-key"
    gemini_api_key: str = ""  # ローカル開発用、本番では Secret Manager
    gemini_model: str = "gemini-3.1-pro-preview"
    log_level: str = "INFO"
    rate_limit_per_minute: int = 60
    rate_limit_per_second: int = 5

    model_config = SettingsConfigDict(
        env_prefix="BACKEND_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """シングルトンで設定を取得する。"""
    return Settings()


def load_secret(secret_name: str, project_id: str) -> str:
    """Secret Manager からシークレットを読み込む。"""
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")
