"""Backend-only construction of the grounded answer pipeline."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, status

from src.config import Settings, get_settings
from src.embeddings import (
    DeterministicHashEmbeddingAdapter,
    EmbeddingAdapter,
    EmbeddingModelManifest,
    OllamaEmbeddingAdapter,
)
from src.generation import GroundedAnswerService, OllamaLLMAdapter
from src.retrieval import ContextAssembler, RetrievalService
from src.supabase_store import SupabaseAliasRepository, SupabaseRetrievalRepository
from src.terminology import AliasResolver, QueryExpander


def _model_key(provider: str, model: str, dimensions: int, revision: str) -> str:
    raw = f"{provider}-{model}-{dimensions}-{revision}".casefold()
    return re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-")


def _embedding_adapter(settings: Settings) -> EmbeddingAdapter:
    model = (
        settings.embedding_model
        if settings.embedding_provider == "ollama"
        else "deterministic-hash"
    )
    revision = settings.embedding_model_revision if settings.embedding_provider == "ollama" else "1"
    manifest = EmbeddingModelManifest(
        model_key=_model_key(
            settings.embedding_provider,
            model,
            settings.embedding_dimensions,
            revision,
        ),
        provider=settings.embedding_provider,
        model_name=model,
        model_revision=revision,
        dimensions=settings.embedding_dimensions,
        batch_size=settings.embedding_batch_size,
    )
    if settings.embedding_provider == "ollama":
        return OllamaEmbeddingAdapter(
            manifest,
            base_url=str(settings.embedding_base_url),
            timeout_seconds=settings.embedding_timeout_seconds,
        )
    return DeterministicHashEmbeddingAdapter(manifest)


def get_answer_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Iterator[GroundedAnswerService]:
    """Yield a request-scoped service and close provider connections afterward."""
    api_key = settings.supabase_admin_api_key
    if settings.supabase_url is None or api_key is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge service is not configured.",
        )
    secret = api_key.get_secret_value()
    try:
        with SupabaseAliasRepository(
            base_url=str(settings.supabase_url),
            api_key=secret,
        ) as alias_repository:
            aliases = alias_repository.list_aliases()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge service is unavailable.",
        ) from exc
    if not aliases:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge aliases have not been synchronized.",
        )

    embedding_adapter = _embedding_adapter(settings)
    retrieval_repository = SupabaseRetrievalRepository(
        base_url=str(settings.supabase_url),
        api_key=secret,
    )
    llm = OllamaLLMAdapter(
        model=settings.llm_model,
        base_url=str(settings.ollama_base_url),
        temperature=settings.llm_temperature,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    retrieval_service = RetrievalService(
        retrieval_repository,
        embedding_adapter,
        QueryExpander(AliasResolver(aliases)),
        context_assembler=ContextAssembler(token_budget=settings.max_context_tokens),
        evidence_threshold=settings.min_evidence_score,
    )
    try:
        yield GroundedAnswerService(
            retrieval_service,
            llm,
            match_count=settings.retrieval_match_count,
        )
    finally:
        retrieval_repository.close()
        llm.close()
        if isinstance(embedding_adapter, OllamaEmbeddingAdapter):
            embedding_adapter.close()
