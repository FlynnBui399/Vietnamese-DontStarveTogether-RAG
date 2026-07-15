"""Checksummed application-level corpus snapshots in private Supabase Storage."""

from __future__ import annotations

import gzip
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import quote

import httpx


class SnapshotError(RuntimeError):
    """Raised when snapshot export or private persistence fails."""


@dataclass(frozen=True, slots=True)
class SnapshotRecords:
    """Complete relational records required for an application-level restore."""

    corpus: dict[str, Any]
    embedding_model: dict[str, Any]
    pages: tuple[dict[str, Any], ...]
    attributions: tuple[dict[str, Any], ...]
    aliases: tuple[dict[str, Any], ...]
    chunks: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class SnapshotReport:
    """Stored snapshot identity and integrity metadata."""

    corpus_version: str
    object_path: str
    manifest_path: str
    sha256: str
    byte_count: int
    page_count: int
    chunk_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "corpus_version": self.corpus_version,
            "object_path": self.object_path,
            "manifest_path": self.manifest_path,
            "sha256": self.sha256,
            "byte_count": self.byte_count,
            "page_count": self.page_count,
            "chunk_count": self.chunk_count,
        }


class SnapshotRepository(Protocol):
    """Persistence operations needed by the deterministic snapshot exporter."""

    def load_snapshot_records(self, version: str) -> SnapshotRecords: ...

    def store_snapshot(
        self,
        version: str,
        *,
        object_bytes: bytes,
        manifest_bytes: bytes,
        manifest: dict[str, object],
    ) -> None: ...


class CorpusSnapshotService:
    """Serialize a corpus deterministically, checksum it, and persist it privately."""

    def __init__(self, repository: SnapshotRepository) -> None:
        self.repository = repository

    def export(self, version: str) -> SnapshotReport:
        """Export active/archived corpus data including vectors needed for restore."""
        records = self.repository.load_snapshot_records(version)
        rows: list[dict[str, object]] = [{"record_type": "corpus", "data": records.corpus}]
        rows.append({"record_type": "embedding_model", "data": records.embedding_model})
        rows.extend({"record_type": "wiki_page", "data": row} for row in records.pages)
        rows.extend(
            {"record_type": "source_attribution", "data": row} for row in records.attributions
        )
        rows.extend({"record_type": "entity_alias", "data": row} for row in records.aliases)
        rows.extend({"record_type": "document_chunk", "data": row} for row in records.chunks)
        raw = "".join(
            f"{json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}\n"
            for row in rows
        ).encode("utf-8")
        compressed = gzip.compress(raw, compresslevel=9, mtime=0)
        checksum = hashlib.sha256(compressed).hexdigest()
        object_path = f"corpus/{version}/chunks.jsonl.gz"
        manifest_path = f"corpus/{version}/manifest.json"
        created_at = datetime.now(UTC).isoformat()
        manifest: dict[str, object] = {
            "schema_version": 1,
            "corpus_version": version,
            "created_at": created_at,
            "object_path": object_path,
            "compression": "gzip",
            "sha256": checksum,
            "byte_count": len(compressed),
            "includes_embeddings": True,
            "record_counts": {
                "embedding_models": 1,
                "wiki_pages": len(records.pages),
                "source_attributions": len(records.attributions),
                "entity_aliases": len(records.aliases),
                "document_chunks": len(records.chunks),
            },
        }
        manifest_bytes = (
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        self.repository.store_snapshot(
            version,
            object_bytes=compressed,
            manifest_bytes=manifest_bytes,
            manifest=manifest,
        )
        return SnapshotReport(
            corpus_version=version,
            object_path=object_path,
            manifest_path=manifest_path,
            sha256=checksum,
            byte_count=len(compressed),
            page_count=len(records.pages),
            chunk_count=len(records.chunks),
        )


class SupabaseSnapshotRepository:
    """Load relational records and store snapshot objects using a server credential."""

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

    def __enter__(self) -> SupabaseSnapshotRepository:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the internally owned HTTP client."""
        if self._owns_client:
            self._client.close()

    def load_snapshot_records(self, version: str) -> SnapshotRecords:
        """Load one immutable active/archived corpus and all restore dependencies."""
        corpus_rows = self._get_rows(
            "corpus_versions",
            {
                "version": f"eq.{version}",
                "status": "in.(active,archived)",
                "select": "*",
                "limit": "1",
            },
        )
        if not corpus_rows:
            raise SnapshotError("Snapshot source must be an active or archived corpus")
        corpus = corpus_rows[0]
        corpus_id = str(corpus["id"])
        model_rows = self._get_rows(
            "embedding_models",
            {
                "model_key": f"eq.{corpus['embedding_model_key']}",
                "select": "*",
                "limit": "1",
            },
        )
        if not model_rows:
            raise SnapshotError("Snapshot corpus has no embedding model contract")
        chunk_fields = (
            "id,wiki_page_id,source_key,page_title,section_path,chunk_index,content,"
            "content_normalized,content_hash,token_count,game_scope,entity_type,source_kind,"
            "subjective,canonical_url,revision_id,search_text,embedding,metadata,created_at"
        )
        chunks = self._get_all(
            "document_chunks",
            {"corpus_version_id": f"eq.{corpus_id}", "select": chunk_fields},
        )
        page_ids = sorted({str(chunk["wiki_page_id"]) for chunk in chunks})
        pages = self._get_by_ids("wiki_pages", page_ids)
        attributions = self._get_by_foreign_ids("source_attributions", "wiki_page_id", page_ids)
        aliases = self._get_all("entity_aliases", {"select": "*", "order": "id.asc"})
        return SnapshotRecords(
            corpus=corpus,
            embedding_model=model_rows[0],
            pages=tuple(pages),
            attributions=tuple(attributions),
            aliases=tuple(aliases),
            chunks=tuple(chunks),
        )

    def store_snapshot(
        self,
        version: str,
        *,
        object_bytes: bytes,
        manifest_bytes: bytes,
        manifest: dict[str, object],
    ) -> None:
        """Upload deterministic objects and attach their manifest to the corpus row."""
        object_path = f"corpus/{version}/chunks.jsonl.gz"
        manifest_path = f"corpus/{version}/manifest.json"
        self._upload(object_path, object_bytes, "application/gzip")
        self._upload(manifest_path, manifest_bytes, "application/json")
        rows = self._get_rows(
            "corpus_versions",
            {"version": f"eq.{version}", "select": "manifest", "limit": "1"},
        )
        if not rows:
            raise SnapshotError("Snapshot corpus disappeared before manifest update")
        existing = rows[0].get("manifest")
        current = existing if isinstance(existing, dict) else {}
        response = self._client.patch(
            f"{self.base_url}/rest/v1/corpus_versions",
            headers=self._database_headers(write=True),
            params={"version": f"eq.{version}"},
            json={"manifest": {**current, "snapshot": manifest}},
        )
        self._raise_for_status(response, "record snapshot manifest")

    def _upload(self, path: str, content: bytes, content_type: str) -> None:
        encoded = "/".join(quote(part, safe="") for part in path.split("/"))
        response = self._client.post(
            f"{self.base_url}/storage/v1/object/{self.bucket}/{encoded}",
            headers={**self._auth_headers, "Content-Type": content_type, "x-upsert": "true"},
            content=content,
        )
        self._raise_for_status(response, f"upload snapshot object {path}")

    def _get_all(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self._get_rows(table, {**params, "limit": "500", "offset": str(offset)})
            rows.extend(page)
            if len(page) < 500:
                return rows
            offset += len(page)

    def _get_by_ids(self, table: str, ids: Sequence[str]) -> list[dict[str, Any]]:
        return self._get_by_foreign_ids(table, "id", ids)

    def _get_by_foreign_ids(
        self,
        table: str,
        field: str,
        ids: Sequence[str],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for offset in range(0, len(ids), 100):
            batch = ids[offset : offset + 100]
            if not batch:
                continue
            rows.extend(
                self._get_all(
                    table,
                    {field: f"in.({','.join(batch)})", "select": "*", "order": "id.asc"},
                )
            )
        return rows

    def _get_rows(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        response = self._client.get(
            f"{self.base_url}/rest/v1/{table}",
            headers=self._database_headers(),
            params=params,
        )
        self._raise_for_status(response, f"load {table}")
        payload = response.json()
        if not isinstance(payload, list):
            raise SnapshotError(f"Supabase {table} response is not a list")
        return [row for row in payload if isinstance(row, dict)]

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
