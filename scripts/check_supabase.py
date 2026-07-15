"""Exit successfully only when the configured development Supabase API is reachable."""

import asyncio

from apps.api.routes.health import check_supabase
from src.config import get_settings


async def main() -> int:
    """Run the shared connectivity probe without printing credentials."""
    result = await check_supabase(get_settings())
    print(f"Supabase: {result.status} - {result.detail}")
    return 0 if result.status == "connected" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
