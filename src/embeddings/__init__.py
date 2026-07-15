"""Embedding adapters, validation, and resumable worker orchestration."""

from src.embeddings.adapter import (
    DeterministicHashEmbeddingAdapter,
    EmbeddingAdapter,
    EmbeddingError,
    OllamaEmbeddingAdapter,
    validate_embedding_batch,
)
from src.embeddings.models import (
    EmbeddingChunk,
    EmbeddingModelManifest,
    EmbeddingPreparation,
    EmbeddingRunReport,
)
from src.embeddings.worker import EmbeddingRepository, EmbeddingWorker

__all__ = [
    "DeterministicHashEmbeddingAdapter",
    "EmbeddingAdapter",
    "EmbeddingChunk",
    "EmbeddingError",
    "EmbeddingModelManifest",
    "EmbeddingPreparation",
    "EmbeddingRepository",
    "EmbeddingRunReport",
    "EmbeddingWorker",
    "OllamaEmbeddingAdapter",
    "validate_embedding_batch",
]
