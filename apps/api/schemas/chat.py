"""Public request and response contracts for grounded chat."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatFilters(BaseModel):
    """MVP retrieval scope; non-DST content is never accepted."""

    game_scope: Literal["dst"] = "dst"


class ChatRequest(BaseModel):
    """One stateless user question."""

    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=100)
    filters: ChatFilters = Field(default_factory=ChatFilters)


class CitationResponse(BaseModel):
    """Evidence metadata displayed by citation cards and source drawers."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    chunk_id: str
    page_title: str
    section: str
    url: str
    revision_id: int
    retrieved_at: str | None
    corpus_version: str
    content: str
    source_kind: str
    subjective: bool


class ResolvedEntityResponse(BaseModel):
    """Alias-resolution decision exposed for user transparency."""

    model_config = ConfigDict(from_attributes=True)

    entity_title: str
    entity_slug: str
    matched_alias: str
    alias_type: str
    match_type: str
    verified: bool
    confidence: float


class ConflictResponse(BaseModel):
    """Structured source conflict surfaced rather than silently resolved."""

    model_config = ConfigDict(from_attributes=True)

    page_title: str
    field: str
    values: tuple[str, ...]
    source_ids: tuple[str, ...]


class LatencyResponse(BaseModel):
    """Measured pipeline timings in milliseconds."""

    model_config = ConfigDict(from_attributes=True)

    supabase_retrieval: float
    rerank_and_context: float
    generation: float
    total: float


class ChatResponse(BaseModel):
    """Validated answer contract consumed by the web application."""

    model_config = ConfigDict(from_attributes=True)

    answer: str
    citations: tuple[CitationResponse, ...]
    resolved_entities: tuple[ResolvedEntityResponse, ...]
    confidence: Literal["high", "medium", "low", "none"]
    abstained: bool
    abstention_reason: str | None
    corpus_version: str | None
    subjective_warning: bool
    conflicts: tuple[ConflictResponse, ...]
    latency_ms: LatencyResponse
