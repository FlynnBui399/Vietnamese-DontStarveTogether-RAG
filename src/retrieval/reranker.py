"""Auditable metadata and token-overlap reranking for hybrid candidates."""

from __future__ import annotations

from dataclasses import replace

from src.retrieval.models import HybridCandidate
from src.terminology.models import ExpandedQuery
from src.terminology.normalizer import normalize_search_text


class HeuristicReranker:
    """Combine normalized RRF, semantic, entity, title, and section evidence."""

    def rerank(
        self,
        expanded: ExpandedQuery,
        candidates: list[HybridCandidate],
        *,
        section_intent: str | None,
    ) -> list[HybridCandidate]:
        """Return candidates with a comparable [0, 1] evidence score."""
        query_tokens = set(normalize_search_text(" ".join(expanded.terms)).split())
        resolved_titles = {entity.entity_title.casefold() for entity in expanded.resolved_entities}
        recommendation_intent = any(
            marker in query_tokens for marker in {"guide", "recommend", "strategy", "tip"}
        )
        reranked: list[HybridCandidate] = []
        for candidate in candidates:
            title_tokens = set(normalize_search_text(candidate.page_title).split())
            content_tokens = set(normalize_search_text(candidate.content).split())
            title_overlap = self._overlap(query_tokens, title_tokens)
            content_overlap = self._overlap(query_tokens, content_tokens)
            semantic = max(0.0, min(candidate.cosine_similarity or 0.0, 1.0))
            rrf = min(candidate.rrf_score / 0.04, 1.0)
            entity_match = float(candidate.page_title.casefold() in resolved_titles)
            section_match = float(
                section_intent is not None and section_intent in candidate.section_path.casefold()
            )
            score = (
                0.35 * rrf
                + 0.20 * title_overlap
                + 0.15 * content_overlap
                + 0.15 * semantic
                + 0.10 * entity_match
                + 0.05 * section_match
            )
            reasons = ["rrf"]
            if title_overlap:
                reasons.append("title_overlap")
            if content_overlap:
                reasons.append("content_overlap")
            if semantic:
                reasons.append("semantic")
            if entity_match:
                reasons.append("resolved_entity")
            if section_match:
                reasons.append("section_intent")
            if candidate.subjective and not recommendation_intent:
                score -= 0.08
                reasons.append("subjective_penalty")
            reranked.append(
                replace(
                    candidate,
                    rerank_score=max(0.0, min(score, 1.0)),
                    rerank_reasons=tuple(reasons),
                )
            )
        reranked.sort(
            key=lambda candidate: (
                candidate.rerank_score,
                candidate.rrf_score,
                candidate.page_title.casefold(),
                candidate.chunk_id,
            ),
            reverse=True,
        )
        return reranked

    @staticmethod
    def _overlap(query_tokens: set[str], candidate_tokens: set[str]) -> float:
        if not query_tokens:
            return 0.0
        return len(query_tokens & candidate_tokens) / len(query_tokens)
