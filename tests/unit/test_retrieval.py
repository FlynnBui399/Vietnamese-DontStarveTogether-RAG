"""Hybrid retrieval filtering, reranking, deduplication, and context tests."""

from collections.abc import Sequence

import pytest

from src.embeddings import DeterministicHashEmbeddingAdapter, EmbeddingModelManifest
from src.evaluation import RetrievalEvaluationDataset
from src.retrieval import ActiveCorpus, ContextAssembler, HybridCandidate, RetrievalService
from src.terminology import AliasResolver, Glossary, QueryExpander


def _manifest(model_key: str = "deterministic-hash-1024-v1") -> EmbeddingModelManifest:
    return EmbeddingModelManifest(
        model_key=model_key,
        provider="deterministic",
        model_name="deterministic-hash",
        model_revision="1",
        dimensions=1024,
    )


def _candidate(
    chunk_id: str,
    *,
    title: str,
    scope: str = "dst",
    body_hash: str,
    rrf_score: float = 0.04,
    similarity: float = 0.8,
) -> HybridCandidate:
    return HybridCandidate(
        chunk_id=chunk_id,
        corpus_version_id="active-id",
        page_title=title,
        section_path="Overview",
        content=f"Page: {title}\nSection: Overview\n{title} factual content",
        content_hash=f"content-{chunk_id}",
        token_count=20,
        game_scope=scope,
        entity_type="armor",
        source_kind="factual_article",
        subjective=False,
        canonical_url=f"https://example.invalid/{chunk_id}",
        revision_id=1,
        metadata={"body_hash": body_hash},
        lexical_rank=1,
        semantic_rank=1,
        cosine_similarity=similarity,
        rrf_score=rrf_score,
    )


class FakeRetrievalRepository:
    def __init__(self, model_key: str = "deterministic-hash-1024-v1") -> None:
        self.model_key = model_key

    def get_active_corpus(self) -> ActiveCorpus:
        return ActiveCorpus(
            id="active-id",
            version="active-v1",
            embedding_model_key=self.model_key,
        )

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
    ) -> list[HybridCandidate]:
        assert "Football Helmet" in query_text
        assert len(query_embedding) == 1024
        assert match_count >= 30 and lexical_count == semantic_count == 40
        assert filter_entity_type is None
        assert entity_titles[0] == "Football Helmet"
        assert section_intent is None
        return [
            _candidate("good", title="Football Helmet", body_hash="same"),
            _candidate("duplicate", title="Football Helmet", body_hash="same"),
            _candidate("mixed", title="Wrong Scope", scope="mixed", body_hash="mixed"),
            _candidate(
                "weak",
                title="Unrelated",
                body_hash="weak",
                rrf_score=0.001,
                similarity=0.0,
            ),
        ]


def test_retrieval_filters_scope_threshold_and_duplicates_before_context() -> None:
    adapter = DeterministicHashEmbeddingAdapter(_manifest())
    service = RetrievalService(
        FakeRetrievalRepository(),
        adapter,
        QueryExpander(AliasResolver(Glossary.load().records)),
    )

    result = service.retrieve("mu da heo")

    assert [candidate.chunk_id for candidate in result.candidates] == ["good"]
    assert result.context.blocks[0].context_id == "CTX-1"
    assert result.context.blocks[0].page_title == "Football Helmet"
    assert result.context.token_count <= result.context.token_budget


def test_retrieval_rejects_query_adapter_that_does_not_match_active_corpus() -> None:
    service = RetrievalService(
        FakeRetrievalRepository(model_key="different-model"),
        DeterministicHashEmbeddingAdapter(_manifest()),
        QueryExpander(AliasResolver(Glossary.load().records)),
    )

    with pytest.raises(RuntimeError, match="does not match"):
        service.retrieve("Football Helmet")


def test_milestone_evaluation_dataset_has_both_required_query_groups() -> None:
    dataset = RetrievalEvaluationDataset.load()

    assert sum(case.category == "entity" for case in dataset.cases) >= 10
    assert sum(case.category == "natural" for case in dataset.cases) >= 10
    assert dataset.target_entity_recall_at_5 == 0.9
    assert dataset.target_natural_recall_at_10 == 0.85


def test_section_intent_and_context_per_section_limits_are_deterministic() -> None:
    candidates = [
        _candidate(str(index), title="Same Page", body_hash=str(index)) for index in range(3)
    ]

    context = ContextAssembler(max_per_section=2).assemble(candidates)

    assert RetrievalService._section_intent("cach lam vat pham") == "craft"
    assert [block.context_id for block in context.blocks] == ["CTX-1", "CTX-2"]
