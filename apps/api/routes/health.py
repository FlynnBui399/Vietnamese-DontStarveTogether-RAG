"""Health endpoint and development Supabase connectivity probe."""

from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.config import Settings, get_settings

router = APIRouter(tags=["health"])


class DependencyHealth(BaseModel):
    """Availability of an external dependency."""

    status: Literal["connected", "not_configured", "unavailable"]
    detail: str


class HealthResponse(BaseModel):
    """Public API health contract."""

    service: str
    status: Literal["ok", "degraded"]
    environment: str
    supabase: DependencyHealth


async def check_supabase(settings: Settings) -> DependencyHealth:
    """Probe the Supabase API without exposing credentials or database contents."""
    if not settings.supabase_configured:
        return DependencyHealth(
            status="not_configured",
            detail="Supabase development credentials are not configured.",
        )

    assert settings.supabase_url is not None
    api_key = settings.supabase_api_key
    assert api_key is not None
    has_server_key = (
        settings.supabase_secret_key is not None or settings.supabase_service_role_key is not None
    )
    health_path = "rest/v1/" if has_server_key else "auth/v1/health"
    url = f"{str(settings.supabase_url).rstrip('/')}/{health_path}"

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(url, headers={"apikey": api_key.get_secret_value()})
            response.raise_for_status()
    except httpx.HTTPError:
        return DependencyHealth(
            status="unavailable",
            detail="Supabase development API did not pass the connectivity check.",
        )

    return DependencyHealth(
        status="connected",
        detail="Supabase development API is reachable.",
    )


@router.get("/health", response_model=HealthResponse)
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    """Report API health and the truthfully observed Supabase state."""
    supabase = await check_supabase(settings)
    return HealthResponse(
        service="dst-vietnamese-rag-api",
        status="ok" if supabase.status == "connected" else "degraded",
        environment=settings.app_env,
        supabase=supabase,
    )
