"""Opt-in local Supabase acceptance test for Milestone 3 corpus processing."""

import os

import httpx
import pytest

from src.processing import CorpusValidator, PageClassifier, SectionChunker, WikiPageCleaner
from src.processing.corpus_builder import CorpusBuilder
from src.supabase_store import SupabaseProcessingRepository


def _live_environment() -> tuple[str, str]:
    if os.getenv("RUN_MILESTONE3_LIVE") != "1":
        pytest.skip("set RUN_MILESTONE3_LIVE=1 for live corpus processing")
    base_url = os.getenv("SUPABASE_TEST_URL")
    api_key = os.getenv("SUPABASE_TEST_SECRET_KEY") or os.getenv("SUPABASE_TEST_SERVICE_ROLE_KEY")
    if base_url is None or api_key is None:
        pytest.skip("local Supabase server credentials are not configured")
    return base_url, api_key


def test_live_corpus_build_covers_all_raw_pages_without_duplicates() -> None:
    base_url, api_key = _live_environment()
    classifier = PageClassifier()
    with SupabaseProcessingRepository(base_url=base_url, api_key=api_key) as repository:
        report = CorpusBuilder(
            repository,
            cleaner=WikiPageCleaner(),
            classifier=classifier,
            chunker=SectionChunker(classifier),
            validator=CorpusValidator(),
        ).build(
            version="milestone3-live-test",
            embedding_model_key="pending-1024",
            embedding_dimensions=1024,
        )

    assert report.status == "building"
    assert report.source_page_count >= 30
    assert report.parsed_page_count == report.source_page_count
    assert report.validation is not None and report.validation.passed is True
    assert report.validation.metadata_completeness >= 0.95
    assert report.validation.empty_count == 0
    assert report.validation.covered_page_count == report.source_page_count
    assert report.inserted_chunk_count > 0

    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Accept-Profile": "knowledge",
    }
    with httpx.Client(base_url=base_url, headers=headers, timeout=20.0) as client:
        corpus_response = client.get(
            "/rest/v1/corpus_versions",
            params={
                "id": f"eq.{report.corpus_id}",
                "select": "status,page_count,chunk_count,manifest",
            },
        )
        corpus_response.raise_for_status()
        corpus = corpus_response.json()[0]
        chunk_response = client.get(
            "/rest/v1/document_chunks",
            params={
                "corpus_version_id": f"eq.{report.corpus_id}",
                "select": (
                    "source_key,wiki_page_id,page_title,section_path,content,canonical_url,"
                    "revision_id,game_scope,metadata"
                ),
            },
        )
        chunk_response.raise_for_status()
        chunks = chunk_response.json()

    assert corpus["status"] == "building"
    assert corpus["page_count"] == report.source_page_count
    assert corpus["chunk_count"] == report.inserted_chunk_count
    assert corpus["manifest"]["processing_status"] == "passed"
    assert len(chunks) == report.inserted_chunk_count
    assert len({chunk["wiki_page_id"] for chunk in chunks}) == report.source_page_count
    assert len({chunk["source_key"] for chunk in chunks}) == len(chunks)
    assert len({chunk["metadata"]["body_hash"] for chunk in chunks}) == len(chunks)
    assert all(
        chunk["page_title"]
        and chunk["section_path"]
        and chunk["content"]
        and chunk["canonical_url"]
        and chunk["revision_id"]
        and chunk["game_scope"]
        for chunk in chunks
    )
