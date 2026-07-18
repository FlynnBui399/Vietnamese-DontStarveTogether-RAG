"""Supabase Data API and Storage writes used by raw wiki ingestion."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from src.ingestion.mediawiki_client import RawWikiPage, SiteInfo
from src.ingestion.page_discovery import DiscoveredPage, GameScope


class SupabaseIngestionError(RuntimeError):
    """Raised when an ingestion write fails."""


class SupabaseIngestionRepository:
    """Persist sync runs, revision metadata, attribution, and private raw objects."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        raw_bucket: str,
        timeout_seconds: float = 20.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.raw_bucket = raw_bucket
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._auth_headers = {
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
        }

    def __enter__(self) -> SupabaseIngestionRepository:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the internally owned HTTP client."""
        if self._owns_client:
            self._client.close()

    def create_sync_run(self, *, sync_type: str, details: dict[str, object]) -> str:
        """Create a running audit row and return its UUID."""
        response = self._client.post(
            f"{self.base_url}/rest/v1/sync_runs",
            headers=self._database_headers(write=True, representation=True),
            json={"status": "running", "sync_type": sync_type, "details": details},
        )
        rows = self._rows(response, "create sync run")
        return str(rows[0]["id"])

    def finish_sync_run(
        self,
        run_id: str,
        *,
        status: str,
        pages_discovered: int,
        pages_fetched: int,
        pages_changed: int,
        error_count: int,
        details: dict[str, object],
    ) -> None:
        """Finish a sync run with counters and its discovery report."""
        response = self._client.patch(
            f"{self.base_url}/rest/v1/sync_runs",
            headers=self._database_headers(write=True),
            params={"id": f"eq.{run_id}"},
            json={
                "status": status,
                "finished_at": datetime.now(UTC).isoformat(),
                "pages_discovered": pages_discovered,
                "pages_fetched": pages_fetched,
                "pages_changed": pages_changed,
                "chunks_created": 0,
                "error_count": error_count,
                "details": details,
            },
        )
        self._raise_for_status(response, "finish sync run")

    def revision_exists(self, *, page_id: int, revision_id: int) -> bool:
        """Return whether this immutable MediaWiki revision was already persisted."""
        response = self._client.get(
            f"{self.base_url}/rest/v1/wiki_pages",
            headers=self._database_headers(),
            params={
                "mediawiki_page_id": f"eq.{page_id}",
                "revision_id": f"eq.{revision_id}",
                "select": "id",
                "limit": "1",
            },
        )
        return bool(self._rows(response, "check page revision", allow_empty=True))

    def upload_raw_snapshot(self, page: RawWikiPage) -> bool:
        """Upload once to the deterministic private path; return false for an existing object."""
        encoded_path = "/".join(quote(part, safe="") for part in page.storage_path.split("/"))
        response = self._client.post(
            f"{self.base_url}/storage/v1/object/{self.raw_bucket}/{encoded_path}",
            headers={
                **self._auth_headers,
                "Content-Type": "application/json",
                "x-upsert": "false",
            },
            content=page.storage_bytes(),
        )
        if response.status_code in {400, 409}:
            body = response.text.casefold()
            if "duplicate" in body or "already exists" in body or "resource already exists" in body:
                return False
        self._raise_for_status(response, "upload raw wiki snapshot")
        return True

    def upsert_wiki_page(
        self,
        page: RawWikiPage,
        discovered: DiscoveredPage,
        *,
        game_scope: GameScope,
    ) -> str:
        """Deactivate older revisions and upsert the current revision metadata."""
        deactivate = self._client.patch(
            f"{self.base_url}/rest/v1/wiki_pages",
            headers=self._database_headers(write=True),
            params={
                "mediawiki_page_id": f"eq.{page.page_id}",
                "revision_id": f"neq.{page.revision_id}",
                "is_active": "eq.true",
            },
            json={"is_active": False},
        )
        self._raise_for_status(deactivate, "deactivate prior page revision")

        row = {
            "mediawiki_page_id": page.page_id,
            "title": page.title,
            "slug": page.title.replace(" ", "_"),
            "canonical_url": page.canonical_url,
            "namespace": page.namespace,
            "revision_id": page.revision_id,
            "revision_timestamp": page.revision_timestamp,
            "retrieved_at": page.retrieved_at,
            "content_hash": page.content_hash,
            "game_scope": game_scope,
            "entity_type": None,
            "source_kind": "unknown",
            "language": "en",
            "raw_storage_bucket": self.raw_bucket,
            "raw_storage_path": page.storage_path,
            "is_active": True,
            "metadata": {
                "api_url": page.api_url,
                "content_model": page.content_model,
                "discovery_depth": discovered.depth,
                "discovery_source": discovered.source,
                "fetch_method": "mediawiki_api",
                "mediawiki_sha1": page.mediawiki_sha1,
            },
        }
        response = self._client.post(
            f"{self.base_url}/rest/v1/wiki_pages",
            headers=self._database_headers(write=True, representation=True, merge=True),
            params={"on_conflict": "mediawiki_page_id,revision_id"},
            json=row,
        )
        rows = self._rows(response, "upsert wiki page")
        return str(rows[0]["id"])

    def upsert_attribution(self, wiki_page_id: str, page: RawWikiPage, site: SiteInfo) -> None:
        """Preserve the canonical source and site-reported license metadata."""
        response = self._client.post(
            f"{self.base_url}/rest/v1/source_attributions",
            headers=self._database_headers(write=True, merge=True),
            params={"on_conflict": "wiki_page_id,source_url"},
            json={
                "wiki_page_id": wiki_page_id,
                "source_name": site.site_name,
                "source_url": page.canonical_url,
                "license_name": site.rights_text,
                "attribution_text": f"Source: {site.site_name}",
                "metadata": {"license_url": site.rights_url},
            },
        )
        self._raise_for_status(response, "upsert source attribution")

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
            raise SupabaseIngestionError(f"Supabase {operation} returned a non-list response")
        rows = [row for row in payload if isinstance(row, dict)]
        if not rows and not allow_empty:
            raise SupabaseIngestionError(f"Supabase {operation} returned no rows")
        return rows

    @staticmethod
    def _raise_for_status(response: httpx.Response, operation: str) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SupabaseIngestionError(
                f"Supabase could not {operation} (HTTP {response.status_code})"
            ) from exc
