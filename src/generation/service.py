"""Grounded retrieval-to-generation orchestration with fail-closed validation."""

from __future__ import annotations

from time import perf_counter

from src.generation.citations import (
    CitationValidationError,
    CitationValidator,
    build_evidence_sources,
)
from src.generation.guardrails import detect_conflicts, missing_comparison_entities
from src.generation.llm import LLMAdapter
from src.generation.models import AnswerLatency, GroundedAnswer
from src.generation.prompts import SYSTEM_PROMPT, build_user_prompt
from src.retrieval import RetrievalResult, RetrievalService

ABSTENTION_TEXT = (
    "Mình chưa tìm thấy đủ thông tin trong corpus Don't Starve Together đã được lập chỉ mục "
    "để trả lời chính xác câu hỏi này. Câu hỏi có thể thuộc mod, phiên bản khác hoặc nội dung "
    "chưa được đồng bộ."
)


class GroundedAnswerService:
    """Retrieve evidence, generate once, and expose only validated factual answers."""

    def __init__(
        self,
        retrieval_service: RetrievalService,
        llm: LLMAdapter,
        *,
        citation_validator: CitationValidator | None = None,
        match_count: int = 8,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.llm = llm
        self.citation_validator = citation_validator or CitationValidator()
        self.match_count = match_count

    def answer(self, query: str) -> GroundedAnswer:
        """Return an answer or a deterministic abstention without leaking invalid output."""
        started = perf_counter()
        result = self.retrieval_service.retrieve(query, match_count=self.match_count)
        sources = build_evidence_sources(result)
        rerank_ms = max(0.0, result.total_latency_ms - result.retrieval_latency_ms)
        if not sources:
            return self._abstain(
                result=result,
                reason="insufficient_evidence",
                started=started,
                rerank_ms=rerank_ms,
            )
        missing_entities = missing_comparison_entities(
            query,
            result.query.resolved_entities,
            sources,
        )
        if missing_entities:
            return self._abstain(
                result=result,
                reason=f"comparison_missing_evidence:{','.join(missing_entities)}",
                started=started,
                rerank_ms=rerank_ms,
            )
        conflicts = detect_conflicts(sources)
        subjective = any(source.subjective or source.source_kind == "guide" for source in sources)
        generation_started = perf_counter()
        raw_answer = self.llm.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_user_prompt(
                query,
                sources,
                conflicts=conflicts,
                subjective=subjective,
            ),
        )
        generation_ms = (perf_counter() - generation_started) * 1000.0
        try:
            citations = self.citation_validator.validate(
                raw_answer,
                sources,
                active_corpus_id=result.corpus.id,
            )
        except CitationValidationError as exc:
            return self._abstain(
                result=result,
                reason=f"citation_validation_failed:{exc}",
                started=started,
                rerank_ms=rerank_ms,
                generation_ms=generation_ms,
            )
        return GroundedAnswer(
            answer=raw_answer,
            citations=citations,
            resolved_entities=result.query.resolved_entities,
            confidence=result.confidence,
            abstained=False,
            abstention_reason=None,
            corpus_version=result.corpus.version,
            subjective_warning=subjective,
            conflicts=conflicts,
            latency_ms=AnswerLatency(
                supabase_retrieval=result.retrieval_latency_ms,
                rerank_and_context=rerank_ms,
                generation=generation_ms,
                total=(perf_counter() - started) * 1000.0,
            ),
        )

    @staticmethod
    def _abstain(
        *,
        result: RetrievalResult,
        reason: str,
        started: float,
        rerank_ms: float,
        generation_ms: float = 0.0,
    ) -> GroundedAnswer:
        return GroundedAnswer(
            answer=ABSTENTION_TEXT,
            citations=(),
            resolved_entities=result.query.resolved_entities,
            confidence="none",
            abstained=True,
            abstention_reason=reason,
            corpus_version=result.corpus.version,
            subjective_warning=False,
            conflicts=(),
            latency_ms=AnswerLatency(
                supabase_retrieval=result.retrieval_latency_ms,
                rerank_and_context=rerank_ms,
                generation=generation_ms,
                total=(perf_counter() - started) * 1000.0,
            ),
        )
