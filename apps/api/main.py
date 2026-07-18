"""Minimal HTTP API for the Wiki chatbot."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.auto_ingest import WikiAutoIngestor
from src.config import Settings, get_settings
from src.embeddings.adapter import (
    DeterministicHashEmbeddingAdapter,
    EmbeddingError,
    OllamaEmbeddingAdapter,
)
from src.embeddings.models import EmbeddingModelManifest
from src.generation.llm import LLMError, create_llm_adapter
from src.rag import SimpleRAGService, SupabaseVectorStore, VectorStoreError
from src.wiki import WikiClient, WikiError


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class SourceResponse(BaseModel):
    title: str
    section: str
    url: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceResponse]


def _embedding(settings: Settings):
    manifest = EmbeddingModelManifest(
        model_key=f"{settings.embedding_model}-{settings.embedding_dimensions}",
        provider=settings.embedding_provider,
        model_name=settings.embedding_model,
        model_revision=settings.embedding_model_revision,
        dimensions=settings.embedding_dimensions,
        batch_size=settings.embedding_batch_size,
    )
    if settings.embedding_provider == "deterministic":
        return DeterministicHashEmbeddingAdapter(manifest)
    return OllamaEmbeddingAdapter(
        manifest,
        base_url=str(settings.embedding_base_url),
        timeout_seconds=settings.embedding_timeout_seconds,
    )


@lru_cache
def _build_rag_service() -> SimpleRAGService:
    settings = get_settings()
    if not settings.supabase_configured:
        raise ValueError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")
    if settings.supabase_api_key is None:
        raise ValueError("A Supabase server key is required")
    embedding = _embedding(settings)
    store = SupabaseVectorStore(
        base_url=str(settings.supabase_url),
        api_key=settings.supabase_api_key.get_secret_value(),
    )
    wiki = WikiClient(
        api_url=str(settings.wiki_api_url),
        base_url=str(settings.wiki_base_url),
        user_agent=settings.wiki_user_agent,
        timeout_seconds=settings.wiki_request_timeout_seconds,
    )
    auto_ingestor = (
        WikiAutoIngestor(
            wiki=wiki,
            embedding=embedding,
            store=store,
            max_pages=settings.auto_ingest_max_pages,
        )
        if settings.auto_ingest_enabled
        else None
    )
    return SimpleRAGService(
        embedding,
        store,
        create_llm_adapter(settings),
        auto_ingestor=auto_ingestor,
        match_count=min(settings.retrieval_match_count, 5),
        min_similarity=settings.min_evidence_score,
    )


def get_rag_service() -> SimpleRAGService:
    try:
        return _build_rag_service()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


app = FastAPI(title="DST Wiki Chatbot", version="1.0.0")


@app.get("/api/health")
def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, object]:
    llm_configured = (
        (settings.llm_provider == "deepseek" and settings.deepseek_api_key is not None)
        or (settings.llm_provider == "groq" and settings.groq_api_key is not None)
        or settings.llm_provider == "ollama"
    )
    ready = settings.supabase_configured and llm_configured
    return {
        "status": "ready" if ready else "not_configured",
        "llm": settings.llm_provider,
        "embedding": settings.embedding_model,
        "vector_store": "supabase",
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    service: Annotated[SimpleRAGService, Depends(get_rag_service)],
) -> ChatResponse:
    try:
        result = service.answer(request.message)
    except (EmbeddingError, VectorStoreError, LLMError, WikiError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ChatResponse(
        answer=result.answer,
        sources=[
            SourceResponse(title=source.title, section=source.section, url=source.url)
            for source in result.sources
        ],
    )


WEB_DIR = Path(__file__).resolve().parents[1] / "web"
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
