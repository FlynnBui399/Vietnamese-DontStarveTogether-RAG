"""Backend-only Supabase persistence for terminology aliases."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

import httpx

from src.terminology.models import AliasRecord, AliasType

VALID_ALIAS_TYPES = {
    "official_title",
    "official_translation",
    "community_translation",
    "abbreviation",
    "common_misspelling",
    "descriptive_alias",
    "generated_candidate",
}


class SupabaseAliasError(RuntimeError):
    """Raised when alias persistence or retrieval fails."""


class SupabaseAliasRepository:
    """Synchronize and read aliases through the protected knowledge schema."""

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

    def __enter__(self) -> SupabaseAliasRepository:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the internally owned HTTP client."""
        if self._owns_client:
            self._client.close()

    def sync_aliases(self, aliases: Sequence[AliasRecord]) -> int:
        """Idempotently upsert every glossary alias by entity and normalized value."""
        for offset in range(0, len(aliases), 100):
            rows = [self._to_row(alias) for alias in aliases[offset : offset + 100]]
            response = self._client.post(
                f"{self.base_url}/rest/v1/entity_aliases",
                headers={
                    **self._auth_headers,
                    "Content-Profile": "knowledge",
                    "Prefer": "resolution=merge-duplicates",
                },
                params={"on_conflict": "entity_title,alias_normalized"},
                json=rows,
            )
            self._raise_for_status(response, "synchronize entity aliases")
        return len(aliases)

    def list_aliases(self) -> tuple[AliasRecord, ...]:
        """Return stored aliases in deterministic resolver order."""
        response = self._client.get(
            f"{self.base_url}/rest/v1/entity_aliases",
            headers={**self._auth_headers, "Accept-Profile": "knowledge"},
            params={
                "select": (
                    "entity_title,entity_slug,alias,alias_normalized,language,alias_type,"
                    "priority,confidence,verified,source,metadata"
                ),
                "order": "entity_title.asc,priority.desc,alias_normalized.asc",
                "limit": "1000",
            },
        )
        self._raise_for_status(response, "list entity aliases")
        payload = response.json()
        if not isinstance(payload, list):
            raise SupabaseAliasError("Supabase alias list returned a non-list response")
        return tuple(self._from_row(row) for row in payload if isinstance(row, dict))

    @staticmethod
    def _to_row(alias: AliasRecord) -> dict[str, object]:
        return {
            "entity_title": alias.entity_title,
            "entity_slug": alias.entity_slug,
            "alias": alias.alias,
            "alias_normalized": alias.alias_normalized,
            "language": alias.language,
            "alias_type": alias.alias_type,
            "priority": alias.priority,
            "confidence": alias.confidence,
            "verified": alias.verified,
            "source": alias.source,
            "metadata": alias.metadata,
        }

    @staticmethod
    def _from_row(row: dict[str, Any]) -> AliasRecord:
        alias_type = str(row["alias_type"])
        if alias_type not in VALID_ALIAS_TYPES:
            raise SupabaseAliasError(f"Unsupported stored alias type: {alias_type}")
        metadata = row.get("metadata")
        confidence = row.get("confidence")
        return AliasRecord(
            entity_title=str(row["entity_title"]),
            entity_slug=str(row.get("entity_slug") or ""),
            alias=str(row["alias"]),
            alias_normalized=str(row["alias_normalized"]),
            language=str(row["language"]),
            alias_type=cast(AliasType, alias_type),
            priority=int(row["priority"]),
            confidence=float(confidence) if confidence is not None else 0.0,
            verified=bool(row["verified"]),
            source=str(row.get("source") or ""),
            metadata=metadata if isinstance(metadata, dict) else {},
        )

    @staticmethod
    def _raise_for_status(response: httpx.Response, operation: str) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SupabaseAliasError(
                f"Supabase could not {operation} (HTTP {response.status_code})"
            ) from exc
