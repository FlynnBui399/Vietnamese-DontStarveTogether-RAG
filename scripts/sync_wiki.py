"""Synchronize bounded latest wiki revisions into private Supabase storage and tables."""

import argparse
import json
from pathlib import Path

from src.config import get_settings
from src.ingestion import DiscoveryPolicy, MediaWikiClient, SyncManager
from src.supabase_store import SupabaseIngestionRepository

DEFAULT_CONFIG = Path("data/ingestion/discovery_config.json")


def build_parser() -> argparse.ArgumentParser:
    """Build the ingestion CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--max-depth", type=int)
    parser.add_argument("--sync-type", choices=("initial", "incremental"), default="initial")
    parser.add_argument("--report", type=Path)
    return parser


def main() -> int:
    """Run ingestion only with a backend-only Supabase credential."""
    args = build_parser().parse_args()
    settings = get_settings()
    admin_key = settings.supabase_admin_api_key
    if settings.supabase_url is None or admin_key is None:
        raise SystemExit(
            "SUPABASE_URL and SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY are required"
        )

    policy = DiscoveryPolicy.from_path(
        args.config,
        max_depth=args.max_depth,
        max_pages=args.max_pages,
    )
    with (
        MediaWikiClient(
            api_url=str(settings.wiki_api_url),
            user_agent=settings.wiki_user_agent,
            request_delay_seconds=settings.wiki_request_delay_ms / 1000,
            timeout_seconds=settings.wiki_request_timeout_seconds,
            max_retries=settings.wiki_max_retries,
            cache_dir=settings.wiki_cache_dir,
            cache_ttl_seconds=settings.wiki_cache_ttl_seconds,
        ) as wiki_client,
        SupabaseIngestionRepository(
            base_url=str(settings.supabase_url),
            api_key=admin_key.get_secret_value(),
            raw_bucket=settings.supabase_raw_bucket,
            timeout_seconds=settings.wiki_request_timeout_seconds,
        ) as repository,
    ):
        summary = SyncManager(wiki_client, repository).run(policy, sync_type=args.sync_type)

    serialized = json.dumps(summary.to_dict(), ensure_ascii=False, indent=2)
    print(serialized)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(f"{serialized}\n", encoding="utf-8")
    return 0 if summary.status == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
