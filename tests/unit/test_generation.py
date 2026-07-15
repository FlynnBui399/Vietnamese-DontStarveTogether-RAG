"""Grounded generation, citation, conflict, and abstention tests."""

from __future__ import annotations

from typing import cast

import httpx

from src.generation import GroundedAnswerService, OllamaLLMAdapter
from src.generation.guardrails import detect_conflicts
from src.generation.llm import LLMAdapter
from src.generation.models import EvidenceSource
from src.retrieval import (
    ActiveCorpus,
    ContextAssembly,
    ContextBlock,
    HybridCandidate,
    RetrievalResult,
    RetrievalService,
)
from src.terminology.models import ExpandedQuery, NormalizedQuery, ResolvedEntity


class FakeLLM:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls = 0

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        assert "Chỉ sử dụng" in system_prompt
        assert "<SOURCE_CONTENT>" in user_prompt
        return self.answer


class FakeRetrievalService:
    def __init__(self, result: RetrievalResult) -> None:
        self.result = result

    def retrieve(self, query: str, *, match_count: int = 10) -> RetrievalResult:
        assert query.strip()
        assert match_count == 8
        return self.result


def _entity(title: str) -> ResolvedEntity:
    return ResolvedEntity(
        entity_title=title,
        entity_slug=title.casefold().replace(" ", "-"),
        matched_alias=title,
        alias_type="official_title",
        match_type="exact_title",
        verified=True,
        confidence=1.0,
        score=4101.0,
    )


def _candidate(
    chunk_id: str = "chunk-1",
    *,
    title: str = "Football Helmet",
    content: str = "Football Helmet absorbs 80% of incoming damage.",
    subjective: bool = False,
) -> HybridCandidate:
    return HybridCandidate(
        chunk_id=chunk_id,
        corpus_version_id="active-id",
        page_title=title,
        section_path="Overview",
        content=content,
        content_hash=f"hash-{chunk_id}",
        token_count=12,
        game_scope="dst",
        entity_type="armor",
        source_kind="guide" if subjective else "factual_article",
        subjective=subjective,
        canonical_url=f"https://dontstarve.wiki.gg/wiki/{title.replace(' ', '_')}",
        revision_id=123,
        metadata={"retrieved_at": "2026-07-15T00:00:00Z"},
        lexical_rank=1,
        semantic_rank=1,
        cosine_similarity=0.9,
        rrf_score=0.03,
        rerank_score=0.8,
    )


def _result(
    candidates: tuple[HybridCandidate, ...],
    *,
    entities: tuple[ResolvedEntity, ...] = (),
) -> RetrievalResult:
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
        for index, candidate in enumerate(candidates, start=1)
    )
    return RetrievalResult(
        query=ExpandedQuery(
            query=NormalizedQuery(
                original="query",
                normalized="query",
                search_normalized="query",
                language="en",
            ),
            resolved_entities=entities,
            terms=("query",),
        ),
        corpus=ActiveCorpus(
            id="active-id",
            version="active-v1",
            embedding_model_key="model",
        ),
        candidates=candidates,
        context=ContextAssembly(
            blocks=blocks,
            token_count=sum(block.token_count for block in blocks),
            token_budget=1800,
        ),
        confidence="high" if candidates else "none",
        retrieval_latency_ms=10.0,
        total_latency_ms=12.0,
    )


def _service(result: RetrievalResult, llm: FakeLLM) -> GroundedAnswerService:
    retrieval = cast(RetrievalService, FakeRetrievalService(result))
    return GroundedAnswerService(retrieval, cast(LLMAdapter, llm))


def test_grounded_answer_returns_only_validated_active_corpus_citations() -> None:
    llm = FakeLLM("Football Helmet hấp thụ 80% sát thương nhận vào [S1].")

    answer = _service(_result((_candidate(),)), llm).answer("Football Helmet bảo vệ ra sao?")

    assert not answer.abstained
    assert [citation.id for citation in answer.citations] == ["S1"]
    assert answer.citations[0].corpus_version == "active-v1"
    assert answer.citations[0].revision_id == 123


def test_fake_or_uncited_llm_output_is_replaced_with_abstention() -> None:
    llm = FakeLLM("Football Helmet hấp thụ 80% sát thương nhận vào [S9].")

    answer = _service(_result((_candidate(),)), llm).answer("Football Helmet bảo vệ ra sao?")

    assert answer.abstained
    assert answer.citations == ()
    assert answer.abstention_reason is not None
    assert answer.abstention_reason.startswith("citation_validation_failed")


def test_no_evidence_and_incomplete_comparison_abstain_before_llm() -> None:
    no_evidence_llm = FakeLLM("should not be used")
    no_evidence = _service(_result(()), no_evidence_llm).answer("Unknown mod item")
    assert no_evidence.abstained
    assert no_evidence_llm.calls == 0

    comparison_llm = FakeLLM("should not be used")
    comparison = _service(
        _result(
            (_candidate(),),
            entities=(_entity("Football Helmet"), _entity("Log Suit")),
        ),
        comparison_llm,
    ).answer("So sánh Football Helmet và Log Suit")
    assert comparison.abstained
    assert comparison.abstention_reason == "comparison_missing_evidence:Log Suit"
    assert comparison_llm.calls == 0


def test_conflicting_structured_values_are_detected_with_both_sources() -> None:
    sources = (
        EvidenceSource(
            id="S1",
            chunk_id="one",
            corpus_version_id="active-id",
            corpus_version="v1",
            page_title="Item",
            section="Stats",
            url="https://example.invalid/one",
            revision_id=1,
            content="Damage: 10",
            source_kind="factual_article",
            subjective=False,
        ),
        EvidenceSource(
            id="S2",
            chunk_id="two",
            corpus_version_id="active-id",
            corpus_version="v1",
            page_title="Item",
            section="Stats",
            url="https://example.invalid/two",
            revision_id=2,
            content="Damage: 20",
            source_kind="factual_article",
            subjective=False,
        ),
    )

    conflicts = detect_conflicts(sources)

    assert conflicts[0].values == ("10", "20")
    assert conflicts[0].source_ids == ("S1", "S2")


def test_ollama_adapter_sends_grounded_non_streaming_chat_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = request.read().decode()
        assert '"stream":false' in payload
        assert '"temperature":0.1' in payload
        return httpx.Response(200, json={"message": {"content": "Câu trả lời [S1]."}})

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://ollama.invalid",
    )
    adapter = OllamaLLMAdapter(model="test-model", client=client)

    assert adapter.generate(system_prompt="system", user_prompt="user") == "Câu trả lời [S1]."
