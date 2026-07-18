"""Opt-in local Supabase acceptance test for Milestone 5 embeddings and indexes."""

import os

import httpx
import pytest

from src.embeddings import (
    DeterministicHashEmbeddingAdapter,
    EmbeddingModelManifest,
    EmbeddingWorker,
)
from src.processing import CorpusValidator, PageClassifier, SectionChunker, WikiPageCleaner
from src.processing.corpus_builder import CorpusBuilder
from src.supabase_store import SupabaseEmbeddingRepository, SupabaseProcessingRepository


def _live_environment() -> tuple[str, str]:
    if os.getenv("RUN_MILESTONE5_LIVE") != "1":
        pytest.skip("set RUN_MILESTONE5_LIVE=1 for live embedding acceptance")
    base_url = os.getenv("SUPABASE_TEST_URL")
    api_key = os.getenv("SUPABASE_TEST_SECRET_KEY") or os.getenv("SUPABASE_TEST_SERVICE_ROLE_KEY")
    if base_url is None or api_key is None:
        pytest.skip("local Supabase server credentials are not configured")
    return base_url, api_key


def test_live_embedding_run_populates_every_chunk_and_searches_both_indexes() -> None:
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
            version="milestone5-live-test",
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
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Accept-Profile": "knowledge",
    }
    with SupabaseEmbeddingRepository(base_url=base_url, api_key=api_key) as repository:
        report = EmbeddingWorker(repository, adapter).run("milestone5-live-test")
        with httpx.Client(base_url=base_url, headers=headers, timeout=20.0) as client:
            sample_response = client.get(
                "/rest/v1/document_chunks",
                params={
                    "corpus_version_id": f"eq.{report.corpus_id}",
                    "game_scope": "eq.dst",
                    "select": "page_title",
                    "order": "page_title.asc",
                    "limit": "1",
                },
            )
            sample_response.raise_for_status()
            sample_title = str(sample_response.json()[0]["page_title"])
        lexical = repository.lexical_search(report.corpus_id, sample_title)
        semantic = repository.semantic_search(
            report.corpus_id,
            adapter.embed([sample_title])[0],
        )

    assert report.status == "passed"
    assert report.total_chunk_count == report.embedded_chunk_count > 0
    assert report.recorded_error_count == 0
    assert lexical and lexical[0]["page_title"] == sample_title
    assert semantic and semantic[0]["page_title"] == sample_title

    with httpx.Client(
        base_url=base_url,
        headers={**headers, "Prefer": "count=exact", "Range": "0-0"},
        timeout=20.0,
    ) as client:
        response = client.get(
            "/rest/v1/document_chunks",
            params={
                "corpus_version_id": f"eq.{report.corpus_id}",
                "embedding": "not.is.null",
                "select": "id",
            },
        )
        response.raise_for_status()
    assert int(response.headers["content-range"].rsplit("/", 1)[1]) == report.total_chunk_count
