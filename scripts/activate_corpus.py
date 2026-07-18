"""Atomically activate a validated corpus and write its private checksummed snapshot."""

from __future__ import annotations

import argparse
import json

from src.config import Settings
from src.operations import (
    CorpusSnapshotService,
    SupabaseCorpusLifecycleRepository,
    SupabaseSnapshotRepository,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument(
        "--skip-snapshot",
        action="store_true",
        help="Emergency-only activation without the normal application snapshot.",
    )
    return parser.parse_args()


def main() -> int:
    """Activate through PostgreSQL, then export the now-immutable active corpus."""
    args = parse_args()
    settings = Settings()
    api_key = settings.supabase_admin_api_key
    if settings.supabase_url is None or api_key is None:
        raise SystemExit("SUPABASE_URL and a backend secret/service-role key are required")
    secret = api_key.get_secret_value()
    with SupabaseCorpusLifecycleRepository(
        base_url=str(settings.supabase_url),
        api_key=secret,
    ) as lifecycle:
        transition = lifecycle.activate(args.version)

    snapshot = None
    if not args.skip_snapshot:
        with SupabaseSnapshotRepository(
            base_url=str(settings.supabase_url),
            api_key=secret,
            bucket=settings.supabase_snapshot_bucket,
        ) as repository:
            snapshot = CorpusSnapshotService(repository).export(args.version)

    print(
        json.dumps(
            {
                "transition": transition.to_dict(),
                "snapshot": snapshot.to_dict() if snapshot is not None else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
