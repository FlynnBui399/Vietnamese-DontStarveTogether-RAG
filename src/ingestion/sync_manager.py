"""Orchestrate one auditable, idempotent raw-wiki synchronization run."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from src.ingestion.mediawiki_client import PageReference, RawWikiPage, SiteInfo
from src.ingestion.page_discovery import (
    DiscoveredPage,
    DiscoveryPolicy,
    DiscoveryResult,
    GameScope,
    PageDiscovery,
)


class IngestionRepository(Protocol):
    """Persistence operations used by the sync manager."""

    def create_sync_run(self, *, sync_type: str, details: dict[str, object]) -> str: ...

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
    ) -> None: ...

    def revision_exists(self, *, page_id: int, revision_id: int) -> bool: ...

    def upload_raw_snapshot(self, page: RawWikiPage) -> bool: ...

    def upsert_wiki_page(
        self,
        page: RawWikiPage,
        discovered: DiscoveredPage,
        *,
        game_scope: GameScope,
    ) -> str: ...

    def upsert_attribution(self, wiki_page_id: str, page: RawWikiPage, site: SiteInfo) -> None: ...


class SyncClient(Protocol):
    """MediaWiki operations required by discovery and synchronization."""

    def site_info(self) -> SiteInfo: ...

    def resolve_titles(self, titles: tuple[str, ...]) -> list[PageReference]: ...

    def category_members(self, category: str, *, limit: int) -> list[PageReference]: ...

    def fetch_pages(self, references: tuple[PageReference, ...]) -> list[RawWikiPage]: ...


@dataclass(frozen=True, slots=True)
class SyncSummary:
    """Truthful counters and reports from a completed synchronization attempt."""

    run_id: str
    status: str
    pages_discovered: int
    pages_fetched: int
    pages_changed: int
    pages_unchanged: int
    raw_objects_uploaded: int
    raw_objects_existing: int
    errors: tuple[str, ...]
    site_info: dict[str, object]
    discovery_report: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "pages_discovered": self.pages_discovered,
            "pages_fetched": self.pages_fetched,
            "pages_changed": self.pages_changed,
            "pages_unchanged": self.pages_unchanged,
            "raw_objects_uploaded": self.raw_objects_uploaded,
            "raw_objects_existing": self.raw_objects_existing,
            "errors": list(self.errors),
            "site_info": self.site_info,
            "discovery_report": self.discovery_report,
        }


class SyncManager:
    """Fetch only bounded discoveries and persist each immutable revision once."""

    def __init__(self, client: SyncClient, repository: IngestionRepository) -> None:
        self._client = client
        self._repository = repository

    def run(self, policy: DiscoveryPolicy, *, sync_type: str = "initial") -> SyncSummary:
        """Run a sync and always finalize its audit row after creation."""
        run_id = self._repository.create_sync_run(
            sync_type=sync_type,
            details={"policy": policy.to_dict(), "phase": "starting"},
        )
        site: SiteInfo | None = None
        discovery: DiscoveryResult | None = None
        fetched = 0
        changed = 0
        unchanged = 0
        uploaded = 0
        existing_objects = 0
        errors: list[str] = []

        try:
            site = self._client.site_info()
            discovery = PageDiscovery(self._client).discover(policy)
            raw_pages = self._client.fetch_pages(
                tuple(candidate.reference for candidate in discovery.pages)
            )
            discovered_by_id = {
                candidate.reference.page_id: candidate for candidate in discovery.pages
            }
            fetched_ids = {page.page_id for page in raw_pages}
            for candidate in discovery.pages:
                if candidate.reference.page_id not in fetched_ids:
                    errors.append(
                        f"{candidate.reference.title}: no readable latest revision returned"
                    )

            for page in raw_pages:
                fetched += 1
                candidate = discovered_by_id[page.page_id]
                try:
                    if self._repository.revision_exists(
                        page_id=page.page_id,
                        revision_id=page.revision_id,
                    ):
                        unchanged += 1
                        continue
                    if self._repository.upload_raw_snapshot(page):
                        uploaded += 1
                    else:
                        existing_objects += 1
                    wiki_page_id = self._repository.upsert_wiki_page(
                        page,
                        candidate,
                        game_scope=policy.game_scope,
                    )
                    self._repository.upsert_attribution(wiki_page_id, page, site)
                    changed += 1
                except Exception as exc:  # Continue other bounded pages and record the exact title.
                    errors.append(f"{page.title}: {type(exc).__name__}: {exc}")
        except Exception as exc:
            errors.append(f"sync: {type(exc).__name__}: {exc}")

        site_report = site.to_dict() if site is not None else {}
        discovery_report = discovery.to_dict() if discovery is not None else {}
        status = "succeeded" if not errors else "failed"
        details: dict[str, object] = {
            "completed_at": datetime.now(UTC).isoformat(),
            "site_info": site_report,
            "discovery_report": discovery_report,
            "pages_unchanged": unchanged,
            "raw_objects_uploaded": uploaded,
            "raw_objects_existing": existing_objects,
            "errors": errors,
        }
        self._repository.finish_sync_run(
            run_id,
            status=status,
            pages_discovered=len(discovery.pages) if discovery is not None else 0,
            pages_fetched=fetched,
            pages_changed=changed,
            error_count=len(errors),
            details=details,
        )
        return SyncSummary(
            run_id=run_id,
            status=status,
            pages_discovered=len(discovery.pages) if discovery is not None else 0,
            pages_fetched=fetched,
            pages_changed=changed,
            pages_unchanged=unchanged,
            raw_objects_uploaded=uploaded,
            raw_objects_existing=existing_objects,
            errors=tuple(errors),
            site_info=site_report,
            discovery_report=discovery_report,
        )
