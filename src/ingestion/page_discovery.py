"""Bounded seed and category discovery with explicit inclusion policy."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, cast

from src.ingestion.mediawiki_client import PageReference

GameScope = Literal[
    "dst",
    "dont_starve",
    "reign_of_giants",
    "shipwrecked",
    "hamlet",
    "mixed",
    "unknown",
]
VALID_GAME_SCOPES = {
    "dst",
    "dont_starve",
    "reign_of_giants",
    "shipwrecked",
    "hamlet",
    "mixed",
    "unknown",
}


class DiscoveryClient(Protocol):
    """MediaWiki methods required by the discovery traversal."""

    def resolve_titles(self, titles: tuple[str, ...]) -> list[PageReference]: ...

    def category_members(self, category: str, *, limit: int) -> list[PageReference]: ...


@dataclass(frozen=True, slots=True)
class DiscoveryPolicy:
    """Auditable crawl boundary loaded from version-controlled JSON."""

    seed_titles: tuple[str, ...]
    seed_categories: tuple[str, ...]
    allowed_namespaces: frozenset[int]
    denied_namespaces: frozenset[int]
    title_deny_patterns: tuple[str, ...]
    category_deny_patterns: tuple[str, ...]
    max_depth: int
    max_pages: int
    max_members_per_category: int
    game_scope: GameScope

    def __post_init__(self) -> None:
        if self.max_depth < 0:
            raise ValueError("max_depth cannot be negative")
        if self.max_pages <= 0:
            raise ValueError("max_pages must be positive")
        if self.max_members_per_category <= 0:
            raise ValueError("max_members_per_category must be positive")
        overlap = self.allowed_namespaces & self.denied_namespaces
        if overlap:
            raise ValueError(f"Namespaces cannot be both allowed and denied: {sorted(overlap)}")

    @classmethod
    def from_path(
        cls,
        path: Path,
        *,
        max_depth: int | None = None,
        max_pages: int | None = None,
    ) -> DiscoveryPolicy:
        """Load and optionally narrow traversal limits from a JSON file."""
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Discovery configuration must be a JSON object")
        game_scope = str(payload["game_scope"])
        if game_scope not in VALID_GAME_SCOPES:
            raise ValueError(f"Unsupported discovery game_scope: {game_scope}")
        return cls(
            seed_titles=tuple(str(value) for value in payload["seed_titles"]),
            seed_categories=tuple(str(value) for value in payload["seed_categories"]),
            allowed_namespaces=frozenset(int(value) for value in payload["allowed_namespaces"]),
            denied_namespaces=frozenset(int(value) for value in payload["denied_namespaces"]),
            title_deny_patterns=tuple(str(value) for value in payload["title_deny_patterns"]),
            category_deny_patterns=tuple(str(value) for value in payload["category_deny_patterns"]),
            max_depth=int(payload["max_depth"] if max_depth is None else max_depth),
            max_pages=int(payload["max_pages"] if max_pages is None else max_pages),
            max_members_per_category=int(payload["max_members_per_category"]),
            game_scope=cast(GameScope, game_scope),
        )

    def to_dict(self) -> dict[str, object]:
        """Return the effective limits without hidden defaults."""
        return {
            "seed_titles": list(self.seed_titles),
            "seed_categories": list(self.seed_categories),
            "allowed_namespaces": sorted(self.allowed_namespaces),
            "denied_namespaces": sorted(self.denied_namespaces),
            "title_deny_patterns": list(self.title_deny_patterns),
            "category_deny_patterns": list(self.category_deny_patterns),
            "max_depth": self.max_depth,
            "max_pages": self.max_pages,
            "max_members_per_category": self.max_members_per_category,
            "game_scope": self.game_scope,
        }


@dataclass(frozen=True, slots=True)
class DiscoveredPage:
    """An included article and the traversal edge that found it."""

    reference: PageReference
    source: str
    depth: int


@dataclass(frozen=True, slots=True)
class ExcludedCandidate:
    """A candidate rejected by an explicit discovery rule."""

    title: str
    page_id: int | None
    namespace: int | None
    source: str
    depth: int
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "page_id": self.page_id,
            "namespace": self.namespace,
            "source": self.source,
            "depth": self.depth,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    """Included pages plus an auditable include/exclude report."""

    pages: tuple[DiscoveredPage, ...]
    excluded: tuple[ExcludedCandidate, ...]
    visited_categories: tuple[str, ...]
    truncated: bool
    policy: DiscoveryPolicy

    def to_dict(self) -> dict[str, object]:
        return {
            "included_count": len(self.pages),
            "excluded_count": len(self.excluded),
            "truncated": self.truncated,
            "visited_categories": list(self.visited_categories),
            "policy": self.policy.to_dict(),
            "included": [
                {
                    "page_id": page.reference.page_id,
                    "title": page.reference.title,
                    "namespace": page.reference.namespace,
                    "source": page.source,
                    "depth": page.depth,
                }
                for page in self.pages
            ],
            "excluded": [candidate.to_dict() for candidate in self.excluded],
        }


class PageDiscovery:
    """Discover pages using seeds and a breadth-first, depth-limited category walk."""

    def __init__(self, client: DiscoveryClient) -> None:
        self._client = client

    def discover(self, policy: DiscoveryPolicy) -> DiscoveryResult:
        """Return no more than the configured number of allowlisted article pages."""
        included: dict[int, DiscoveredPage] = {}
        excluded: list[ExcludedCandidate] = []

        for reference in self._client.resolve_titles(policy.seed_titles):
            self._consider_page(
                reference,
                source=f"seed:{reference.title}",
                depth=0,
                policy=policy,
                included=included,
                excluded=excluded,
            )
            if len(included) >= policy.max_pages:
                break

        queue = deque((category, 0) for category in policy.seed_categories)
        visited: list[str] = []
        visited_keys: set[str] = set()
        truncated = len(included) >= policy.max_pages

        while queue and len(included) < policy.max_pages:
            category, depth = queue.popleft()
            category_key = category.casefold()
            if category_key in visited_keys:
                excluded.append(
                    ExcludedCandidate(category, None, 14, category, depth, "duplicate_category")
                )
                continue
            if self._matches(category, policy.category_deny_patterns):
                excluded.append(
                    ExcludedCandidate(category, None, 14, category, depth, "denied_category")
                )
                continue

            visited_keys.add(category_key)
            visited.append(category)
            members = self._client.category_members(
                category,
                limit=policy.max_members_per_category,
            )
            for member in members:
                if member.member_type == "subcat" or member.namespace == 14:
                    if depth < policy.max_depth:
                        if self._matches(member.title, policy.category_deny_patterns):
                            excluded.append(
                                ExcludedCandidate(
                                    member.title,
                                    member.page_id,
                                    member.namespace,
                                    category,
                                    depth + 1,
                                    "denied_category",
                                )
                            )
                        else:
                            queue.append((member.title, depth + 1))
                    else:
                        excluded.append(
                            ExcludedCandidate(
                                member.title,
                                member.page_id,
                                member.namespace,
                                category,
                                depth + 1,
                                "depth_limit",
                            )
                        )
                    continue

                self._consider_page(
                    member,
                    source=category,
                    depth=depth,
                    policy=policy,
                    included=included,
                    excluded=excluded,
                )
                if len(included) >= policy.max_pages:
                    truncated = True
                    break

        if queue:
            truncated = True
        return DiscoveryResult(
            pages=tuple(included.values()),
            excluded=tuple(excluded),
            visited_categories=tuple(visited),
            truncated=truncated,
            policy=policy,
        )

    @classmethod
    def _consider_page(
        cls,
        reference: PageReference,
        *,
        source: str,
        depth: int,
        policy: DiscoveryPolicy,
        included: dict[int, DiscoveredPage],
        excluded: list[ExcludedCandidate],
    ) -> None:
        reason: str | None = None
        if reference.page_id in included:
            reason = "duplicate_page"
        elif reference.namespace in policy.denied_namespaces:
            reason = "denied_namespace"
        elif reference.namespace not in policy.allowed_namespaces:
            reason = "namespace_not_allowed"
        elif cls._matches(reference.title, policy.title_deny_patterns):
            reason = "denied_title"

        if reason is not None:
            excluded.append(
                ExcludedCandidate(
                    reference.title,
                    reference.page_id,
                    reference.namespace,
                    source,
                    depth,
                    reason,
                )
            )
            return
        included[reference.page_id] = DiscoveredPage(reference, source, depth)

    @staticmethod
    def _matches(value: str, patterns: tuple[str, ...]) -> bool:
        normalized = value.casefold()
        return any(pattern.casefold() in normalized for pattern in patterns)
