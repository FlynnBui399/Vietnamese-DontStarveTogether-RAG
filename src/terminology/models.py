"""Typed records for Vietnamese terminology and query expansion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AliasType = Literal[
    "official_title",
    "official_translation",
    "community_translation",
    "abbreviation",
    "common_misspelling",
    "descriptive_alias",
    "generated_candidate",
]
QueryLanguage = Literal["vi", "en", "mixed", "unknown"]
MatchType = Literal["exact_title", "exact_alias", "prefix", "fuzzy"]


@dataclass(frozen=True, slots=True)
class AliasRecord:
    """One canonical or alternate entity name with ranking evidence."""

    entity_title: str
    entity_slug: str
    alias: str
    alias_normalized: str
    language: str
    alias_type: AliasType
    priority: int
    confidence: float
    verified: bool
    source: str
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class NormalizedQuery:
    """Original query plus deterministic retrieval variants."""

    original: str
    normalized: str
    search_normalized: str
    language: QueryLanguage


@dataclass(frozen=True, slots=True)
class ResolvedEntity:
    """One ranked entity resolution result."""

    entity_title: str
    entity_slug: str
    matched_alias: str
    alias_type: AliasType
    match_type: MatchType
    verified: bool
    confidence: float
    score: float


@dataclass(frozen=True, slots=True)
class ExpandedQuery:
    """Safe, bounded query expansion output for retrieval."""

    query: NormalizedQuery
    resolved_entities: tuple[ResolvedEntity, ...]
    terms: tuple[str, ...]
