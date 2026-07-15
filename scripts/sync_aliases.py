"""Synchronize the repository glossary into the protected Supabase alias table."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.config import Settings
from src.supabase_store import SupabaseAliasRepository
from src.terminology import DEFAULT_GLOSSARY_PATH, Glossary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--glossary",
        type=Path,
        default=DEFAULT_GLOSSARY_PATH,
        help="version-controlled glossary CSV",
    )
    return parser.parse_args()


def main() -> int:
    """Load, validate, and idempotently upsert the glossary."""
    args = parse_args()
    settings = Settings()
    api_key = settings.supabase_admin_api_key
    if settings.supabase_url is None or api_key is None:
        raise SystemExit("SUPABASE_URL and a backend secret/service-role key are required")
    glossary = Glossary.load(args.glossary)
    with SupabaseAliasRepository(
        base_url=str(settings.supabase_url),
        api_key=api_key.get_secret_value(),
    ) as repository:
        synchronized = repository.sync_aliases(glossary.records)
        stored = repository.list_aliases()
    print(
        json.dumps(
            {
                "glossary": args.glossary.as_posix(),
                "synchronized": synchronized,
                "stored_total": len(stored),
                "verified_total": sum(alias.verified for alias in stored),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
