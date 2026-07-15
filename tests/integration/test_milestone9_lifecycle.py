"""Opt-in local Supabase acceptance for activation, snapshot, and rollback."""

import os

import httpx
import pytest

from src.operations import (
    CorpusSnapshotService,
    SupabaseCorpusLifecycleRepository,
    SupabaseSnapshotRepository,
)

PAGE_ID = "00000000-0000-0000-0000-000000000003"


def _live_environment() -> tuple[str, str]:
    if os.getenv("RUN_MILESTONE9_LIVE") != "1":
        pytest.skip("set RUN_MILESTONE9_LIVE=1 for live lifecycle acceptance")
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


def _create_ready_corpus(
    client: httpx.Client,
    api_key: str,
    *,
    corpus_id: str,
    version: str,
    content: str,
) -> None:
    corpus = client.post(
        "/rest/v1/corpus_versions",
        headers=_headers(api_key, write=True),
        json={
            "id": corpus_id,
            "version": version,
            "status": "validating",
            "embedding_model_key": "fixture-hash-1024",
            "page_count": 1,
            "chunk_count": 1,
            "source_revision_max": 1,
            "manifest": {"processing_status": "passed", "embedding_status": "passed"},
        },
    )
    corpus.raise_for_status()
    chunk = client.post(
        "/rest/v1/document_chunks",
        headers=_headers(api_key, write=True),
        json={
            "corpus_version_id": corpus_id,
            "wiki_page_id": PAGE_ID,
            "source_key": "a" * 64,
            "page_title": "Milestone Fixture",
            "section_path": "Overview",
            "chunk_index": 0,
            "content": content,
            "content_normalized": content.casefold(),
            "content_hash": "b" * 64,
            "token_count": 4,
            "game_scope": "dst",
            "entity_type": "other",
            "source_kind": "factual_article",
            "subjective": False,
            "canonical_url": "https://example.invalid/wiki/Milestone_Fixture",
            "revision_id": 1,
            "search_text": content,
            "embedding": [1.0] + [0.0] * 1023,
            "metadata": {"body_hash": "c" * 64},
        },
    )
    chunk.raise_for_status()


def test_atomic_activation_snapshot_and_rollback() -> None:
    base_url, api_key = _live_environment()
    first_id = "90000000-0000-0000-0000-000000000001"
    second_id = "90000000-0000-0000-0000-000000000002"
    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        _create_ready_corpus(
            client,
            api_key,
            corpus_id=first_id,
            version="milestone9-v1",
            content="First complete corpus evidence",
        )
        _create_ready_corpus(
            client,
            api_key,
            corpus_id=second_id,
            version="milestone9-v2",
            content="Second complete corpus evidence",
        )

        with SupabaseCorpusLifecycleRepository(base_url=base_url, api_key=api_key) as lifecycle:
            first = lifecycle.activate("milestone9-v1")
            second = lifecycle.activate("milestone9-v2")
        assert first.archived_version is None
        assert second.archived_version == "milestone9-v1"

        with SupabaseSnapshotRepository(
            base_url=base_url,
            api_key=api_key,
            bucket="dst-corpus-snapshots",
        ) as snapshots:
            snapshot = CorpusSnapshotService(snapshots).export("milestone9-v1")
        assert snapshot.chunk_count == 1
        assert len(snapshot.sha256) == 64

        with SupabaseCorpusLifecycleRepository(base_url=base_url, api_key=api_key) as lifecycle:
            rollback = lifecycle.rollback("milestone9-v1")
        assert rollback.active_version == "milestone9-v1"
        assert rollback.archived_version == "milestone9-v2"

        active = client.get(
            "/rest/v1/corpus_versions",
            headers=_headers(api_key),
            params={"status": "eq.active", "select": "version"},
        )
        active.raise_for_status()
        assert active.json() == [{"version": "milestone9-v1"}]

        demote = client.patch(
            "/rest/v1/corpus_versions",
            headers=_headers(api_key, write=True),
            params={"id": f"eq.{first_id}"},
            json={"status": "validating", "activated_at": None},
        )
        demote.raise_for_status()
        cleanup = client.delete(
            "/rest/v1/corpus_versions",
            headers=_headers(api_key, write=True),
            params={"id": f"in.({first_id},{second_id})"},
        )
        cleanup.raise_for_status()
        storage_cleanup = client.request(
            "DELETE",
            "/storage/v1/object/dst-corpus-snapshots",
            headers={
                "apikey": api_key,
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "prefixes": [
                    "corpus/milestone9-v1/chunks.jsonl.gz",
                    "corpus/milestone9-v1/manifest.json",
                ]
            },
        )
        storage_cleanup.raise_for_status()
