"""Typed hybrid retrieval, reranking, and context records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.terminology.models import ExpandedQuery

RetrievalConfidence = Literal["high", "medium", "low", "none"]


@dataclass(frozen=True, slots=True)
class ActiveCorpus:
    """The only corpus eligible for production retrieval."""

    id: str
    version: str
    embedding_model_key: str


@dataclass(frozen=True, slots=True)
class HybridCandidate:
    """One active-corpus candidate returned by the protected hybrid RPC."""

    chunk_id: str
    corpus_version_id: str
    page_title: str
    section_path: str
    content: str
    content_hash: str
    token_count: int
    game_scope: str
    entity_type: str | None
    source_kind: str
    subjective: bool
    canonical_url: str
    revision_id: int
    metadata: dict[str, object]
    lexical_rank: int | None
    semantic_rank: int | None
    cosine_similarity: float | None
    rrf_score: float
    rerank_score: float = 0.0
    rerank_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ContextBlock:
    """One accepted evidence block with a stable context identifier."""

    context_id: str
    chunk_id: str
    page_title: str
    section_path: str
    content: str
    canonical_url: str
    revision_id: int
    token_count: int
    score: float


@dataclass(frozen=True, slots=True)
class ContextAssembly:
    """Bounded, diverse evidence ready for a later generation milestone."""

    blocks: tuple[ContextBlock, ...]
    token_count: int
    token_budget: int

    @property
    def rendered(self) -> str:
        return "\n\n".join(
            (
                f"[{block.context_id}]\n"
                f"Page: {block.page_title}\n"
                f"Section: {block.section_path}\n"
                f"Revision: {block.revision_id}\n"
                f"{block.content}"
            )
            for block in self.blocks
        )


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """Complete retrieval-stage output before generation and final citations."""

    query: ExpandedQuery
    corpus: ActiveCorpus
    candidates: tuple[HybridCandidate, ...]
    context: ContextAssembly
    confidence: RetrievalConfidence
    retrieval_latency_ms: float
    total_latency_ms: float
