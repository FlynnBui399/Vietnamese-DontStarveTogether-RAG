"""Atomic lifecycle client and deterministic snapshot tests."""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import replace

import httpx
import pytest

from src.operations import (
    CorpusRestoreService,
    CorpusSnapshotService,
    SnapshotError,
    SnapshotRecords,
    SupabaseCorpusLifecycleRepository,
    SupabaseRestoreRepository,
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
            embedding_model={"id": "model-id", "model_key": "model-v1"},
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
        "embedding_models": 1,
        "wiki_pages": 1,
        "source_attributions": 1,
        "entity_aliases": 1,
        "document_chunks": 1,
    }
    records = [json.loads(line) for line in gzip.decompress(repository.object_bytes).splitlines()]
    assert [record["record_type"] for record in records] == [
        "corpus",
        "embedding_model",
        "wiki_page",
        "source_attribution",
        "entity_alias",
        "document_chunk",
    ]
    assert records[-1]["data"]["embedding"] == "[1,0]"


class FakeRestoreRepository:
    def __init__(self, manifest_bytes: bytes, object_bytes: bytes) -> None:
        self.manifest_bytes = manifest_bytes
        self.object_bytes = object_bytes
        self.imported = False

    def download_snapshot(self, version: str) -> tuple[bytes, bytes]:
        assert version == "v1"
        return self.manifest_bytes, self.object_bytes

    def import_records(
        self,
        *,
        target_version: str,
        source_version: str,
        manifest: dict[str, object],
        records: dict[str, list[dict[str, object]]],
    ) -> str:
        assert target_version == "restored-v1"
        assert source_version == "v1"
        assert manifest["schema_version"] == 1
        assert len(records["document_chunk"]) == 1
        self.imported = True
        return "restored-id"


def test_restore_verifies_checksum_and_leaves_corpus_validating() -> None:
    snapshot_repository = FakeSnapshotRepository()
    snapshot = CorpusSnapshotService(snapshot_repository).export("v1")
    restore_repository = FakeRestoreRepository(
        snapshot_repository.manifest_bytes,
        snapshot_repository.object_bytes,
    )

    report = CorpusRestoreService(restore_repository).restore("v1", "restored-v1")

    assert restore_repository.imported
    assert report.corpus_id == "restored-id"
    assert report.status == "validating"
    assert report.sha256 == snapshot.sha256


def test_restore_rejects_tampered_snapshot_before_import() -> None:
    snapshot_repository = FakeSnapshotRepository()
    CorpusSnapshotService(snapshot_repository).export("v1")
    restore_repository = FakeRestoreRepository(
        snapshot_repository.manifest_bytes,
        snapshot_repository.object_bytes + b"tampered",
    )

    with pytest.raises(SnapshotError, match="checksum"):
        CorpusRestoreService(restore_repository).restore("v1", "restored-v1")

    assert not restore_repository.imported


def test_restore_accepts_a_verified_snapshot_with_no_alias_rows() -> None:
    snapshot_repository = FakeSnapshotRepository()
    snapshot_repository.records = replace(snapshot_repository.records, aliases=())
    CorpusSnapshotService(snapshot_repository).export("v1")
    restore_repository = FakeRestoreRepository(
        snapshot_repository.manifest_bytes,
        snapshot_repository.object_bytes,
    )

    report = CorpusRestoreService(restore_repository).restore("v1", "restored-v1")

    assert report.status == "validating"
    assert restore_repository.imported


def test_restore_preserves_an_existing_compatible_embedding_model() -> None:
    requests: list[tuple[str, str]] = []
    model = {
        "model_key": "model-v1",
        "provider": "fixture",
        "model_name": "fixture-model",
        "model_revision": "1",
        "dimensions": 2,
        "distance_metric": "cosine",
        "normalized": True,
        "is_active": True,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        return httpx.Response(
            200,
            json=[
                {
                    key: value
                    for key, value in model.items()
                    if key not in {"model_key", "is_active"}
                }
            ],
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    repository = SupabaseRestoreRepository(
        base_url="https://project.supabase.co",
        api_key="server-secret",
        bucket="snapshots",
        client=client,
    )

    repository._upsert_embedding_model(model)

    assert requests == [("GET", "/rest/v1/embedding_models")]
