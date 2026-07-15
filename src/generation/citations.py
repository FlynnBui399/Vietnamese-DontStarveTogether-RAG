"""Build and validate citations against accepted active-corpus evidence."""

from __future__ import annotations

import re
from collections.abc import Sequence

from src.generation.models import EvidenceSource
from src.retrieval.models import RetrievalResult
from src.terminology.normalizer import normalize_search_text

CITATION_PATTERN = re.compile(r"\[(S[1-9][0-9]*)\]")
NUMBER_PATTERN = re.compile(r"(?<!\w)-?\d+(?:[.,]\d+)?%?")


class CitationValidationError(ValueError):
    """Raised when generated factual text is not grounded in accepted evidence."""


def build_evidence_sources(result: RetrievalResult) -> tuple[EvidenceSource, ...]:
    """Assign stable S-identifiers only to context blocks accepted for generation."""
    candidates = {candidate.chunk_id: candidate for candidate in result.candidates}
    sources: list[EvidenceSource] = []
    for index, block in enumerate(result.context.blocks, start=1):
        candidate = candidates[block.chunk_id]
        retrieved_at = candidate.metadata.get("retrieved_at")
        sources.append(
            EvidenceSource(
                id=f"S{index}",
                chunk_id=block.chunk_id,
                corpus_version_id=candidate.corpus_version_id,
                corpus_version=result.corpus.version,
                page_title=block.page_title,
                section=block.section_path,
                url=block.canonical_url,
                revision_id=block.revision_id,
                content=block.content,
                source_kind=candidate.source_kind,
                subjective=candidate.subjective,
                retrieved_at=str(retrieved_at) if retrieved_at else None,
            )
        )
    return tuple(sources)


class CitationValidator:
    """Reject fake IDs, wrong corpus chunks, uncited claims, and unsupported numbers."""

    def validate(
        self,
        answer: str,
        sources: Sequence[EvidenceSource],
        *,
        active_corpus_id: str,
    ) -> tuple[EvidenceSource, ...]:
        if not answer.strip():
            raise CitationValidationError("Generated answer is empty")
        source_map = {source.id: source for source in sources}
        cited_ids = CITATION_PATTERN.findall(answer)
        if not cited_ids:
            raise CitationValidationError("Factual answer contains no citation")
        unknown = sorted(set(cited_ids) - source_map.keys())
        if unknown:
            raise CitationValidationError(f"Unknown citation IDs: {', '.join(unknown)}")
        if any(
            source_map[source_id].corpus_version_id != active_corpus_id for source_id in cited_ids
        ):
            raise CitationValidationError("Citation does not belong to the active corpus")
        self._validate_claims(answer, source_map)
        return tuple(source for source in sources if source.id in set(cited_ids))

    def _validate_claims(self, answer: str, source_map: dict[str, EvidenceSource]) -> None:
        claims = re.split(r"(?<=[.!?])\s+|\n+", answer)
        for claim in claims:
            clean = claim.strip().lstrip("-*#| ")
            if len(normalize_search_text(clean).split()) < 4 or self._is_table_separator(clean):
                continue
            claim_ids = CITATION_PATTERN.findall(clean)
            if not claim_ids:
                raise CitationValidationError("A factual claim has no citation")
            cited_text = " ".join(source_map[source_id].content for source_id in claim_ids)
            source_numbers = {
                self._normalize_number(value) for value in NUMBER_PATTERN.findall(cited_text)
            }
            for number in NUMBER_PATTERN.findall(CITATION_PATTERN.sub("", clean)):
                if self._normalize_number(number) not in source_numbers:
                    raise CitationValidationError(f"Unsupported numeric claim: {number}")

    @staticmethod
    def _normalize_number(value: str) -> str:
        return value.replace(",", ".")

    @staticmethod
    def _is_table_separator(value: str) -> bool:
        return bool(value) and not re.search(r"[\wÀ-ỹ]", value, re.UNICODE)
