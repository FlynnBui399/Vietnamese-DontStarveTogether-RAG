"""Verify the configured MediaWiki endpoint and print non-sensitive site information."""

import json

from src.config import get_settings
from src.ingestion import MediaWikiClient


def main() -> int:
    """Return success only when the Action API siteinfo query succeeds."""
    settings = get_settings()
    with MediaWikiClient(
        api_url=str(settings.wiki_api_url),
        user_agent=settings.wiki_user_agent,
        request_delay_seconds=settings.wiki_request_delay_ms / 1000,
        timeout_seconds=settings.wiki_request_timeout_seconds,
        max_retries=settings.wiki_max_retries,
        cache_dir=settings.wiki_cache_dir,
        cache_ttl_seconds=settings.wiki_cache_ttl_seconds,
    ) as client:
        print(json.dumps(client.site_info().to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
