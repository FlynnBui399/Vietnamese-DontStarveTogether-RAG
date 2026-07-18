"""HTTP contract tests for the small public API."""

import asyncio

import httpx

from apps.api.main import app, get_rag_service
from src.config import Settings, get_settings
from src.rag import AnswerSource, ChatAnswer


class FakeRAG:
    def answer(self, message):
        assert message == "Mũ da heo dùng để làm gì?"
        return ChatAnswer(
            answer="Football Helmet giúp giảm sát thương [S1].",
            sources=(
                AnswerSource(
                    title="Football Helmet",
                    section="Overview",
                    url="https://dontstarve.wiki.gg/wiki/Football_Helmet",
                ),
            ),
        )


def test_chat_endpoint_has_a_small_response_contract() -> None:
    app.dependency_overrides[get_rag_service] = FakeRAG

    async def request():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/api/chat",
                json={"message": "Mũ da heo dùng để làm gì?"},
            )

    try:
        response = asyncio.run(request())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Football Helmet giúp giảm sát thương [S1].",
        "sources": [
            {
                "title": "Football Helmet",
                "section": "Overview",
                "url": "https://dontstarve.wiki.gg/wiki/Football_Helmet",
            }
        ],
    }


def test_health_is_honest_when_secrets_are_missing() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)

    async def request():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/health")

    try:
        response = asyncio.run(request())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "not_configured"
