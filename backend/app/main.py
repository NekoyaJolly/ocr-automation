"""FastAPI アプリケーション エントリポイント。"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.firestore_client import create_firestore_client
from app.core.gemini_client import create_gemini_client
from app.core.logging_config import configure_logging
from app.middleware.auth import LicenseAuthMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.routers import health, license, ocr
from app.services.gemini_service import GeminiService


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """アプリケーションのライフサイクル管理。"""
    settings = get_settings()
    configure_logging(settings.log_level)

    application.state.db = create_firestore_client()
    application.state.settings = settings

    client = create_gemini_client()
    application.state.gemini_service = GeminiService(
        client,
        settings.gemini_model,
        thinking_level=settings.gemini_thinking_level,
    )

    yield


app = FastAPI(
    title="OCR Automation Backend",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(LicenseAuthMiddleware)

app.include_router(health.router)
app.include_router(license.router, prefix="/api/v1/license")
app.include_router(ocr.router, prefix="/api/v1/ocr")
