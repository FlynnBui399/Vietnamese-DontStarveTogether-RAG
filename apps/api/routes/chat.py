"""Grounded chat endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from apps.api.dependencies import get_answer_service, get_chat_rate_limiter
from apps.api.schemas import ChatRequest, ChatResponse
from src.generation import GroundedAnswerService
from src.security import SlidingWindowRateLimiter

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    service: Annotated[GroundedAnswerService, Depends(get_answer_service)],
    http_request: Request,
    rate_limiter: Annotated[SlidingWindowRateLimiter, Depends(get_chat_rate_limiter)],
) -> ChatResponse:
    """Answer from active DST evidence or fail safely with a public service error."""
    client_key = http_request.client.host if http_request.client is not None else "unknown"
    retry_after = rate_limiter.check(client_key)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many chat requests. Please retry shortly.",
            headers={"Retry-After": str(max(1, round(retry_after)))},
        )
    try:
        result = service.answer(request.message)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The answer service is temporarily unavailable.",
        ) from exc
    return ChatResponse.model_validate(result)
