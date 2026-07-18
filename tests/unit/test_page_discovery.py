"""Bounded discovery tests for namespaces, denylists, cycles, and depth."""

from src.ingestion.mediawiki_client import PageReference
from src.ingestion.page_discovery import DiscoveryPolicy, PageDiscovery


class FakeDiscoveryClient:
    def resolve_titles(self, _titles: tuple[str, ...]) -> list[PageReference]:
        return [PageReference(1, "Don't Starve Together", 0)]

    def category_members(self, category: str, *, limit: int) -> list[PageReference]:
        members = {
            "Category:Don't Starve Together": [
                PageReference(1, "Don't Starve Together", 0),
                PageReference(2, "Football Helmet", 0),
                PageReference(3, "File:Helmet.png", 6, "file"),
                PageReference(4, "Wendy/Character quotes", 0),
                PageReference(20, "Category:Characters", 14, "subcat"),
                PageReference(21, "Category:Skins", 14, "subcat"),
            ],
            "Category:Characters": [
                PageReference(5, "Wendy", 0),
                PageReference(22, "Category:Don't Starve Together", 14, "subcat"),
            ],
        }
        return members.get(category, [])[:limit]


def _policy() -> DiscoveryPolicy:
    return DiscoveryPolicy(
        seed_titles=("Don't Starve Together",),
        seed_categories=("Category:Don't Starve Together",),
        allowed_namespaces=frozenset({0}),
        denied_namespaces=frozenset({1, 2, 3, 6}),
        title_deny_patterns=("/Character quotes",),
        category_deny_patterns=("skins",),
        max_depth=1,
        max_pages=10,
        max_members_per_category=20,
        game_scope="dst",
    )


def test_discovery_enforces_bounds_and_records_exclusions() -> None:
    result = PageDiscovery(FakeDiscoveryClient()).discover(_policy())

    assert [page.reference.title for page in result.pages] == [
        "Don't Starve Together",
        "Football Helmet",
        "Wendy",
    ]
    assert result.visited_categories == (
        "Category:Don't Starve Together",
        "Category:Characters",
    )
    assert {candidate.reason for candidate in result.excluded} == {
        "duplicate_page",
        "denied_namespace",
        "denied_title",
        "denied_category",
        "depth_limit",
    }


def test_discovery_never_exceeds_page_limit() -> None:
    policy = _policy()
    policy = DiscoveryPolicy(
        seed_titles=policy.seed_titles,
        seed_categories=policy.seed_categories,
        allowed_namespaces=policy.allowed_namespaces,
        denied_namespaces=policy.denied_namespaces,
        title_deny_patterns=policy.title_deny_patterns,
        category_deny_patterns=policy.category_deny_patterns,
        max_depth=policy.max_depth,
        max_pages=2,
        max_members_per_category=policy.max_members_per_category,
        game_scope=policy.game_scope,
    )

    result = PageDiscovery(FakeDiscoveryClient()).discover(policy)

    assert len(result.pages) == 2
    assert result.truncated is True
