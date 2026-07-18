"""Public-safe knowledge repository and API tests."""

import asyncio
from typing import cast

import httpx

from apps.api.dependencies import get_knowledge_repository
from apps.api.main import app
from src.supabase_store import (
    PublicCorpusStatus,
    SupabaseKnowledgeRepository,
)


def _client(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=handler, base_url="https://project.supabase.co")


def test_public_corpus_status_contains_no_credentials() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/corpus_versions"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "active-id",
                        "version": "v1",
                        "page_count": 30,
                        "chunk_count": 120,
                        "embedding_model_key": "bge-m3-1024",
                        "activated_at": "2026-07-15T00:00:00Z",
                    }
                ],
            )
        return httpx.Response(200, json=[{"finished_at": "2026-07-14T00:00:00Z"}])

    repository = SupabaseKnowledgeRepository(
        base_url="https://project.supabase.co",
        api_key="server-secret",
        client=_client(httpx.MockTransport(handler)),
    )

    status = repository.get_corpus_status()

    assert status.available
    assert status.version == "v1"
    assert status.chunk_count == 120
    assert "secret" not in repr(status).casefold()


def test_entity_search_ranks_verified_exact_alias_and_deduplicates() -> None:
    aliases = [
        {
            "entity_title": "Football Helmet",
            "entity_slug": "football-helmet",
            "alias": "Mũ da heo",
            "alias_normalized": "mu da heo",
            "alias_type": "community_translation",
            "priority": 85,
            "confidence": 0.95,
            "verified": True,
        },
        {
            "entity_title": "Football Helmet",
            "entity_slug": "football-helmet",
            "alias": "Football Hat",
            "alias_normalized": "football hat",
            "alias_type": "common_misspelling",
            "priority": 70,
            "confidence": 0.9,
            "verified": True,
        },
    ]
    repository = SupabaseKnowledgeRepository(
        base_url="https://project.supabase.co",
        api_key="server-secret",
        client=_client(httpx.MockTransport(lambda _request: httpx.Response(200, json=aliases))),
    )

    results = repository.search_entities("mu da heo")

    assert len(results) == 1
    assert results[0].title == "Football Helmet"
    assert results[0].matched_alias == "Mũ da heo"


def test_source_read_rejects_building_corpus() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/document_chunks"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "chunk-id",
                        "corpus_version_id": "building-id",
                        "page_title": "Item",
                        "section_path": "Overview",
                        "content": "Evidence",
                        "canonical_url": "https://example.invalid/item",
                        "revision_id": 1,
                        "source_kind": "factual_article",
                        "subjective": False,
                    }
                ],
            )
        assert request.url.params["status"] == "in.(active,archived)"
        return httpx.Response(200, json=[])

    repository = SupabaseKnowledgeRepository(
        base_url="https://project.supabase.co",
        api_key="server-secret",
        client=_client(httpx.MockTransport(handler)),
    )

    assert repository.get_source("chunk-id") is None


class FakeKnowledgeRepository:
    def get_corpus_status(self) -> PublicCorpusStatus:
        return PublicCorpusStatus(
            available=False,
            version=None,
            page_count=0,
            chunk_count=0,
            embedding_model=None,
            activated_at=None,
            last_sync_at=None,
        )


def _fake_repository() -> SupabaseKnowledgeRepository:
    return cast(SupabaseKnowledgeRepository, FakeKnowledgeRepository())


def test_corpus_status_endpoint_returns_public_contract() -> None:
    app.dependency_overrides[get_knowledge_repository] = _fake_repository

    async def request_status() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/corpus/status")

    try:
        response = asyncio.run(request_status())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "available": False,
        "version": None,
        "page_count": 0,
        "chunk_count": 0,
        "embedding_model": None,
        "activated_at": None,
        "last_sync_at": None,
    }
