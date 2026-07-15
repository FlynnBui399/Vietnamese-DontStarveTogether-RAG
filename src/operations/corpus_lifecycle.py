"""Atomic corpus activation and rollback through protected PostgreSQL RPCs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import httpx


class CorpusLifecycleError(RuntimeError):
    """Raised when PostgreSQL rejects a corpus lifecycle transition."""


@dataclass(frozen=True, slots=True)
class CorpusTransition:
    """Auditable result of one atomic activation or rollback."""

    action: Literal["activate", "rollback"]
    active_version: str
    archived_version: str | None
    activated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "active_version": self.active_version,
            "archived_version": self.archived_version,
            "activated_at": self.activated_at,
        }


class SupabaseCorpusLifecycleRepository:
    """Call backend-only transactional corpus lifecycle functions."""

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
            "Content-Type": "application/json",
        }

    def __enter__(self) -> SupabaseCorpusLifecycleRepository:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the internally owned HTTP client."""
        if self._owns_client:
            self._client.close()

    def activate(self, version: str) -> CorpusTransition:
        """Validate and atomically activate one complete corpus."""
        return self._transition("activate_corpus_version", version, "activate")

    def rollback(self, version: str) -> CorpusTransition:
        """Validate and atomically restore one archived corpus."""
        return self._transition("rollback_corpus_version", version, "rollback")

    def _transition(
        self,
        function: str,
        version: str,
        action: Literal["activate", "rollback"],
    ) -> CorpusTransition:
        if not version.strip():
            raise ValueError("Corpus version is required")
        response = self._client.post(
            f"{self.base_url}/rest/v1/rpc/{function}",
            headers=self._headers,
            json={"p_version": version},
        )
        rows = self._rows(response, function)
        row = rows[0]
        archived = row.get("archived_version")
        return CorpusTransition(
            action=action,
            active_version=str(row["active_version"]),
            archived_version=str(archived) if archived is not None else None,
            activated_at=str(row["activated_at"]),
        )

    @staticmethod
    def _rows(response: httpx.Response, operation: str) -> list[dict[str, Any]]:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise CorpusLifecycleError(
                f"Supabase could not {operation} (HTTP {response.status_code})"
            ) from exc
        payload = response.json()
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
            raise CorpusLifecycleError(f"Supabase {operation} returned no transition row")
        return [row for row in payload if isinstance(row, dict)]
