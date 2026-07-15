"""Structured chat API contract tests without external services."""

import asyncio
from typing import cast

import httpx

from apps.api.dependencies import get_answer_service
from apps.api.main import app
from src.generation import AnswerLatency, GroundedAnswer, GroundedAnswerService


class FakeAnswerService:
    def answer(self, query: str) -> GroundedAnswer:
        assert query == "mu da heo"
        return GroundedAnswer(
            answer="Chưa có đủ bằng chứng.",
            citations=(),
            resolved_entities=(),
            confidence="none",
            abstained=True,
            abstention_reason="insufficient_evidence",
            corpus_version="v1",
            subjective_warning=False,
            conflicts=(),
            latency_ms=AnswerLatency(
                supabase_retrieval=1.0,
                rerank_and_context=2.0,
                generation=0.0,
                total=3.0,
            ),
        )


def _fake_service() -> GroundedAnswerService:
    return cast(GroundedAnswerService, FakeAnswerService())


def test_chat_endpoint_returns_structured_abstention() -> None:
    app.dependency_overrides[get_answer_service] = _fake_service

    async def request_chat() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/api/chat",
                json={"message": "mu da heo", "filters": {"game_scope": "dst"}},
            )

    try:
        response = asyncio.run(request_chat())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Chưa có đủ bằng chứng.",
        "citations": [],
        "resolved_entities": [],
        "confidence": "none",
        "abstained": True,
        "abstention_reason": "insufficient_evidence",
        "corpus_version": "v1",
        "subjective_warning": False,
        "conflicts": [],
        "latency_ms": {
            "supabase_retrieval": 1.0,
            "rerank_and_context": 2.0,
            "generation": 0.0,
            "total": 3.0,
        },
    }
