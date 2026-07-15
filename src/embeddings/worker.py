"""Resumable batch embedding orchestration with per-chunk error recording."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from src.embeddings.adapter import EmbeddingAdapter
from src.embeddings.models import (
    EmbeddingChunk,
    EmbeddingModelManifest,
    EmbeddingPreparation,
    EmbeddingRunReport,
    EmbeddingRunStatus,
)


class EmbeddingRepository(Protocol):
    """Persistence boundary used by the embedding worker."""

    def prepare_run(
        self,
        corpus_version: str,
        manifest: EmbeddingModelManifest,
    ) -> EmbeddingPreparation: ...

    def store_embedding(
        self,
        chunk: EmbeddingChunk,
        vector: Sequence[float],
        model_key: str,
    ) -> None: ...

    def record_embedding_error(
        self,
        chunk: EmbeddingChunk,
        error: str,
        model_key: str,
    ) -> None: ...

    def finish_run(self, report: EmbeddingRunReport) -> None: ...


class EmbeddingWorker:
    """Embed every missing chunk and leave an explicit success or error state."""

    def __init__(self, repository: EmbeddingRepository, adapter: EmbeddingAdapter) -> None:
        self.repository = repository
        self.adapter = adapter

    def run(self, corpus_version: str) -> EmbeddingRunReport:
        """Run a resumable embedding pass without activating the corpus."""
        manifest = self.adapter.manifest
        preparation = self.repository.prepare_run(corpus_version, manifest)
        new_embedding_count = 0
        recorded_error_count = 0
        errors: list[str] = []
        chunks = preparation.pending_chunks
        for offset in range(0, len(chunks), manifest.batch_size):
            batch = chunks[offset : offset + manifest.batch_size]
            try:
                vectors = self.adapter.embed([chunk.content for chunk in batch])
            except Exception as exc:
                message = self._error_message(exc)
                errors.append(message)
                for chunk in batch:
                    self.repository.record_embedding_error(chunk, message, manifest.model_key)
                    recorded_error_count += 1
                continue
            for chunk, vector in zip(batch, vectors, strict=True):
                try:
                    self.repository.store_embedding(chunk, vector, manifest.model_key)
                    new_embedding_count += 1
                except Exception as exc:
                    message = self._error_message(exc)
                    errors.append(message)
                    self.repository.record_embedding_error(chunk, message, manifest.model_key)
                    recorded_error_count += 1

        embedded_chunk_count = preparation.already_embedded_count + new_embedding_count
        status: EmbeddingRunStatus
        if embedded_chunk_count == preparation.total_chunk_count:
            status = "passed"
        elif embedded_chunk_count > 0:
            status = "partial"
        else:
            status = "failed"
        report = EmbeddingRunReport(
            corpus_id=preparation.corpus_id,
            corpus_version=corpus_version,
            model_key=manifest.model_key,
            status=status,
            total_chunk_count=preparation.total_chunk_count,
            embedded_chunk_count=embedded_chunk_count,
            new_embedding_count=new_embedding_count,
            recorded_error_count=recorded_error_count,
            errors=tuple(dict.fromkeys(errors)),
        )
        self.repository.finish_run(report)
        return report

    @staticmethod
    def _error_message(exc: Exception) -> str:
        detail = str(exc).strip() or type(exc).__name__
        return f"{type(exc).__name__}: {detail}"[:500]
