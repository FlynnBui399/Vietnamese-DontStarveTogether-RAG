"""Opt-in local Supabase acceptance test for Milestone 6 hybrid retrieval."""

import os
from datetime import UTC, datetime

import httpx
import pytest

from src.embeddings import (
    DeterministicHashEmbeddingAdapter,
    EmbeddingModelManifest,
    EmbeddingWorker,
)
from src.evaluation import RetrievalEvaluationDataset, RetrievalEvaluator
from src.processing import CorpusValidator, PageClassifier, SectionChunker, WikiPageCleaner
from src.processing.corpus_builder import CorpusBuilder
from src.retrieval import RetrievalService
from src.supabase_store import (
    SupabaseAliasRepository,
    SupabaseEmbeddingRepository,
    SupabaseProcessingRepository,
    SupabaseRetrievalRepository,
)
from src.terminology import AliasResolver, Glossary, QueryExpander


def _live_environment() -> tuple[str, str]:
    if os.getenv("RUN_MILESTONE6_LIVE") != "1":
        pytest.skip("set RUN_MILESTONE6_LIVE=1 for live hybrid retrieval acceptance")
    base_url = os.getenv("SUPABASE_TEST_URL")
    api_key = os.getenv("SUPABASE_TEST_SECRET_KEY") or os.getenv("SUPABASE_TEST_SERVICE_ROLE_KEY")
    if base_url is None or api_key is None:
        pytest.skip("local Supabase server credentials are not configured")
    return base_url, api_key


def _headers(api_key: str, *, write: bool = False) -> dict[str, str]:
    return {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Profile" if write else "Accept-Profile": "knowledge",
    }


def _temporarily_activate(
    client: httpx.Client,
    api_key: str,
    corpus_id: str,
) -> str | None:
    response = client.get(
        "/rest/v1/corpus_versions",
        headers=_headers(api_key),
        params={"status": "eq.active", "select": "id", "limit": "1"},
    )
    response.raise_for_status()
    rows = response.json()
    previous_id = str(rows[0]["id"]) if rows else None
    if previous_id == corpus_id:
        return previous_id
    if previous_id is not None:
        demote = client.patch(
            "/rest/v1/corpus_versions",
            headers=_headers(api_key, write=True),
            params={"id": f"eq.{previous_id}"},
            json={"status": "validating", "activated_at": None},
        )
        demote.raise_for_status()
    activate = client.patch(
        "/rest/v1/corpus_versions",
        headers=_headers(api_key, write=True),
        params={"id": f"eq.{corpus_id}"},
        json={"status": "active", "activated_at": datetime.now(UTC).isoformat()},
    )
    activate.raise_for_status()
    return previous_id


def _restore_activation(
    client: httpx.Client,
    api_key: str,
    corpus_id: str,
    previous_id: str | None,
) -> None:
    if previous_id == corpus_id:
        return
    demote = client.patch(
        "/rest/v1/corpus_versions",
        headers=_headers(api_key, write=True),
        params={"id": f"eq.{corpus_id}"},
        json={"status": "validating", "activated_at": None},
    )
    demote.raise_for_status()
    if previous_id is not None:
        restore = client.patch(
            "/rest/v1/corpus_versions",
            headers=_headers(api_key, write=True),
            params={"id": f"eq.{previous_id}"},
            json={"status": "active", "activated_at": datetime.now(UTC).isoformat()},
        )
        restore.raise_for_status()


def test_live_hybrid_retrieval_meets_scope_recall_and_latency_targets() -> None:
    base_url, api_key = _live_environment()
    classifier = PageClassifier()
    with SupabaseProcessingRepository(base_url=base_url, api_key=api_key) as repository:
        build = CorpusBuilder(
            repository,
            cleaner=WikiPageCleaner(),
            classifier=classifier,
            chunker=SectionChunker(classifier),
            validator=CorpusValidator(),
        ).build(
            version="milestone6-live-test",
            embedding_model_key="pending-1024",
            embedding_dimensions=1024,
        )
    assert build.status == "building"

    manifest = EmbeddingModelManifest(
        model_key="deterministic-hash-1024-v1",
        provider="deterministic",
        model_name="deterministic-hash",
        model_revision="1",
        dimensions=1024,
        batch_size=16,
    )
    adapter = DeterministicHashEmbeddingAdapter(manifest)
    with SupabaseEmbeddingRepository(base_url=base_url, api_key=api_key) as repository:
        embedding_report = EmbeddingWorker(repository, adapter).run("milestone6-live-test")
    assert embedding_report.status == "passed"

    glossary = Glossary.load()
    with SupabaseAliasRepository(base_url=base_url, api_key=api_key) as repository:
        repository.sync_aliases(glossary.records)
        aliases = repository.list_aliases()

    with httpx.Client(base_url=base_url, timeout=20.0) as client:
        previous_id = _temporarily_activate(client, api_key, embedding_report.corpus_id)
        try:
            with SupabaseRetrievalRepository(base_url=base_url, api_key=api_key) as repository:
                service = RetrievalService(
                    repository,
                    adapter,
                    QueryExpander(AliasResolver(aliases)),
                )
                sample = service.retrieve("ancent archive", match_count=10)
                evaluation = RetrievalEvaluator(service).evaluate(RetrievalEvaluationDataset.load())
        finally:
            _restore_activation(client, api_key, embedding_report.corpus_id, previous_id)

    assert sample.candidates[0].page_title == "Ancient Archive"
    assert sample.context.blocks
    assert all(candidate.game_scope == "dst" for candidate in sample.candidates)
    assert all(
        candidate.corpus_version_id == embedding_report.corpus_id for candidate in sample.candidates
    )
    assert evaluation.passed is True
    assert evaluation.entity_recall_at_5 >= 0.90
    assert evaluation.natural_recall_at_10 >= 0.85
    assert evaluation.scope_violation_count == 0
    assert evaluation.p95_retrieval_ms <= 250.0
