"""FastAPI dependency providers."""

from apps.api.dependencies.services import (
    get_answer_service,
    get_chat_rate_limiter,
    get_knowledge_repository,
)

__all__ = ["get_answer_service", "get_chat_rate_limiter", "get_knowledge_repository"]
