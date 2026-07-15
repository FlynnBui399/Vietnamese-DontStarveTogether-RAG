"""Run bounded DST page discovery and emit an include/exclude report."""

import argparse
import json
from pathlib import Path

from src.config import get_settings
from src.ingestion import DiscoveryPolicy, MediaWikiClient, PageDiscovery

DEFAULT_CONFIG = Path("data/ingestion/discovery_config.json")


def build_parser() -> argparse.ArgumentParser:
    """Build the small, explicit discovery CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--max-depth", type=int)
    parser.add_argument("--report", type=Path)
    return parser


def main() -> int:
    """Verify siteinfo, discover bounded pages, and optionally persist the report locally."""
    args = build_parser().parse_args()
    settings = get_settings()
    policy = DiscoveryPolicy.from_path(
        args.config,
        max_depth=args.max_depth,
        max_pages=args.max_pages,
    )
    with MediaWikiClient(
        api_url=str(settings.wiki_api_url),
        user_agent=settings.wiki_user_agent,
        request_delay_seconds=settings.wiki_request_delay_ms / 1000,
        timeout_seconds=settings.wiki_request_timeout_seconds,
        max_retries=settings.wiki_max_retries,
        cache_dir=settings.wiki_cache_dir,
        cache_ttl_seconds=settings.wiki_cache_ttl_seconds,
    ) as client:
        site_info = client.site_info().to_dict()
        discovery = PageDiscovery(client).discover(policy).to_dict()

    output = {"site_info": site_info, "discovery_report": discovery}
    serialized = json.dumps(output, ensure_ascii=False, indent=2)
    print(serialized)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(f"{serialized}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
