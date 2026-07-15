"""Atomic lifecycle client and deterministic snapshot tests."""

from __future__ import annotations

import gzip
import hashlib
import json

import httpx

from src.operations import (
    CorpusSnapshotService,
    SnapshotRecords,
    SupabaseCorpusLifecycleRepository,
)


def test_lifecycle_client_calls_protected_activation_and_rollback_rpcs() -> None:
    calls: list[tuple[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.read())
        calls.append((request.url.path, payload))
        version = payload["p_version"]
        return httpx.Response(
            200,
            json=[
                {
                    "active_version": version,
                    "archived_version": "previous-v1",
                    "activated_at": "2026-07-15T00:00:00Z",
                }
            ],
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://project.supabase.co",
    )
    repository = SupabaseCorpusLifecycleRepository(
        base_url="https://project.supabase.co",
        api_key="server-secret",
        client=client,
    )

    activation = repository.activate("current-v2")
    rollback = repository.rollback("previous-v1")

    assert activation.action == "activate"
    assert activation.active_version == "current-v2"
    assert rollback.action == "rollback"
    assert calls == [
        ("/rest/v1/rpc/activate_corpus_version", {"p_version": "current-v2"}),
        ("/rest/v1/rpc/rollback_corpus_version", {"p_version": "previous-v1"}),
    ]


class FakeSnapshotRepository:
    def __init__(self) -> None:
        self.records = SnapshotRecords(
            corpus={"id": "corpus-id", "version": "v1", "status": "active"},
            pages=({"id": "page-id", "title": "Football Helmet"},),
            attributions=({"id": "source-id", "wiki_page_id": "page-id"},),
            aliases=({"id": "alias-id", "alias": "Mũ da heo"},),
            chunks=(
                {
                    "id": "chunk-id",
                    "wiki_page_id": "page-id",
                    "content": "Evidence",
                    "embedding": "[1,0]",
                },
            ),
        )
        self.object_bytes = b""
        self.manifest_bytes = b""
        self.manifest: dict[str, object] = {}

    def load_snapshot_records(self, version: str) -> SnapshotRecords:
        assert version == "v1"
        return self.records

    def store_snapshot(
        self,
        version: str,
        *,
        object_bytes: bytes,
        manifest_bytes: bytes,
        manifest: dict[str, object],
    ) -> None:
        assert version == "v1"
        self.object_bytes = object_bytes
        self.manifest_bytes = manifest_bytes
        self.manifest = manifest


def test_snapshot_is_gzipped_checksummed_and_contains_restore_dependencies() -> None:
    repository = FakeSnapshotRepository()

    report = CorpusSnapshotService(repository).export("v1")

    assert report.sha256 == hashlib.sha256(repository.object_bytes).hexdigest()
    assert repository.manifest["includes_embeddings"] is True
    assert repository.manifest["record_counts"] == {
        "wiki_pages": 1,
        "source_attributions": 1,
        "entity_aliases": 1,
        "document_chunks": 1,
    }
    records = [json.loads(line) for line in gzip.decompress(repository.object_bytes).splitlines()]
    assert [record["record_type"] for record in records] == [
        "corpus",
        "wiki_page",
        "source_attribution",
        "entity_alias",
        "document_chunk",
    ]
    assert records[-1]["data"]["embedding"] == "[1,0]"
