"""Typed records shared by the Milestone 3 processing pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

GameScope = Literal[
    "dst",
    "dont_starve",
    "reign_of_giants",
    "shipwrecked",
    "hamlet",
    "mixed",
    "unknown",
]
EntityType = Literal[
    "character",
    "item",
    "weapon",
    "armor",
    "tool",
    "food",
    "recipe",
    "structure",
    "mob",
    "boss",
    "mechanic",
    "biome",
    "season",
    "guide",
    "update",
    "other",
]
SourceKind = Literal[
    "factual_article",
    "guide",
    "version_history",
    "category_list",
    "unknown",
]


@dataclass(frozen=True, slots=True)
class SourcePage:
    """Current raw wiki revision selected from Supabase."""

    id: str
    mediawiki_page_id: int
    title: str
    canonical_url: str
    revision_id: int
    revision_timestamp: str | None
    preliminary_game_scope: GameScope
    raw_storage_bucket: str
    raw_storage_path: str
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ParsedSection:
    """One cleaned semantic section with its heading hierarchy."""

    path: tuple[str, ...]
    content: str

    @property
    def section_path(self) -> str:
        return " > ".join(self.path)


@dataclass(frozen=True, slots=True)
class ParsedPage:
    """Cleaned page structure and classifier evidence."""

    source: SourcePage
    sections: tuple[ParsedSection, ...]
    categories: tuple[str, ...]
    template_names: tuple[str, ...]
    scope_hints: tuple[str, ...]
    infobox_facts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PageClassification:
    """Page-level labels plus auditable rule reasons."""

    game_scope: GameScope
    entity_type: EntityType
    source_kind: SourceKind
    subjective: bool
    scope_reason: str
    entity_reason: str
    source_reason: str


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    """Validated-column candidate before a corpus UUID is attached."""

    wiki_page_id: str
    mediawiki_page_id: int
    source_key: str
    page_title: str
    section_path: str
    chunk_index: int
    content: str
    content_normalized: str
    content_hash: str
    token_count: int
    game_scope: GameScope
    entity_type: EntityType
    source_kind: SourceKind
    subjective: bool
    canonical_url: str
    revision_id: int
    search_text: str
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One fatal or explained duplicate validation finding."""

    code: str
    message: str
    source_key: str | None = None
    fatal: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "source_key": self.source_key,
            "fatal": self.fatal,
        }


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Corpus-processing acceptance result and insertable chunks."""

    passed: bool
    total_candidates: int
    valid_chunk_count: int
    duplicate_count: int
    empty_count: int
    metadata_complete_count: int
    metadata_completeness: float
    expected_page_count: int
    covered_page_count: int
    issues: tuple[ValidationIssue, ...]
    valid_chunks: tuple[ChunkDraft, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "total_candidates": self.total_candidates,
            "valid_chunk_count": self.valid_chunk_count,
            "duplicate_count": self.duplicate_count,
            "empty_count": self.empty_count,
            "metadata_complete_count": self.metadata_complete_count,
            "metadata_completeness": self.metadata_completeness,
            "expected_page_count": self.expected_page_count,
            "covered_page_count": self.covered_page_count,
            "issues": [issue.to_dict() for issue in self.issues],
        }
