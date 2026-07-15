"""Generate and persist embeddings for one non-active corpus version."""

from __future__ import annotations

import argparse
import json
import re

from src.config import Settings
from src.embeddings import (
    DeterministicHashEmbeddingAdapter,
    EmbeddingModelManifest,
    EmbeddingWorker,
    OllamaEmbeddingAdapter,
)
from src.supabase_store import SupabaseEmbeddingRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-version", required=True)
    parser.add_argument("--provider", choices=("ollama", "deterministic"))
    parser.add_argument("--model")
    parser.add_argument("--model-key")
    parser.add_argument("--revision")
    parser.add_argument("--batch-size", type=int)
    return parser.parse_args()


def _model_key(provider: str, model: str, dimensions: int, revision: str) -> str:
    raw = f"{provider}-{model}-{dimensions}-{revision}".casefold()
    return re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-")


def main() -> int:
    """Embed missing chunks, recording every failure without activating the corpus."""
    args = parse_args()
    settings = Settings()
    api_key = settings.supabase_admin_api_key
    if settings.supabase_url is None or api_key is None:
        raise SystemExit("SUPABASE_URL and a backend secret/service-role key are required")
    provider = args.provider or settings.embedding_provider
    model = args.model or (
        settings.embedding_model if provider == "ollama" else "deterministic-hash"
    )
    revision = args.revision or (settings.embedding_model_revision if provider == "ollama" else "1")
    batch_size = args.batch_size or settings.embedding_batch_size
    manifest = EmbeddingModelManifest(
        model_key=args.model_key
        or _model_key(provider, model, settings.embedding_dimensions, revision),
        provider=provider,
        model_name=model,
        model_revision=revision,
        dimensions=settings.embedding_dimensions,
        batch_size=batch_size,
    )
    adapter = (
        OllamaEmbeddingAdapter(
            manifest,
            base_url=str(settings.embedding_base_url),
            timeout_seconds=settings.embedding_timeout_seconds,
        )
        if provider == "ollama"
        else DeterministicHashEmbeddingAdapter(manifest)
    )
    try:
        with SupabaseEmbeddingRepository(
            base_url=str(settings.supabase_url),
            api_key=api_key.get_secret_value(),
        ) as repository:
            report = EmbeddingWorker(repository, adapter).run(args.corpus_version)
    finally:
        if isinstance(adapter, OllamaEmbeddingAdapter):
            adapter.close()
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
