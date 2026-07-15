"""Structured chat API contract tests without external services."""

import asyncio
from typing import cast

import httpx

from apps.api.dependencies import get_answer_service, get_chat_rate_limiter
from apps.api.main import app
from src.generation import AnswerLatency, GroundedAnswer, GroundedAnswerService
from src.security import SlidingWindowRateLimiter


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
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
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


def test_chat_endpoint_rate_limit_returns_retry_after() -> None:
    limiter = SlidingWindowRateLimiter(1)
    app.dependency_overrides[get_answer_service] = _fake_service
    app.dependency_overrides[get_chat_rate_limiter] = lambda: limiter

    async def request_twice() -> tuple[httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {"message": "mu da heo", "filters": {"game_scope": "dst"}}
            return (
                await client.post("/api/chat", json=payload),
                await client.post("/api/chat", json=payload),
            )

    try:
        first, second = asyncio.run(request_twice())
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 429
    assert int(second.headers["retry-after"]) >= 1
