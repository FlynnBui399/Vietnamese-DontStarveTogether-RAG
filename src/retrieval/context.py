"""Evidence deduplication and bounded context assembly."""

from __future__ import annotations

from collections import Counter

from src.retrieval.models import ContextAssembly, ContextBlock, HybridCandidate


class ContextAssembler:
    """Build diverse context without splitting or silently truncating chunks."""

    def __init__(
        self,
        *,
        token_budget: int = 1800,
        max_chunks: int = 8,
        max_per_section: int = 2,
    ) -> None:
        if token_budget <= 0 or max_chunks <= 0 or max_per_section <= 0:
            raise ValueError("Context limits must be positive")
        self.token_budget = token_budget
        self.max_chunks = max_chunks
        self.max_per_section = max_per_section

    def assemble(
        self,
        candidates: list[HybridCandidate],
        *,
        preferred_pages: tuple[str, ...] = (),
    ) -> ContextAssembly:
        """Prefer one result per resolved page, then fill by score within hard limits."""
        ordered: list[HybridCandidate] = []
        for page_title in preferred_pages:
            match = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.page_title.casefold() == page_title.casefold()
                    and candidate not in ordered
                ),
                None,
            )
            if match is not None:
                ordered.append(match)
        ordered.extend(candidate for candidate in candidates if candidate not in ordered)

        selected: list[HybridCandidate] = []
        section_counts: Counter[tuple[str, str]] = Counter()
        used_tokens = 0
        for candidate in ordered:
            section_key = (candidate.page_title.casefold(), candidate.section_path.casefold())
            if section_counts[section_key] >= self.max_per_section:
                continue
            if used_tokens + candidate.token_count > self.token_budget:
                continue
            selected.append(candidate)
            section_counts[section_key] += 1
            used_tokens += candidate.token_count
            if len(selected) == self.max_chunks:
                break
        blocks = tuple(
            ContextBlock(
                context_id=f"CTX-{index}",
                chunk_id=candidate.chunk_id,
                page_title=candidate.page_title,
                section_path=candidate.section_path,
                content=candidate.content,
                canonical_url=candidate.canonical_url,
                revision_id=candidate.revision_id,
                token_count=candidate.token_count,
                score=candidate.rerank_score,
            )
            for index, candidate in enumerate(selected, start=1)
        )
        return ContextAssembly(
            blocks=blocks,
            token_count=used_tokens,
            token_budget=self.token_budget,
        )
