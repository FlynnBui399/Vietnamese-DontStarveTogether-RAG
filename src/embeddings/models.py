"""Typed embedding model, chunk, and run records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EmbeddingProvider = Literal["ollama", "deterministic"]
EmbeddingRunStatus = Literal["passed", "partial", "failed"]


@dataclass(frozen=True, slots=True)
class EmbeddingModelManifest:
    """Immutable identity and runtime contract for one embedding model."""

    model_key: str
    provider: EmbeddingProvider
    model_name: str
    model_revision: str
    dimensions: int
    distance_metric: Literal["cosine"] = "cosine"
    normalized: bool = True
    batch_size: int = 16

    def __post_init__(self) -> None:
        if not self.model_key.strip() or not self.model_name.strip():
            raise ValueError("Embedding model key and name are required")
        if self.dimensions <= 0 or self.batch_size <= 0:
            raise ValueError("Embedding dimensions and batch size must be positive")

    def to_dict(self) -> dict[str, object]:
        return {
            "model_key": self.model_key,
            "provider": self.provider,
            "model_name": self.model_name,
            "model_revision": self.model_revision,
            "dimensions": self.dimensions,
            "distance_metric": self.distance_metric,
            "normalized": self.normalized,
            "batch_size": self.batch_size,
        }


@dataclass(frozen=True, slots=True)
class EmbeddingChunk:
    """One corpus chunk awaiting an embedding."""

    id: str
    content: str
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class EmbeddingPreparation:
    """Corpus state at the start of a resumable embedding run."""

    corpus_id: str
    total_chunk_count: int
    already_embedded_count: int
    pending_chunks: tuple[EmbeddingChunk, ...]


@dataclass(frozen=True, slots=True)
class EmbeddingRunReport:
    """Honest outcome for a complete or partial embedding attempt."""

    corpus_id: str
    corpus_version: str
    model_key: str
    status: EmbeddingRunStatus
    total_chunk_count: int
    embedded_chunk_count: int
    new_embedding_count: int
    recorded_error_count: int
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "corpus_id": self.corpus_id,
            "corpus_version": self.corpus_version,
            "model_key": self.model_key,
            "status": self.status,
            "total_chunk_count": self.total_chunk_count,
            "embedded_chunk_count": self.embedded_chunk_count,
            "new_embedding_count": self.new_embedding_count,
            "recorded_error_count": self.recorded_error_count,
            "errors": list(self.errors),
        }
