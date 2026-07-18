"""Backend-only Supabase adapter for active-corpus hybrid retrieval."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from src.retrieval import ActiveCorpus, HybridCandidate


class SupabaseRetrievalError(RuntimeError):
    """Raised when active-corpus lookup or hybrid RPC execution fails."""


class SupabaseRetrievalRepository:
    """Call the protected hybrid RPC and parse its evidence-rich rows."""

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

    def __enter__(self) -> SupabaseRetrievalRepository:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the internally owned HTTP client."""
        if self._owns_client:
            self._client.close()

    def get_active_corpus(self) -> ActiveCorpus:
        """Return the sole active corpus or fail closed."""
        response = self._client.get(
            f"{self.base_url}/rest/v1/corpus_versions",
            headers={**self._auth_headers, "Accept-Profile": "knowledge"},
            params={
                "status": "eq.active",
                "select": "id,version,embedding_model_key",
                "limit": "2",
            },
        )
        rows = self._rows(response, "find active corpus", allow_empty=True)
        if not rows:
            raise SupabaseRetrievalError("No active corpus is available for retrieval")
        if len(rows) != 1:
            raise SupabaseRetrievalError("Multiple active corpora violate the retrieval contract")
        row = rows[0]
        return ActiveCorpus(
            id=str(row["id"]),
            version=str(row["version"]),
            embedding_model_key=str(row["embedding_model_key"]),
        )

    def hybrid_search(
        self,
        *,
        query_text: str,
        query_embedding: Sequence[float],
        match_count: int,
        lexical_count: int,
        semantic_count: int,
        filter_entity_type: str | None,
        entity_titles: Sequence[str],
        section_intent: str | None,
    ) -> list[HybridCandidate]:
        """Execute FTS/vector RRF with active-corpus and DST filters inside PostgreSQL."""
        response = self._client.post(
            f"{self.base_url}/rest/v1/rpc/hybrid_search_dst",
            headers={**self._auth_headers, "Content-Type": "application/json"},
            json={
                "p_query_text": query_text,
                "p_query_embedding": list(query_embedding),
                "p_match_count": match_count,
                "p_lexical_count": lexical_count,
                "p_semantic_count": semantic_count,
                "p_filter_entity_type": filter_entity_type,
                "p_entity_titles": list(entity_titles) or None,
                "p_section_intent": section_intent,
                "p_rrf_k": 60,
            },
        )
        rows = self._rows(response, "run hybrid retrieval", allow_empty=True)
        return [self._candidate(row) for row in rows]

    @staticmethod
    def _candidate(row: dict[str, Any]) -> HybridCandidate:
        metadata = row.get("metadata")
        lexical_rank = row.get("lexical_rank")
        semantic_rank = row.get("semantic_rank")
        similarity = row.get("cosine_similarity")
        entity_type = row.get("entity_type")
        return HybridCandidate(
            chunk_id=str(row["chunk_id"]),
            corpus_version_id=str(row["corpus_version_id"]),
            page_title=str(row["page_title"]),
            section_path=str(row["section_path"]),
            content=str(row["content"]),
            content_hash=str(row["content_hash"]),
            token_count=int(row["token_count"]),
            game_scope=str(row["game_scope"]),
            entity_type=str(entity_type) if entity_type is not None else None,
            source_kind=str(row["source_kind"]),
            subjective=bool(row["subjective"]),
            canonical_url=str(row["canonical_url"]),
            revision_id=int(row["revision_id"]),
            metadata=metadata if isinstance(metadata, dict) else {},
            lexical_rank=int(lexical_rank) if lexical_rank is not None else None,
            semantic_rank=int(semantic_rank) if semantic_rank is not None else None,
            cosine_similarity=float(similarity) if similarity is not None else None,
            rrf_score=float(row["rrf_score"]),
        )

    @classmethod
    def _rows(
        cls,
        response: httpx.Response,
        operation: str,
        *,
        allow_empty: bool = False,
    ) -> list[dict[str, Any]]:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SupabaseRetrievalError(
                f"Supabase could not {operation} (HTTP {response.status_code})"
            ) from exc
        payload = response.json()
        if not isinstance(payload, list):
            raise SupabaseRetrievalError(f"Supabase {operation} returned a non-list response")
        rows = [row for row in payload if isinstance(row, dict)]
        if not rows and not allow_empty:
            raise SupabaseRetrievalError(f"Supabase {operation} returned no rows")
        return rows
