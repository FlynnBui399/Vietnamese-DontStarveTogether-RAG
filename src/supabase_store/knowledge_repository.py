"""Backend-only public knowledge reads for status, entities, and source evidence."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

import httpx

from src.terminology.normalizer import normalize_search_text


class SupabaseKnowledgeError(RuntimeError):
    """Raised when a public knowledge read cannot be completed safely."""


@dataclass(frozen=True, slots=True)
class PublicCorpusStatus:
    """Non-secret active-corpus information displayed by the web app."""

    available: bool
    version: str | None
    page_count: int
    chunk_count: int
    embedding_model: str | None
    activated_at: str | None
    last_sync_at: str | None


@dataclass(frozen=True, slots=True)
class EntitySearchResult:
    """One distinct entity autocomplete result."""

    title: str
    slug: str
    matched_alias: str
    alias_type: str
    verified: bool
    score: float


@dataclass(frozen=True, slots=True)
class EntityDetail:
    """Active-corpus entity summary and its stored aliases."""

    title: str
    slug: str
    entity_type: str | None
    summary: str
    aliases: tuple[str, ...]
    source_chunk_id: str
    source_url: str
    corpus_version: str


@dataclass(frozen=True, slots=True)
class SourceDetail:
    """Exact active or archived evidence returned to a source drawer."""

    chunk_id: str
    page_title: str
    section: str
    content: str
    url: str
    revision_id: int
    source_kind: str
    subjective: bool
    corpus_version: str
    corpus_status: str


class SupabaseKnowledgeRepository:
    """Read public-safe records using only a backend credential."""

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
        self._headers = {
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
            "Accept-Profile": "knowledge",
        }

    def close(self) -> None:
        """Close the internally owned HTTP client."""
        if self._owns_client:
            self._client.close()

    def get_corpus_status(self) -> PublicCorpusStatus:
        """Return the sole active corpus and latest successful sync timestamp."""
        active_rows = self._get_rows(
            "corpus_versions",
            {
                "status": "eq.active",
                "select": "id,version,page_count,chunk_count,embedding_model_key,activated_at",
                "limit": "2",
            },
            "load active corpus status",
        )
        if len(active_rows) > 1:
            raise SupabaseKnowledgeError("Multiple active corpora violate the status contract")
        sync_rows = self._get_rows(
            "sync_runs",
            {
                "status": "eq.succeeded",
                "select": "finished_at",
                "order": "finished_at.desc.nullslast",
                "limit": "1",
            },
            "load latest sync status",
        )
        last_sync = sync_rows[0].get("finished_at") if sync_rows else None
        if not active_rows:
            return PublicCorpusStatus(
                available=False,
                version=None,
                page_count=0,
                chunk_count=0,
                embedding_model=None,
                activated_at=None,
                last_sync_at=str(last_sync) if last_sync else None,
            )
        row = active_rows[0]
        activated_at = row.get("activated_at")
        return PublicCorpusStatus(
            available=True,
            version=str(row["version"]),
            page_count=int(row["page_count"]),
            chunk_count=int(row["chunk_count"]),
            embedding_model=str(row["embedding_model_key"]),
            activated_at=str(activated_at) if activated_at else None,
            last_sync_at=str(last_sync) if last_sync else None,
        )

    def search_entities(self, query: str, *, limit: int = 8) -> tuple[EntitySearchResult, ...]:
        """Rank stored aliases locally and return distinct canonical entities."""
        normalized = normalize_search_text(query)
        if not normalized:
            return ()
        rows = self._get_rows(
            "entity_aliases",
            {
                "select": (
                    "entity_title,entity_slug,alias,alias_normalized,alias_type,"
                    "priority,confidence,verified"
                ),
                "order": "priority.desc,alias_normalized.asc",
                "limit": "1000",
            },
            "search entity aliases",
        )
        ranked: list[EntitySearchResult] = []
        for row in rows:
            alias_normalized = str(row["alias_normalized"])
            similarity = SequenceMatcher(None, normalized, alias_normalized).ratio()
            contains = normalized in alias_normalized or alias_normalized in normalized
            if not contains and similarity < 0.55:
                continue
            exact = normalized == alias_normalized
            verified = bool(row["verified"])
            score = (
                (1000.0 if exact else 500.0 if contains else 0.0)
                + (100.0 if verified else 0.0)
                + float(row["priority"])
                + similarity
            )
            ranked.append(
                EntitySearchResult(
                    title=str(row["entity_title"]),
                    slug=str(row.get("entity_slug") or ""),
                    matched_alias=str(row["alias"]),
                    alias_type=str(row["alias_type"]),
                    verified=verified,
                    score=score,
                )
            )
        ranked.sort(key=lambda result: (result.score, result.title.casefold()), reverse=True)
        distinct: list[EntitySearchResult] = []
        seen: set[str] = set()
        for result in ranked:
            key = result.title.casefold()
            if key in seen:
                continue
            seen.add(key)
            distinct.append(result)
            if len(distinct) == limit:
                break
        return tuple(distinct)

    def get_entity(self, slug: str) -> EntityDetail | None:
        """Return an entity only when it has evidence in the active corpus."""
        alias_rows = self._get_rows(
            "entity_aliases",
            {
                "entity_slug": f"eq.{slug}",
                "select": "entity_title,entity_slug,alias,priority",
                "order": "priority.desc,alias.asc",
                "limit": "100",
            },
            "load entity aliases",
        )
        if not alias_rows:
            return None
        status = self.get_corpus_status()
        if not status.available or status.version is None:
            return None
        title = str(alias_rows[0]["entity_title"])
        corpus_rows = self._get_rows(
            "corpus_versions",
            {"status": "eq.active", "select": "id", "limit": "1"},
            "load active corpus",
        )
        corpus_id = str(corpus_rows[0]["id"])
        chunk_rows = self._get_rows(
            "document_chunks",
            {
                "corpus_version_id": f"eq.{corpus_id}",
                "page_title": f"eq.{title}",
                "select": "id,content,entity_type,canonical_url,chunk_index",
                "order": "chunk_index.asc",
                "limit": "1",
            },
            "load entity evidence",
        )
        if not chunk_rows:
            return None
        chunk = chunk_rows[0]
        entity_type = chunk.get("entity_type")
        aliases = tuple(dict.fromkeys(str(row["alias"]) for row in alias_rows))
        return EntityDetail(
            title=title,
            slug=str(alias_rows[0].get("entity_slug") or slug),
            entity_type=str(entity_type) if entity_type is not None else None,
            summary=str(chunk["content"]),
            aliases=aliases,
            source_chunk_id=str(chunk["id"]),
            source_url=str(chunk["canonical_url"]),
            corpus_version=status.version,
        )

    def get_source(self, chunk_id: str) -> SourceDetail | None:
        """Return exact evidence only from an active or archived corpus version."""
        chunk_rows = self._get_rows(
            "document_chunks",
            {
                "id": f"eq.{chunk_id}",
                "select": (
                    "id,corpus_version_id,page_title,section_path,content,canonical_url,"
                    "revision_id,source_kind,subjective"
                ),
                "limit": "1",
            },
            "load source evidence",
        )
        if not chunk_rows:
            return None
        chunk = chunk_rows[0]
        corpus_rows = self._get_rows(
            "corpus_versions",
            {
                "id": f"eq.{chunk['corpus_version_id']}",
                "status": "in.(active,archived)",
                "select": "version,status",
                "limit": "1",
            },
            "validate source corpus",
        )
        if not corpus_rows:
            return None
        corpus = corpus_rows[0]
        return SourceDetail(
            chunk_id=str(chunk["id"]),
            page_title=str(chunk["page_title"]),
            section=str(chunk["section_path"]),
            content=str(chunk["content"]),
            url=str(chunk["canonical_url"]),
            revision_id=int(chunk["revision_id"]),
            source_kind=str(chunk["source_kind"]),
            subjective=bool(chunk["subjective"]),
            corpus_version=str(corpus["version"]),
            corpus_status=str(corpus["status"]),
        )

    def _get_rows(
        self,
        table: str,
        params: dict[str, str],
        operation: str,
    ) -> list[dict[str, Any]]:
        response = self._client.get(
            f"{self.base_url}/rest/v1/{table}",
            headers=self._headers,
            params=params,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SupabaseKnowledgeError(
                f"Supabase could not {operation} (HTTP {response.status_code})"
            ) from exc
        payload = response.json()
        if not isinstance(payload, list):
            raise SupabaseKnowledgeError(f"Supabase {operation} returned a non-list response")
        return [row for row in payload if isinstance(row, dict)]
