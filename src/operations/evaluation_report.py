"""Private Supabase Storage persistence for evaluation reports."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import quote

import httpx


class EvaluationReportError(RuntimeError):
    """Raised when an evaluation report cannot be stored privately."""


class SupabaseEvaluationReportRepository:
    """Upload JSON reports to deterministic run directories in a private bucket."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        bucket: str,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.bucket = bucket
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=30.0)
        self._headers = {
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
        }

    def __enter__(self) -> SupabaseEvaluationReportRepository:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the internally owned HTTP client."""
        if self._owns_client:
            self._client.close()

    def upload_json(self, kind: str, content: bytes) -> str:
        """Upload one immutable timestamped JSON report and return its object path."""
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        path = f"runs/{timestamp}/{kind}.json"
        encoded = "/".join(quote(part, safe="") for part in path.split("/"))
        response = self._client.post(
            f"{self.base_url}/storage/v1/object/{self.bucket}/{encoded}",
            headers={**self._headers, "Content-Type": "application/json", "x-upsert": "false"},
            content=content,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise EvaluationReportError(
                f"Supabase could not upload the {kind} report (HTTP {response.status_code})"
            ) from exc
        return path
