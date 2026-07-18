"""Backend-only Supabase persistence for corpus processing and chunk insertion."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import quote

import httpx

from src.processing.models import (
    ChunkDraft,
    GameScope,
    PageClassification,
    SourcePage,
    ValidationReport,
)

VALID_GAME_SCOPES = {
    "dst",
    "dont_starve",
    "reign_of_giants",
    "shipwrecked",
    "hamlet",
    "mixed",
    "unknown",
}


class SupabaseProcessingError(RuntimeError):
    """Raised when a corpus processing read or write fails."""


class SupabaseProcessingRepository:
    """Read raw revisions and persist a non-active, validated processing corpus."""

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

    def __enter__(self) -> SupabaseProcessingRepository:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the internally owned HTTP client."""
        if self._owns_client:
            self._client.close()

    def create_or_reset_corpus(
        self,
        *,
        version: str,
        embedding_model_key: str,
        embedding_dimensions: int,
    ) -> str:
        """Create a building corpus or safely reset the same non-active version."""
        self._ensure_pending_embedding_model(embedding_model_key, embedding_dimensions)
        response = self._client.get(
            f"{self.base_url}/rest/v1/corpus_versions",
            headers=self._database_headers(),
            params={"version": f"eq.{version}", "select": "id,status", "limit": "1"},
        )
        rows = self._rows(response, "find corpus version", allow_empty=True)
        if rows:
            corpus_id = str(rows[0]["id"])
            status = str(rows[0]["status"])
            if status in {"active", "archived"}:
                raise SupabaseProcessingError(
                    f"Corpus {version} is {status} and cannot be rebuilt in place"
                )
            delete_response = self._client.delete(
                f"{self.base_url}/rest/v1/document_chunks",
                headers=self._database_headers(write=True),
                params={"corpus_version_id": f"eq.{corpus_id}"},
            )
            self._raise_for_status(delete_response, "clear prior building chunks")
            reset_response = self._client.patch(
                f"{self.base_url}/rest/v1/corpus_versions",
                headers=self._database_headers(write=True),
                params={"id": f"eq.{corpus_id}"},
                json={
                    "status": "building",
                    "embedding_model_key": embedding_model_key,
                    "page_count": 0,
                    "chunk_count": 0,
                    "source_revision_max": None,
                    "completed_at": None,
                    "activated_at": None,
                    "manifest": {"processing_status": "building"},
                },
            )
            self._raise_for_status(reset_response, "reset corpus version")
            return corpus_id

        create_response = self._client.post(
            f"{self.base_url}/rest/v1/corpus_versions",
            headers=self._database_headers(write=True, representation=True),
            json={
                "version": version,
                "status": "building",
                "embedding_model_key": embedding_model_key,
                "manifest": {"processing_status": "building"},
            },
        )
        created = self._rows(create_response, "create corpus version")
        return str(created[0]["id"])

    def list_source_pages(self) -> list[SourcePage]:
        """Return current raw wiki revisions eligible for processing."""
        response = self._client.get(
            f"{self.base_url}/rest/v1/wiki_pages",
            headers=self._database_headers(),
            params={
                "is_active": "eq.true",
                "raw_storage_path": "not.is.null",
                "select": (
                    "id,mediawiki_page_id,title,canonical_url,revision_id,revision_timestamp,"
                    "game_scope,raw_storage_bucket,raw_storage_path,metadata"
                ),
                "order": "mediawiki_page_id.asc",
            },
        )
        rows = self._rows(response, "list raw source pages", allow_empty=True)
        pages: list[SourcePage] = []
        for row in rows:
            scope = str(row["game_scope"])
            if scope not in VALID_GAME_SCOPES:
                raise SupabaseProcessingError(f"Unsupported stored game scope: {scope}")
            metadata = row.get("metadata")
            pages.append(
                SourcePage(
                    id=str(row["id"]),
                    mediawiki_page_id=int(row["mediawiki_page_id"]),
                    title=str(row["title"]),
                    canonical_url=str(row["canonical_url"]),
                    revision_id=int(row["revision_id"]),
                    revision_timestamp=(
                        str(row["revision_timestamp"])
                        if row.get("revision_timestamp") is not None
                        else None
                    ),
                    preliminary_game_scope=cast(GameScope, scope),
                    raw_storage_bucket=str(row["raw_storage_bucket"]),
                    raw_storage_path=str(row["raw_storage_path"]),
                    metadata=metadata if isinstance(metadata, dict) else {},
                )
            )
        return pages

    def download_wikitext(self, page: SourcePage) -> str:
        """Download and validate the private raw snapshot for one selected revision."""
        encoded_path = "/".join(quote(part, safe="") for part in page.raw_storage_path.split("/"))
        response = self._client.get(
            f"{self.base_url}/storage/v1/object/{page.raw_storage_bucket}/{encoded_path}",
            headers=self._auth_headers,
        )
        self._raise_for_status(response, "download raw wiki snapshot")
        payload = response.json()
        if not isinstance(payload, dict):
            raise SupabaseProcessingError("Raw snapshot is not a JSON object")
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            raise SupabaseProcessingError("Raw snapshot has no metadata object")
        if (
            int(metadata.get("page_id", -1)) != page.mediawiki_page_id
            or int(metadata.get("revision_id", -1)) != page.revision_id
        ):
            raise SupabaseProcessingError("Raw snapshot identity does not match wiki_pages")
        try:
            raw_pages = payload["response"]["query"]["pages"]
            raw_page = raw_pages[0]
            revision = raw_page["revisions"][0]
            content = revision["slots"]["main"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise SupabaseProcessingError("Raw snapshot has no main revision content") from exc
        if not isinstance(content, str) or not content.strip():
            raise SupabaseProcessingError("Raw snapshot revision content is empty")
        return content

    def update_page_classification(
        self,
        page: SourcePage,
        classification: PageClassification,
    ) -> None:
        """Persist page-level labels and the rule evidence that produced them."""
        metadata = {
            **page.metadata,
            "classification": {
                "scope_reason": classification.scope_reason,
                "entity_reason": classification.entity_reason,
                "source_reason": classification.source_reason,
                "classified_at": datetime.now(UTC).isoformat(),
            },
        }
        response = self._client.patch(
            f"{self.base_url}/rest/v1/wiki_pages",
            headers=self._database_headers(write=True),
            params={"id": f"eq.{page.id}"},
            json={
                "game_scope": classification.game_scope,
                "entity_type": classification.entity_type,
                "source_kind": classification.source_kind,
                "metadata": metadata,
            },
        )
        self._raise_for_status(response, "update page classification")

    def insert_chunks(self, corpus_id: str, chunks: Sequence[ChunkDraft]) -> None:
        """Insert validated chunks in bounded PostgREST batches."""
        for offset in range(0, len(chunks), 100):
            rows = [self._chunk_row(corpus_id, chunk) for chunk in chunks[offset : offset + 100]]
            response = self._client.post(
                f"{self.base_url}/rest/v1/document_chunks",
                headers=self._database_headers(write=True, merge=True),
                params={"on_conflict": "corpus_version_id,source_key"},
                json=rows,
            )
            self._raise_for_status(response, "insert document chunks")

    def finish_processing(
        self,
        corpus_id: str,
        *,
        page_count: int,
        source_revision_max: int,
        validation: ValidationReport,
        classification_counts: dict[str, int],
    ) -> None:
        """Keep the corpus building while recording successful processing validation."""
        response = self._client.patch(
            f"{self.base_url}/rest/v1/corpus_versions",
            headers=self._database_headers(write=True),
            params={"id": f"eq.{corpus_id}"},
            json={
                "status": "building",
                "page_count": page_count,
                "chunk_count": validation.valid_chunk_count,
                "source_revision_max": source_revision_max,
                "manifest": {
                    "processing_status": "passed",
                    "embedding_status": "pending",
                    "validation": validation.to_dict(),
                    "classification_counts": classification_counts,
                    "parser": "mwparserfromhell-0.7.2",
                },
            },
        )
        self._raise_for_status(response, "finish corpus processing")

    def mark_corpus_failed(
        self,
        corpus_id: str,
        *,
        errors: Sequence[str],
        validation: ValidationReport | None,
    ) -> None:
        """Mark an incomplete non-active corpus failed with honest error details."""
        response = self._client.patch(
            f"{self.base_url}/rest/v1/corpus_versions",
            headers=self._database_headers(write=True),
            params={"id": f"eq.{corpus_id}"},
            json={
                "status": "failed",
                "completed_at": datetime.now(UTC).isoformat(),
                "manifest": {
                    "processing_status": "failed",
                    "errors": list(errors),
                    "validation": validation.to_dict() if validation is not None else None,
                },
            },
        )
        self._raise_for_status(response, "mark corpus failed")

    def _ensure_pending_embedding_model(self, model_key: str, dimensions: int) -> None:
        response = self._client.post(
            f"{self.base_url}/rest/v1/embedding_models",
            headers=self._database_headers(write=True, merge=True),
            params={"on_conflict": "model_key"},
            json={
                "model_key": model_key,
                "provider": "pending",
                "model_name": "unassigned-until-milestone-5",
                "model_revision": "milestone-3",
                "dimensions": dimensions,
                "distance_metric": "cosine",
                "normalized": True,
                "batch_size": 32,
                "is_active": False,
            },
        )
        self._raise_for_status(response, "ensure pending embedding model")

    @staticmethod
    def _chunk_row(corpus_id: str, chunk: ChunkDraft) -> dict[str, object]:
        return {
            "corpus_version_id": corpus_id,
            "wiki_page_id": chunk.wiki_page_id,
            "source_key": chunk.source_key,
            "page_title": chunk.page_title,
            "section_path": chunk.section_path,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "content_normalized": chunk.content_normalized,
            "content_hash": chunk.content_hash,
            "token_count": chunk.token_count,
            "game_scope": chunk.game_scope,
            "entity_type": chunk.entity_type,
            "source_kind": chunk.source_kind,
            "subjective": chunk.subjective,
            "canonical_url": chunk.canonical_url,
            "revision_id": chunk.revision_id,
            "search_text": chunk.search_text,
            "embedding": None,
            "metadata": chunk.metadata,
        }

    def _database_headers(
        self,
        *,
        write: bool = False,
        representation: bool = False,
        merge: bool = False,
    ) -> dict[str, str]:
        profile_header = "Content-Profile" if write else "Accept-Profile"
        preferences: list[str] = []
        if representation:
            preferences.append("return=representation")
        if merge:
            preferences.append("resolution=merge-duplicates")
        headers = {**self._auth_headers, profile_header: "knowledge"}
        if preferences:
            headers["Prefer"] = ",".join(preferences)
        return headers

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
            raise SupabaseProcessingError(f"Supabase {operation} returned a non-list response")
        rows = [row for row in payload if isinstance(row, dict)]
        if not rows and not allow_empty:
            raise SupabaseProcessingError(f"Supabase {operation} returned no rows")
        return rows

    @staticmethod
    def _raise_for_status(response: httpx.Response, operation: str) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SupabaseProcessingError(
                f"Supabase could not {operation} (HTTP {response.status_code})"
            ) from exc
