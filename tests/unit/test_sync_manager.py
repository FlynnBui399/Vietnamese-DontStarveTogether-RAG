"""Idempotency and audit-counter tests for raw synchronization."""

from src.ingestion.mediawiki_client import PageReference, RawWikiPage, SiteInfo
from src.ingestion.page_discovery import (
    DiscoveredPage,
    DiscoveryPolicy,
    GameScope,
)
from src.ingestion.sync_manager import SyncManager


class FakeSyncClient:
    def site_info(self) -> SiteInfo:
        return SiteInfo(
            api_url="https://dontstarve.wiki.gg/api.php",
            site_name="Don't Starve Wiki",
            generator="MediaWiki 1.43.6",
            server="https://dontstarve.wiki.gg",
            article_path="/wiki/$1",
            language="en",
            rights_text="Creative Commons Attribution-ShareAlike 4.0 License",
            rights_url="https://creativecommons.org/licenses/by-sa/4.0",
            namespaces={0: "", 14: "Category"},
        )

    def resolve_titles(self, _titles: tuple[str, ...]) -> list[PageReference]:
        return [PageReference(1, "Don't Starve Together", 0)]

    def category_members(self, _category: str, *, limit: int) -> list[PageReference]:
        return [
            PageReference(1, "Don't Starve Together", 0),
            PageReference(2, "Football Helmet", 0),
        ][:limit]

    def fetch_pages(self, references: tuple[PageReference, ...]) -> list[RawWikiPage]:
        return [self._raw(reference) for reference in references]

    @staticmethod
    def _raw(reference: PageReference) -> RawWikiPage:
        revision_id = reference.page_id * 100
        return RawWikiPage(
            page_id=reference.page_id,
            title=reference.title,
            namespace=reference.namespace,
            canonical_url=f"https://dontstarve.wiki.gg/wiki/{reference.title.replace(' ', '_')}",
            revision_id=revision_id,
            revision_timestamp="2026-07-15T00:00:00Z",
            mediawiki_sha1="a" * 40,
            content_model="wikitext",
            content=f"Raw content for {reference.title}",
            retrieved_at="2026-07-15T00:01:00+00:00",
            api_url="https://dontstarve.wiki.gg/api.php",
            raw_page={"pageid": reference.page_id, "title": reference.title},
        )


class FakeRepository:
    def __init__(self) -> None:
        self.revisions: set[tuple[int, int]] = set()
        self.uploaded_paths: list[str] = []
        self.finished: list[dict[str, object]] = []
        self.run_number = 0

    def create_sync_run(self, *, sync_type: str, details: dict[str, object]) -> str:
        assert sync_type == "initial"
        assert "policy" in details
        self.run_number += 1
        return f"run-{self.run_number}"

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
        self.finished.append(
            {
                "run_id": run_id,
                "status": status,
                "pages_discovered": pages_discovered,
                "pages_fetched": pages_fetched,
                "pages_changed": pages_changed,
                "error_count": error_count,
                "details": details,
            }
        )

    def revision_exists(self, *, page_id: int, revision_id: int) -> bool:
        return (page_id, revision_id) in self.revisions

    def upload_raw_snapshot(self, page: RawWikiPage) -> bool:
        self.uploaded_paths.append(page.storage_path)
        return True

    def upsert_wiki_page(
        self,
        page: RawWikiPage,
        _discovered: DiscoveredPage,
        *,
        game_scope: GameScope,
    ) -> str:
        assert game_scope == "dst"
        self.revisions.add((page.page_id, page.revision_id))
        return f"wiki-{page.page_id}"

    def upsert_attribution(
        self,
        _wiki_page_id: str,
        _page: RawWikiPage,
        _site: SiteInfo,
    ) -> None:
        return None


def _policy() -> DiscoveryPolicy:
    return DiscoveryPolicy(
        seed_titles=("Don't Starve Together",),
        seed_categories=("Category:Don't Starve Together",),
        allowed_namespaces=frozenset({0}),
        denied_namespaces=frozenset({1, 6}),
        title_deny_patterns=(),
        category_deny_patterns=(),
        max_depth=0,
        max_pages=10,
        max_members_per_category=10,
        game_scope="dst",
    )


def test_second_sync_does_not_upload_or_upsert_unchanged_revisions() -> None:
    repository = FakeRepository()
    manager = SyncManager(FakeSyncClient(), repository)

    first = manager.run(_policy())
    second = manager.run(_policy())

    assert first.status == "succeeded"
    assert first.pages_changed == 2
    assert first.raw_objects_uploaded == 2
    assert second.status == "succeeded"
    assert second.pages_changed == 0
    assert second.pages_unchanged == 2
    assert second.raw_objects_uploaded == 0
    assert repository.uploaded_paths == ["pages/1/100.json", "pages/2/200.json"]
    assert repository.finished[1]["pages_changed"] == 0
