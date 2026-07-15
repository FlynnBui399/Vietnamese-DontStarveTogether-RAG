"""Grounded chat endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.dependencies import get_answer_service
from apps.api.schemas import ChatRequest, ChatResponse
from src.generation import GroundedAnswerService

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    service: Annotated[GroundedAnswerService, Depends(get_answer_service)],
) -> ChatResponse:
    """Answer from active DST evidence or fail safely with a public service error."""
    try:
        result = service.answer(request.message)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The answer service is temporarily unavailable.",
        ) from exc
    return ChatResponse.model_validate(result)
