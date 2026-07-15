"""Health endpoint tests."""

import asyncio
from types import TracebackType
from typing import Self

import httpx
import pytest

from apps.api.main import app
from apps.api.routes.health import check_supabase
from src.config import Settings


def test_health_reports_unconfigured_supabase_honestly() -> None:
    """The API remains inspectable without pretending Supabase is connected."""

    async def request_health() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/health")

    response = asyncio.run(request_health())

    assert response.status_code == 200
    assert response.json() == {
        "service": "dst-vietnamese-rag-api",
        "status": "degraded",
        "environment": "development",
        "supabase": {
            "status": "not_configured",
            "detail": "Supabase development credentials are not configured.",
        },
    }


def test_publishable_key_uses_non_privileged_health_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A publishable key can verify the gateway without schema introspection."""
    requested_urls: list[str] = []

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 3.0

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            traceback: TracebackType | None,
        ) -> None:
            return None

        async def get(self, url: str, headers: dict[str, str]) -> httpx.Response:
            requested_urls.append(url)
            assert headers["apikey"] == "publishable-placeholder"
            return httpx.Response(200, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_publishable_key="publishable-placeholder",
    )

    result = asyncio.run(check_supabase(settings))

    assert result.status == "connected"
    assert requested_urls == ["https://example.supabase.co/auth/v1/health"]
