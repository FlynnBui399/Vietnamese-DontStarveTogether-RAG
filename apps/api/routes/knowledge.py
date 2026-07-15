"""Public corpus status, autocomplete, entity, and evidence endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from apps.api.dependencies import get_knowledge_repository
from apps.api.schemas import (
    CorpusStatusResponse,
    EntityDetailResponse,
    EntitySearchResponse,
    SourceDetailResponse,
)
from src.supabase_store import SupabaseKnowledgeError, SupabaseKnowledgeRepository

router = APIRouter(tags=["knowledge"])


def _unavailable(exc: SupabaseKnowledgeError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="The knowledge service is temporarily unavailable.",
    )


@router.get("/corpus/status", response_model=CorpusStatusResponse)
def corpus_status(
    repository: Annotated[SupabaseKnowledgeRepository, Depends(get_knowledge_repository)],
) -> CorpusStatusResponse:
    """Return non-secret active corpus status for the web header."""
    try:
        result = repository.get_corpus_status()
    except SupabaseKnowledgeError as exc:
        raise _unavailable(exc) from exc
    return CorpusStatusResponse.model_validate(result)


@router.get("/search", response_model=EntitySearchResponse)
def search_entities(
    repository: Annotated[SupabaseKnowledgeRepository, Depends(get_knowledge_repository)],
    query: Annotated[str, Query(alias="q", min_length=2, max_length=100)],
    limit: Annotated[int, Query(ge=1, le=12)] = 8,
) -> EntitySearchResponse:
    """Autocomplete canonical entities from stored aliases."""
    try:
        results = repository.search_entities(query, limit=limit)
    except SupabaseKnowledgeError as exc:
        raise _unavailable(exc) from exc
    return EntitySearchResponse(results=results)


@router.get("/entities/{slug}", response_model=EntityDetailResponse)
def entity_detail(
    repository: Annotated[SupabaseKnowledgeRepository, Depends(get_knowledge_repository)],
    slug: Annotated[str, Path(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)],
) -> EntityDetailResponse:
    """Return one entity only when its evidence is in the active corpus."""
    try:
        result = repository.get_entity(slug)
    except SupabaseKnowledgeError as exc:
        raise _unavailable(exc) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found.")
    return EntityDetailResponse.model_validate(result)


@router.get("/sources/{chunk_id}", response_model=SourceDetailResponse)
def source_detail(
    repository: Annotated[SupabaseKnowledgeRepository, Depends(get_knowledge_repository)],
    chunk_id: UUID,
) -> SourceDetailResponse:
    """Return exact evidence only from an active or archived corpus."""
    try:
        result = repository.get_source(str(chunk_id))
    except SupabaseKnowledgeError as exc:
        raise _unavailable(exc) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
    return SourceDetailResponse.model_validate(result)
