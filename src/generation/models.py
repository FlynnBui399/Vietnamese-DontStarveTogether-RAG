"""Typed grounded-generation records exposed by the chat API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.terminology.models import ResolvedEntity

AnswerConfidence = Literal["high", "medium", "low", "none"]


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    """One active-corpus chunk that may be cited by the generated answer."""

    id: str
    chunk_id: str
    corpus_version_id: str
    corpus_version: str
    page_title: str
    section: str
    url: str
    revision_id: int
    content: str
    source_kind: str
    subjective: bool
    retrieved_at: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceConflict:
    """Conflicting structured values found within one page and field."""

    page_title: str
    field: str
    values: tuple[str, ...]
    source_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnswerLatency:
    """Measured request stages in milliseconds."""

    supabase_retrieval: float
    rerank_and_context: float
    generation: float
    total: float


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    """Complete generation result with only validated, user-visible citations."""

    answer: str
    citations: tuple[EvidenceSource, ...]
    resolved_entities: tuple[ResolvedEntity, ...]
    confidence: AnswerConfidence
    abstained: bool
    abstention_reason: str | None
    corpus_version: str | None
    subjective_warning: bool
    conflicts: tuple[EvidenceConflict, ...]
    latency_ms: AnswerLatency
