"""Focused tests for the only chat path used by the MVP."""

import json

import httpx

from src.rag import (
    INVALID_ANSWER,
    NO_EVIDENCE_ANSWER,
    SimpleRAGService,
    SupabaseVectorStore,
    WikiChunk,
)


class FakeEmbedding:
    def embed(self, texts):
        assert texts
        return [[1.0, 0.0]]


class FakeStore:
    def __init__(self, chunks):
        self.chunks = chunks
        self.calls = 0

    def search(self, query_embedding, *, match_count, min_similarity):
        self.calls += 1
        assert query_embedding == [1.0, 0.0]
        assert match_count == 5
        assert min_similarity == 0.2
        return self.chunks

    def replace_page(self, page_title, rows):
        raise AssertionError("replace_page should not be called in this test")


class BackfillStore(FakeStore):
    def search(self, query_embedding, *, match_count, min_similarity):
        self.calls += 1
        if self.calls == 1:
            return []
        return self.chunks


class FakeAutoIngestor:
    def __init__(self):
        self.queries = []

    def ingest_for_query(self, query):
        self.queries.append(query)
        return 1


class FakeLLM:
    def __init__(self, answer):
        self.answer = answer
        self.calls = 0

    def generate(self, *, system_prompt, user_prompt):
        self.calls += 1
        assert "Chỉ sử dụng" in system_prompt
        assert "<SOURCE_CONTENT>" in user_prompt
        return self.answer


def _chunk():
    return WikiChunk(
        id="chunk-1",
        page_title="Football Helmet",
        section="Overview",
        content="Football Helmet absorbs damage.",
        url="https://dontstarve.wiki.gg/wiki/Football_Helmet",
        similarity=0.9,
    )


def test_answer_returns_only_sources_cited_by_the_llm() -> None:
    service = SimpleRAGService(
        FakeEmbedding(), FakeStore([_chunk()]), FakeLLM("Nó hấp thụ sát thương [S1].")
    )

    result = service.answer("Football Helmet có tác dụng gì?")

    assert result.answer.endswith("[S1].")
    assert result.sources[0].title == "Football Helmet"


def test_no_evidence_does_not_call_the_llm() -> None:
    llm = FakeLLM("should not be called")
    service = SimpleRAGService(FakeEmbedding(), FakeStore([]), llm)

    result = service.answer("unknown item")

    assert result.answer == NO_EVIDENCE_ANSWER
    assert result.sources == ()
    assert llm.calls == 0


def test_no_evidence_can_auto_ingest_and_retry_search() -> None:
    llm = FakeLLM("NÃ³ háº¥p thá»¥ sÃ¡t thÆ°Æ¡ng [S1].")
    store = BackfillStore([_chunk()])
    auto_ingestor = FakeAutoIngestor()
    service = SimpleRAGService(
        FakeEmbedding(),
        store,
        llm,
        auto_ingestor=auto_ingestor,
    )

    result = service.answer("Football Helmet cÃ³ tÃ¡c dá»¥ng gÃ¬?")

    assert auto_ingestor.queries == ["Football Helmet cÃ³ tÃ¡c dá»¥ng gÃ¬?"]
    assert store.calls == 2
    assert result.sources[0].title == "Football Helmet"


def test_uncited_answer_is_not_exposed() -> None:
    service = SimpleRAGService(
        FakeEmbedding(), FakeStore([_chunk()]), FakeLLM("Một câu không có nguồn.")
    )

    result = service.answer("question")

    assert result.answer == INVALID_ANSWER
    assert result.sources == ()


def test_supabase_store_calls_the_single_vector_rpc() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/v1/rpc/match_wiki_chunks"
        assert json.loads(request.read()) == {
            "query_embedding": [1.0, 0.0],
            "match_count": 5,
            "min_similarity": 0.2,
        }
        return httpx.Response(
            200,
            json=[
                {
                    "id": "chunk-1",
                    "page_title": "Football Helmet",
                    "section": "Overview",
                    "content": "Evidence",
                    "url": "https://example.invalid/wiki/Football_Helmet",
                    "similarity": 0.9,
                }
            ],
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://project.supabase.co",
    )
    store = SupabaseVectorStore(
        base_url="https://project.supabase.co",
        api_key="server-key",
        client=client,
    )

    result = store.search([1.0, 0.0], match_count=5, min_similarity=0.2)

    assert result[0].page_title == "Football Helmet"
