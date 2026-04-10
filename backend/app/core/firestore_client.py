"""Firestore AsyncClient のファクトリ。"""

import os

from google.cloud.firestore import AsyncClient  # type: ignore[import-untyped]

from app.core.config import get_settings


def create_firestore_client() -> AsyncClient:
    """Firestore AsyncClient を生成する。

    FIRESTORE_EMULATOR_HOST が設定されている場合はエミュレータに接続。
    """
    settings = get_settings()

    if os.environ.get("FIRESTORE_EMULATOR_HOST"):
        return AsyncClient(project=settings.project_id)

    return AsyncClient(
        project=settings.project_id,
        database=settings.firestore_database,
    )
