"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.middleware import SecurityHeadersMiddleware
from apps.api.routes.chat import router as chat_router
from apps.api.routes.health import router as health_router
from apps.api.routes.knowledge import router as knowledge_router
from src.config import get_settings

settings = get_settings()

app = FastAPI(
    title="DST Vietnamese Knowledge Assistant API",
    version="0.1.0",
    docs_url="/docs" if settings.app_env != "production" else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(settings.frontend_origin).rstrip("/")],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.include_router(health_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(knowledge_router, prefix="/api")
