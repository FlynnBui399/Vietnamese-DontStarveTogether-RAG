"""Backend-only Supabase persistence for resumable embedding runs."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import httpx

from src.embeddings.models import (
    EmbeddingChunk,
    EmbeddingModelManifest,
    EmbeddingPreparation,
    EmbeddingRunReport,
)


class SupabaseEmbeddingError(RuntimeError):
    """Raised when embedding persistence violates the corpus/model contract."""


class SupabaseEmbeddingRepository:
    """Persist model manifests, vectors, and honest per-chunk embedding state."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._auth_headers = {
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
        }

    def __enter__(self) -> SupabaseEmbeddingRepository:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the internally owned HTTP client."""
        if self._owns_client:
            self._client.close()

    def prepare_run(
        self,
        corpus_version: str,
        manifest: EmbeddingModelManifest,
    ) -> EmbeddingPreparation:
        """Validate model/corpus identity and return only chunks still missing vectors."""
        self._ensure_model(manifest)
        response = self._client.get(
            f"{self.base_url}/rest/v1/corpus_versions",
            headers=self._database_headers(),
            params={
                "version": f"eq.{corpus_version}",
                "select": "id,status,manifest",
                "limit": "1",
            },
        )
        rows = self._rows(response, "find embedding corpus")
        corpus = rows[0]
        status = str(corpus["status"])
        if status in {"active", "archived"}:
            raise SupabaseEmbeddingError(
                f"Corpus {corpus_version} is {status} and cannot be embedded in place"
            )
        corpus_id = str(corpus["id"])
        existing_manifest = corpus.get("manifest")
        manifest_data = existing_manifest if isinstance(existing_manifest, dict) else {}
        update_response = self._client.patch(
            f"{self.base_url}/rest/v1/corpus_versions",
            headers=self._database_headers(write=True),
            params={"id": f"eq.{corpus_id}"},
            json={
                "status": "building",
                "embedding_model_key": manifest.model_key,
                "completed_at": None,
                "manifest": {
                    **manifest_data,
                    "embedding_status": "running",
                    "embedding_model": manifest.to_dict(),
                },
            },
        )
        self._raise_for_status(update_response, "start embedding run")
        total_chunk_count = self._chunk_count(corpus_id)
        if total_chunk_count == 0:
            raise SupabaseEmbeddingError("Embedding corpus contains no chunks")
        pending_chunks = self._pending_chunks(corpus_id)
        return EmbeddingPreparation(
            corpus_id=corpus_id,
            total_chunk_count=total_chunk_count,
            already_embedded_count=total_chunk_count - len(pending_chunks),
            pending_chunks=tuple(pending_chunks),
        )

    def store_embedding(
        self,
        chunk: EmbeddingChunk,
        vector: Sequence[float],
        model_key: str,
    ) -> None:
        """Store one validated vector and its success provenance."""
        metadata = {
            **chunk.metadata,
            "embedding": {
                "status": "succeeded",
                "model_key": model_key,
                "embedded_at": datetime.now(UTC).isoformat(),
            },
        }
        response = self._client.patch(
            f"{self.base_url}/rest/v1/document_chunks",
            headers=self._database_headers(write=True),
            params={"id": f"eq.{chunk.id}"},
            json={"embedding": list(vector), "metadata": metadata},
        )
        self._raise_for_status(response, "store chunk embedding")

    def record_embedding_error(
        self,
        chunk: EmbeddingChunk,
        error: str,
        model_key: str,
    ) -> None:
        """Record why one candidate has no embedding so failures are never silent."""
        metadata = {
            **chunk.metadata,
            "embedding": {
                "status": "failed",
                "model_key": model_key,
                "error": error,
                "attempted_at": datetime.now(UTC).isoformat(),
            },
        }
        response = self._client.patch(
            f"{self.base_url}/rest/v1/document_chunks",
            headers=self._database_headers(write=True),
            params={"id": f"eq.{chunk.id}"},
            json={"embedding": None, "metadata": metadata},
        )
        self._raise_for_status(response, "record chunk embedding error")

    def finish_run(self, report: EmbeddingRunReport) -> None:
        """Advance only a complete run to validating; partial runs remain building."""
        response = self._client.get(
            f"{self.base_url}/rest/v1/corpus_versions",
            headers=self._database_headers(),
            params={"id": f"eq.{report.corpus_id}", "select": "manifest", "limit": "1"},
        )
        rows = self._rows(response, "reload embedding corpus")
        existing_manifest = rows[0].get("manifest")
        manifest_data = existing_manifest if isinstance(existing_manifest, dict) else {}
        update_response = self._client.patch(
            f"{self.base_url}/rest/v1/corpus_versions",
            headers=self._database_headers(write=True),
            params={"id": f"eq.{report.corpus_id}"},
            json={
                "status": "validating" if report.status == "passed" else "building",
                "completed_at": datetime.now(UTC).isoformat()
                if report.status == "passed"
                else None,
                "manifest": {
                    **manifest_data,
                    "embedding_status": report.status,
                    "embedding_run": report.to_dict(),
                },
            },
        )
        self._raise_for_status(update_response, "finish embedding run")

    def semantic_search(
        self,
        corpus_id: str,
        query_embedding: Sequence[float],
        *,
        match_count: int = 5,
    ) -> list[dict[str, Any]]:
        """Run the protected semantic diagnostic RPC."""
        return self._rpc(
            "semantic_search_dst",
            {
                "p_corpus_version": corpus_id,
                "p_query_embedding": list(query_embedding),
                "p_match_count": match_count,
            },
        )

    def lexical_search(
        self,
        corpus_id: str,
        query_text: str,
        *,
        match_count: int = 5,
    ) -> list[dict[str, Any]]:
        """Run the protected FTS diagnostic RPC."""
        return self._rpc(
            "lexical_search_dst",
            {
                "p_corpus_version": corpus_id,
                "p_query_text": query_text,
                "p_match_count": match_count,
            },
        )

    def _ensure_model(self, manifest: EmbeddingModelManifest) -> None:
        response = self._client.get(
            f"{self.base_url}/rest/v1/embedding_models",
            headers=self._database_headers(),
            params={
                "model_key": f"eq.{manifest.model_key}",
                "select": (
                    "provider,model_name,model_revision,dimensions,distance_metric,normalized"
                ),
                "limit": "1",
            },
        )
        rows = self._rows(response, "find embedding model", allow_empty=True)
        expected = {
            "provider": manifest.provider,
            "model_name": manifest.model_name,
            "model_revision": manifest.model_revision,
            "dimensions": manifest.dimensions,
            "distance_metric": manifest.distance_metric,
            "normalized": manifest.normalized,
        }
        if rows:
            actual = {key: rows[0].get(key) for key in expected}
            if actual != expected:
                raise SupabaseEmbeddingError(
                    f"Embedding model key {manifest.model_key} already has a different contract"
                )
            return
        create_response = self._client.post(
            f"{self.base_url}/rest/v1/embedding_models",
            headers=self._database_headers(write=True),
            json={**manifest.to_dict(), "is_active": False},
        )
        self._raise_for_status(create_response, "create embedding model manifest")

    def _chunk_count(self, corpus_id: str) -> int:
        response = self._client.get(
            f"{self.base_url}/rest/v1/document_chunks",
            headers={
                **self._database_headers(),
                "Range": "0-0",
                "Prefer": "count=exact",
            },
            params={"corpus_version_id": f"eq.{corpus_id}", "select": "id"},
        )
        self._raise_for_status(response, "count embedding chunks")
        content_range = response.headers.get("content-range", "")
        try:
            return int(content_range.rsplit("/", 1)[1])
        except (IndexError, ValueError) as exc:
            raise SupabaseEmbeddingError("Supabase chunk count has no total range") from exc

    def _pending_chunks(self, corpus_id: str) -> list[EmbeddingChunk]:
        chunks: list[EmbeddingChunk] = []
        offset = 0
        while True:
            response = self._client.get(
                f"{self.base_url}/rest/v1/document_chunks",
                headers=self._database_headers(),
                params={
                    "corpus_version_id": f"eq.{corpus_id}",
                    "embedding": "is.null",
                    "select": "id,content,metadata",
                    "order": "id.asc",
                    "limit": "500",
                    "offset": str(offset),
                },
            )
            rows = self._rows(response, "list pending embedding chunks", allow_empty=True)
            for row in rows:
                metadata = row.get("metadata")
                chunks.append(
                    EmbeddingChunk(
                        id=str(row["id"]),
                        content=str(row["content"]),
                        metadata=metadata if isinstance(metadata, dict) else {},
                    )
                )
            if len(rows) < 500:
                break
            offset += len(rows)
        return chunks

    def _rpc(self, function: str, payload: dict[str, object]) -> list[dict[str, Any]]:
        response = self._client.post(
            f"{self.base_url}/rest/v1/rpc/{function}",
            headers={**self._auth_headers, "Content-Type": "application/json"},
            json=payload,
        )
        return self._rows(response, f"call {function}", allow_empty=True)

    def _database_headers(self, *, write: bool = False) -> dict[str, str]:
        profile_header = "Content-Profile" if write else "Accept-Profile"
        return {**self._auth_headers, profile_header: "knowledge"}

    @classmethod
    def _rows(
        cls,
        response: httpx.Response,
        operation: str,
        *,
        allow_empty: bool = False,
    ) -> list[dict[str, Any]]:
        cls._raise_for_status(response, operation)
        payload = response.json()
        if not isinstance(payload, list):
            raise SupabaseEmbeddingError(f"Supabase {operation} returned a non-list response")
        rows = [row for row in payload if isinstance(row, dict)]
        if not rows and not allow_empty:
            raise SupabaseEmbeddingError(f"Supabase {operation} returned no rows")
        return rows

    @staticmethod
    def _raise_for_status(response: httpx.Response, operation: str) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SupabaseEmbeddingError(
                f"Supabase could not {operation} (HTTP {response.status_code})"
            ) from exc
