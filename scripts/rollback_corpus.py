"""Atomically restore one archived corpus version."""

from __future__ import annotations

import argparse
import json

from src.config import Settings
from src.operations import SupabaseCorpusLifecycleRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    return parser.parse_args()


def main() -> int:
    """Validate an archived version and make it active in one database transaction."""
    args = parse_args()
    settings = Settings()
    api_key = settings.supabase_admin_api_key
    if settings.supabase_url is None or api_key is None:
        raise SystemExit("SUPABASE_URL and a backend secret/service-role key are required")
    with SupabaseCorpusLifecycleRepository(
        base_url=str(settings.supabase_url),
        api_key=api_key.get_secret_value(),
    ) as repository:
        transition = repository.rollback(args.version)
    print(json.dumps(transition.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
