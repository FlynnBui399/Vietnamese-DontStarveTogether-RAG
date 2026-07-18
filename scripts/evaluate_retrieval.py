"""Evaluate active-corpus hybrid retrieval against the milestone dataset."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from src.config import Settings
from src.embeddings import (
    DeterministicHashEmbeddingAdapter,
    EmbeddingModelManifest,
    OllamaEmbeddingAdapter,
)
from src.evaluation import DEFAULT_RETRIEVAL_DATASET, RetrievalEvaluationDataset, RetrievalEvaluator
from src.retrieval import RetrievalService
from src.supabase_store import SupabaseAliasRepository, SupabaseRetrievalRepository
from src.terminology import AliasResolver, QueryExpander


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_RETRIEVAL_DATASET)
    parser.add_argument("--provider", choices=("ollama", "deterministic"))
    parser.add_argument("--model")
    parser.add_argument("--model-key")
    parser.add_argument("--revision")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _model_key(provider: str, model: str, dimensions: int, revision: str) -> str:
    raw = f"{provider}-{model}-{dimensions}-{revision}".casefold()
    return re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-")


def main() -> int:
    """Run retrieval evaluation with the exact active-corpus embedding model contract."""
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
    manifest = EmbeddingModelManifest(
        model_key=args.model_key
        or _model_key(provider, model, settings.embedding_dimensions, revision),
        provider=provider,
        model_name=model,
        model_revision=revision,
        dimensions=settings.embedding_dimensions,
        batch_size=settings.embedding_batch_size,
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
    secret = api_key.get_secret_value()
    try:
        with SupabaseAliasRepository(
            base_url=str(settings.supabase_url),
            api_key=secret,
        ) as alias_repository:
            aliases = alias_repository.list_aliases()
        if not aliases:
            raise SystemExit("No stored aliases; run scripts.sync_aliases first")
        with SupabaseRetrievalRepository(
            base_url=str(settings.supabase_url),
            api_key=secret,
        ) as retrieval_repository:
            service = RetrievalService(
                retrieval_repository,
                adapter,
                QueryExpander(AliasResolver(aliases)),
            )
            report = RetrievalEvaluator(service).evaluate(
                RetrievalEvaluationDataset.load(args.dataset)
            )
    finally:
        if isinstance(adapter, OllamaEmbeddingAdapter):
            adapter.close()
    rendered = json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
