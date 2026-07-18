"""Checksum-verified application snapshot restore into a non-active corpus."""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from src.operations.snapshot import SnapshotError


@dataclass(frozen=True, slots=True)
class RestoreReport:
    """Verified outcome of one application-level restore."""

    source_version: str
    restored_version: str
    corpus_id: str
    sha256: str
    page_count: int
    chunk_count: int
    status: str = "validating"

    def to_dict(self) -> dict[str, object]:
        return {
            "source_version": self.source_version,
            "restored_version": self.restored_version,
            "corpus_id": self.corpus_id,
            "sha256": self.sha256,
            "page_count": self.page_count,
            "chunk_count": self.chunk_count,
            "status": self.status,
        }


class RestoreRepository(Protocol):
    """Snapshot download and relational import boundary."""

    def download_snapshot(self, version: str) -> tuple[bytes, bytes]: ...

    def import_records(
        self,
        *,
        target_version: str,
        source_version: str,
        manifest: dict[str, Any],
        records: dict[str, list[dict[str, Any]]],
    ) -> str: ...


class CorpusRestoreService:
    """Verify archive integrity before any non-active database import begins."""

    ALLOWED_TYPES = {
        "corpus",
        "embedding_model",
        "wiki_page",
        "source_attribution",
        "entity_alias",
        "document_chunk",
    }
    REQUIRED_TYPES = ALLOWED_TYPES - {"entity_alias"}

    def __init__(self, repository: RestoreRepository) -> None:
        self.repository = repository

    def restore(self, source_version: str, target_version: str) -> RestoreReport:
        """Restore a private snapshot and leave it validating for benchmark review."""
        if not source_version.strip() or not target_version.strip():
            raise ValueError("Source and target corpus versions are required")
        if source_version == target_version:
            raise ValueError("Restore target version must differ from the snapshot source")
        manifest_bytes, object_bytes = self.repository.download_snapshot(source_version)
        try:
            manifest = json.loads(manifest_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SnapshotError("Snapshot manifest is not valid UTF-8 JSON") from exc
        if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
            raise SnapshotError("Unsupported snapshot manifest schema")
        if manifest.get("corpus_version") != source_version:
            raise SnapshotError("Snapshot manifest version does not match the requested source")
        observed_checksum = hashlib.sha256(object_bytes).hexdigest()
        if observed_checksum != manifest.get("sha256"):
            raise SnapshotError("Snapshot SHA-256 checksum does not match its manifest")
        try:
            raw = gzip.decompress(object_bytes).decode("utf-8")
        except (gzip.BadGzipFile, UnicodeDecodeError) as exc:
            raise SnapshotError("Snapshot object is not valid gzip UTF-8 JSONL") from exc

        records: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for line_number, line in enumerate(raw.splitlines(), start=1):
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SnapshotError(f"Snapshot JSONL line {line_number} is invalid") from exc
            if not isinstance(item, dict) or not isinstance(item.get("data"), dict):
                raise SnapshotError(f"Snapshot JSONL line {line_number} has no record data")
            record_type = str(item.get("record_type"))
            records[record_type].append(item["data"])
        record_types = set(records)
        if record_types - self.ALLOWED_TYPES or self.REQUIRED_TYPES - record_types:
            raise SnapshotError("Snapshot record types are incomplete or unsupported")
        if len(records["corpus"]) != 1 or len(records["embedding_model"]) != 1:
            raise SnapshotError("Snapshot must contain exactly one corpus and embedding model")
        self._validate_counts(manifest, records)
        corpus_id = self.repository.import_records(
            target_version=target_version,
            source_version=source_version,
            manifest=manifest,
            records=dict(records),
        )
        return RestoreReport(
            source_version=source_version,
            restored_version=target_version,
            corpus_id=corpus_id,
            sha256=observed_checksum,
            page_count=len(records["wiki_page"]),
            chunk_count=len(records["document_chunk"]),
        )

    @staticmethod
    def _validate_counts(
        manifest: dict[str, Any],
        records: dict[str, list[dict[str, Any]]],
    ) -> None:
        counts = manifest.get("record_counts")
        if not isinstance(counts, dict):
            raise SnapshotError("Snapshot manifest has no record counts")
        expected = {
            "embedding_models": len(records["embedding_model"]),
            "wiki_pages": len(records["wiki_page"]),
            "source_attributions": len(records["source_attribution"]),
            "entity_aliases": len(records["entity_alias"]),
            "document_chunks": len(records["document_chunk"]),
        }
        if any(counts.get(key) != value for key, value in expected.items()):
            raise SnapshotError("Snapshot record counts do not match the manifest")


class SupabaseRestoreRepository:
    """Restore verified snapshot records through backend-only Supabase APIs."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        bucket: str,
        timeout_seconds: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.bucket = bucket
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._auth_headers = {
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
        }

    def __enter__(self) -> SupabaseRestoreRepository:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the internally owned HTTP client."""
        if self._owns_client:
            self._client.close()

    def download_snapshot(self, version: str) -> tuple[bytes, bytes]:
        """Download the private manifest and gzip object without creating local files."""
        manifest = self._download(f"corpus/{version}/manifest.json")
        object_bytes = self._download(f"corpus/{version}/chunks.jsonl.gz")
        return manifest, object_bytes

    def import_records(
        self,
        *,
        target_version: str,
        source_version: str,
        manifest: dict[str, Any],
        records: dict[str, list[dict[str, Any]]],
    ) -> str:
        """Import dependencies first and keep the restored corpus non-active."""
        if self._get_rows(
            "corpus_versions",
            {"version": f"eq.{target_version}", "select": "id", "limit": "1"},
        ):
            raise SnapshotError(f"Restore target corpus {target_version} already exists")
        self._upsert_embedding_model(records["embedding_model"][0])
        page_ids = self._upsert_pages(records["wiki_page"])
        self._upsert_aliases(records["entity_alias"])
        self._upsert_attributions(records["source_attribution"], page_ids)
        source_corpus = records["corpus"][0]
        restored_manifest = source_corpus.get("manifest")
        prior_manifest = restored_manifest if isinstance(restored_manifest, dict) else {}
        corpus_payload = {
            "version": target_version,
            "status": "validating",
            "embedding_model_key": source_corpus["embedding_model_key"],
            "page_count": source_corpus["page_count"],
            "chunk_count": source_corpus["chunk_count"],
            "source_revision_max": source_corpus.get("source_revision_max"),
            "completed_at": datetime.now(UTC).isoformat(),
            "manifest": {
                **prior_manifest,
                "restore": {
                    "source_version": source_version,
                    "restored_at": datetime.now(UTC).isoformat(),
                    "snapshot_sha256": manifest["sha256"],
                },
            },
        }
        corpus_rows = self._post_rows(
            "corpus_versions",
            corpus_payload,
            operation="create restored corpus",
        )
        corpus_id = str(corpus_rows[0]["id"])
        try:
            self._insert_chunks(records["document_chunk"], corpus_id, page_ids)
        except Exception:
            response = self._client.patch(
                f"{self.base_url}/rest/v1/corpus_versions",
                headers=self._database_headers(write=True),
                params={"id": f"eq.{corpus_id}"},
                json={"status": "failed"},
            )
            self._raise_for_status(response, "mark failed restore")
            raise
        return corpus_id

    def _download(self, path: str) -> bytes:
        encoded = "/".join(quote(part, safe="") for part in path.split("/"))
        response = self._client.get(
            f"{self.base_url}/storage/v1/object/{self.bucket}/{encoded}",
            headers=self._auth_headers,
        )
        self._raise_for_status(response, f"download snapshot {path}")
        return response.content

    def _upsert_embedding_model(self, row: dict[str, Any]) -> None:
        model_key = str(row["model_key"])
        existing = self._get_rows(
            "embedding_models",
            {
                "model_key": f"eq.{model_key}",
                "select": (
                    "provider,model_name,model_revision,dimensions,distance_metric,normalized"
                ),
                "limit": "1",
            },
        )
        if existing:
            contract_fields = (
                "provider",
                "model_name",
                "model_revision",
                "dimensions",
                "distance_metric",
                "normalized",
            )
            if any(existing[0].get(field) != row.get(field) for field in contract_fields):
                raise SnapshotError(
                    f"Embedding model {model_key} exists with an incompatible contract"
                )
            return
        payload = {key: value for key, value in row.items() if key not in {"id", "created_at"}}
        payload["is_active"] = False
        self._upsert_rows("embedding_models", [payload], "model_key")

    def _upsert_pages(self, pages: Sequence[dict[str, Any]]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for page in pages:
            old_id = str(page["id"])
            existing = self._get_rows(
                "wiki_pages",
                {
                    "mediawiki_page_id": f"eq.{page['mediawiki_page_id']}",
                    "revision_id": f"eq.{page['revision_id']}",
                    "select": "id",
                    "limit": "1",
                },
            )
            if existing:
                mapping[old_id] = str(existing[0]["id"])
                continue
            current = self._get_rows(
                "wiki_pages",
                {
                    "mediawiki_page_id": f"eq.{page['mediawiki_page_id']}",
                    "is_active": "eq.true",
                    "select": "id",
                    "limit": "1",
                },
            )
            payload = {key: value for key, value in page.items() if key != "id"}
            payload["is_active"] = not current
            created = self._post_rows("wiki_pages", payload, operation="restore wiki page")
            mapping[old_id] = str(created[0]["id"])
        return mapping

    def _upsert_aliases(self, aliases: Sequence[dict[str, Any]]) -> None:
        rows = [
            {key: value for key, value in alias.items() if key not in {"id", "created_at"}}
            for alias in aliases
        ]
        self._upsert_rows("entity_aliases", rows, "entity_title,alias_normalized")

    def _upsert_attributions(
        self,
        attributions: Sequence[dict[str, Any]],
        page_ids: dict[str, str],
    ) -> None:
        rows = []
        for attribution in attributions:
            payload = {
                key: value for key, value in attribution.items() if key not in {"id", "created_at"}
            }
            payload["wiki_page_id"] = page_ids[str(attribution["wiki_page_id"])]
            rows.append(payload)
        self._upsert_rows("source_attributions", rows, "wiki_page_id,source_url")

    def _insert_chunks(
        self,
        chunks: Sequence[dict[str, Any]],
        corpus_id: str,
        page_ids: dict[str, str],
    ) -> None:
        rows: list[dict[str, Any]] = []
        for chunk in chunks:
            payload = {
                key: value for key, value in chunk.items() if key not in {"id", "created_at", "fts"}
            }
            payload["corpus_version_id"] = corpus_id
            payload["wiki_page_id"] = page_ids[str(chunk["wiki_page_id"])]
            rows.append(payload)
        for offset in range(0, len(rows), 100):
            response = self._client.post(
                f"{self.base_url}/rest/v1/document_chunks",
                headers=self._database_headers(write=True),
                json=rows[offset : offset + 100],
            )
            self._raise_for_status(response, "restore document chunks")

    def _upsert_rows(self, table: str, rows: Sequence[dict[str, Any]], conflict: str) -> None:
        for offset in range(0, len(rows), 100):
            batch = rows[offset : offset + 100]
            if not batch:
                continue
            response = self._client.post(
                f"{self.base_url}/rest/v1/{table}",
                headers={
                    **self._database_headers(write=True),
                    "Prefer": "resolution=merge-duplicates",
                },
                params={"on_conflict": conflict},
                json=batch,
            )
            self._raise_for_status(response, f"restore {table}")

    def _post_rows(
        self,
        table: str,
        payload: dict[str, Any],
        *,
        operation: str,
    ) -> list[dict[str, Any]]:
        response = self._client.post(
            f"{self.base_url}/rest/v1/{table}",
            headers={**self._database_headers(write=True), "Prefer": "return=representation"},
            json=payload,
        )
        self._raise_for_status(response, operation)
        result = response.json()
        if not isinstance(result, list) or not result or not isinstance(result[0], dict):
            raise SnapshotError(f"Supabase {operation} returned no row")
        return [row for row in result if isinstance(row, dict)]

    def _get_rows(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        response = self._client.get(
            f"{self.base_url}/rest/v1/{table}",
            headers=self._database_headers(),
            params=params,
        )
        self._raise_for_status(response, f"load {table} during restore")
        result = response.json()
        if not isinstance(result, list):
            raise SnapshotError(f"Supabase {table} restore response is not a list")
        return [row for row in result if isinstance(row, dict)]

    def _database_headers(self, *, write: bool = False) -> dict[str, str]:
        profile = "Content-Profile" if write else "Accept-Profile"
        return {**self._auth_headers, profile: "knowledge"}

    @staticmethod
    def _raise_for_status(response: httpx.Response, operation: str) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SnapshotError(
                f"Supabase could not {operation} (HTTP {response.status_code})"
            ) from exc
