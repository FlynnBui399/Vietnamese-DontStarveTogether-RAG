"""Build and validate a non-active corpus from current private raw wiki snapshots."""

import argparse
import json
from datetime import UTC, datetime

from src.config import get_settings
from src.processing import (
    ChunkingConfig,
    CorpusValidator,
    PageClassifier,
    SectionChunker,
    WikiPageCleaner,
)
from src.processing.corpus_builder import CorpusBuilder
from src.supabase_store import SupabaseProcessingRepository


def build_parser() -> argparse.ArgumentParser:
    """Build the processing CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version")
    parser.add_argument("--target-tokens", type=int, default=450)
    parser.add_argument("--max-tokens", type=int, default=600)
    parser.add_argument("--overlap-tokens", type=int, default=60)
    return parser


def main() -> int:
    """Process raw pages only with a backend-only Supabase credential."""
    args = build_parser().parse_args()
    settings = get_settings()
    admin_key = settings.supabase_admin_api_key
    if settings.supabase_url is None or admin_key is None:
        raise SystemExit(
            "SUPABASE_URL and SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY are required"
        )
    version = args.version or datetime.now(UTC).strftime("processing-%Y%m%dT%H%M%SZ")
    embedding_model_key = f"pending-{settings.embedding_dimensions}"
    classifier = PageClassifier()
    chunking_config = ChunkingConfig(
        target_tokens=args.target_tokens,
        max_tokens=args.max_tokens,
        overlap_tokens=args.overlap_tokens,
    )

    with SupabaseProcessingRepository(
        base_url=str(settings.supabase_url),
        api_key=admin_key.get_secret_value(),
    ) as repository:
        report = CorpusBuilder(
            repository,
            cleaner=WikiPageCleaner(),
            classifier=classifier,
            chunker=SectionChunker(classifier, chunking_config),
            validator=CorpusValidator(),
        ).build(
            version=version,
            embedding_model_key=embedding_model_key,
            embedding_dimensions=settings.embedding_dimensions,
        )

    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.status == "building" else 1


if __name__ == "__main__":
    raise SystemExit(main())
