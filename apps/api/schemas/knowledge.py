"""Public-safe corpus, entity, and source response contracts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CorpusStatusResponse(BaseModel):
    """Corpus metadata that contains no operational secret."""

    model_config = ConfigDict(from_attributes=True)

    available: bool
    version: str | None
    page_count: int
    chunk_count: int
    embedding_model: str | None
    activated_at: str | None
    last_sync_at: str | None


class EntitySearchItem(BaseModel):
    """One canonical entity autocomplete match."""

    model_config = ConfigDict(from_attributes=True)

    title: str
    slug: str
    matched_alias: str
    alias_type: str
    verified: bool


class EntitySearchResponse(BaseModel):
    """Bounded autocomplete results."""

    results: tuple[EntitySearchItem, ...]


class EntityDetailResponse(BaseModel):
    """Summary of an entity present in the active corpus."""

    model_config = ConfigDict(from_attributes=True)

    title: str
    slug: str
    entity_type: str | None
    summary: str
    aliases: tuple[str, ...]
    source_chunk_id: str
    source_url: str
    corpus_version: str


class SourceDetailResponse(BaseModel):
    """Exact evidence from an active or archived corpus."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    page_title: str
    section: str
    content: str
    url: str
    revision_id: int
    source_kind: str
    subjective: bool
    corpus_version: str
    corpus_status: str
