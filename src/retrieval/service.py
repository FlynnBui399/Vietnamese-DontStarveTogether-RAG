"""End-to-end query expansion, hybrid retrieval, reranking, and context assembly."""

from __future__ import annotations

import re
from collections.abc import Sequence
from time import perf_counter
from typing import Protocol

from src.embeddings import EmbeddingAdapter
from src.retrieval.context import ContextAssembler
from src.retrieval.models import ActiveCorpus, HybridCandidate, RetrievalConfidence, RetrievalResult
from src.retrieval.reranker import HeuristicReranker
from src.terminology import QueryExpander, normalize_search_text, normalize_unicode

LEXICAL_UNSAFE = re.compile(r"[^\w\s'-]", re.UNICODE)
SECTION_INTENTS = {
    "craft": ("craft", "crafting", "recipe", "cong thuc", "cach lam", "che tao"),
    "obtain": ("obtain", "acquisition", "where", "find", "lay o dau", "tim"),
    "usage": ("usage", "use", "dung", "tac dung"),
    "history": ("history", "update", "version", "lich su", "phien ban"),
    "combat": ("combat", "damage", "fight", "chien dau", "sat thuong"),
}


class HybridRetrievalRepository(Protocol):
    """Protected active-corpus retrieval boundary."""

    def get_active_corpus(self) -> ActiveCorpus: ...

    def hybrid_search(
        self,
        *,
        query_text: str,
        query_embedding: Sequence[float],
        match_count: int,
        lexical_count: int,
        semantic_count: int,
        filter_entity_type: str | None,
        entity_titles: Sequence[str],
        section_intent: str | None,
    ) -> list[HybridCandidate]: ...


class RetrievalService:
    """Retrieve only accepted evidence from the active DST corpus."""

    def __init__(
        self,
        repository: HybridRetrievalRepository,
        embedding_adapter: EmbeddingAdapter,
        query_expander: QueryExpander,
        *,
        reranker: HeuristicReranker | None = None,
        context_assembler: ContextAssembler | None = None,
        evidence_threshold: float = 0.20,
    ) -> None:
        if not 0.0 <= evidence_threshold <= 1.0:
            raise ValueError("Evidence threshold must be in [0, 1]")
        self.repository = repository
        self.embedding_adapter = embedding_adapter
        self.query_expander = query_expander
        self.reranker = reranker or HeuristicReranker()
        self.context_assembler = context_assembler or ContextAssembler()
        self.evidence_threshold = evidence_threshold

    def retrieve(
        self,
        query: str,
        *,
        match_count: int = 10,
        filter_entity_type: str | None = None,
    ) -> RetrievalResult:
        """Expand, embed, retrieve, rerank, filter, deduplicate, and assemble context."""
        if not query.strip():
            raise ValueError("Retrieval query cannot be empty")
        started = perf_counter()
        corpus = self.repository.get_active_corpus()
        if corpus.embedding_model_key != self.embedding_adapter.manifest.model_key:
            raise RuntimeError(
                "Active corpus embedding model does not match the configured query adapter"
            )
        expanded = self.query_expander.expand(query)
        query_embedding = self.embedding_adapter.embed([expanded.query.original])[0]
        section_intent = self._section_intent(expanded.query.search_normalized)
        entity_titles = tuple(
            entity.entity_title
            for entity in expanded.resolved_entities
            if entity.verified and entity.confidence >= 0.70
        )
        retrieval_started = perf_counter()
        candidates = self.repository.hybrid_search(
            query_text=self._lexical_query(expanded.terms),
            query_embedding=query_embedding,
            match_count=max(match_count * 4, 30),
            lexical_count=40,
            semantic_count=40,
            filter_entity_type=filter_entity_type,
            entity_titles=entity_titles,
            section_intent=section_intent,
        )
        retrieval_latency_ms = (perf_counter() - retrieval_started) * 1000.0
        reranked = self.reranker.rerank(
            expanded,
            candidates,
            section_intent=section_intent,
        )
        accepted = self._accepted(reranked, match_count)
        context = self.context_assembler.assemble(
            accepted,
            preferred_pages=entity_titles,
        )
        confidence = self._confidence(accepted)
        return RetrievalResult(
            query=expanded,
            corpus=corpus,
            candidates=tuple(accepted),
            context=context,
            confidence=confidence,
            retrieval_latency_ms=retrieval_latency_ms,
            total_latency_ms=(perf_counter() - started) * 1000.0,
        )

    def _accepted(
        self,
        candidates: list[HybridCandidate],
        match_count: int,
    ) -> list[HybridCandidate]:
        accepted: list[HybridCandidate] = []
        seen_hashes: set[str] = set()
        for candidate in candidates:
            if candidate.game_scope != "dst" or candidate.rerank_score < self.evidence_threshold:
                continue
            body_hash = candidate.metadata.get("body_hash")
            deduplication_key = (
                str(body_hash) if isinstance(body_hash, str) else candidate.content_hash
            )
            if deduplication_key in seen_hashes:
                continue
            seen_hashes.add(deduplication_key)
            accepted.append(candidate)
            if len(accepted) == match_count:
                break
        return accepted

    @staticmethod
    def _lexical_query(terms: tuple[str, ...]) -> str:
        safe_terms: list[str] = []
        for term in terms:
            safe = LEXICAL_UNSAFE.sub(" ", normalize_unicode(term))
            safe = re.sub(r"\s+", " ", safe).strip()
            if not safe:
                continue
            safe_terms.append(f'"{safe}"' if " " in safe else safe)
        return " OR ".join(dict.fromkeys(safe_terms))

    @staticmethod
    def _section_intent(query_normalized: str) -> str | None:
        padded = f" {normalize_search_text(query_normalized)} "
        for section, markers in SECTION_INTENTS.items():
            if any(f" {marker} " in padded for marker in markers):
                return section
        return None

    @staticmethod
    def _confidence(candidates: list[HybridCandidate]) -> RetrievalConfidence:
        if not candidates:
            return "none"
        top_score = candidates[0].rerank_score
        if top_score >= 0.55 and len(candidates) >= 2:
            return "high"
        if top_score >= 0.35:
            return "medium"
        return "low"
