"""Embedding adapter and resumable worker tests."""

import math
from collections.abc import Sequence

import httpx
import pytest

from src.embeddings import (
    DeterministicHashEmbeddingAdapter,
    EmbeddingChunk,
    EmbeddingError,
    EmbeddingModelManifest,
    EmbeddingPreparation,
    EmbeddingRunReport,
    EmbeddingWorker,
    OllamaEmbeddingAdapter,
)


def _manifest(*, provider: str = "deterministic", batch_size: int = 2) -> EmbeddingModelManifest:
    return EmbeddingModelManifest(
        model_key=f"{provider}-test-1024-v1",
        provider=provider,  # type: ignore[arg-type]
        model_name="test-model",
        model_revision="v1",
        dimensions=1024,
        batch_size=batch_size,
    )


def test_deterministic_embeddings_are_stable_unit_length_and_dimensioned() -> None:
    adapter = DeterministicHashEmbeddingAdapter(_manifest())

    first, second = adapter.embed(["Football Helmet armor", "Football Helmet armor"])

    assert first == second
    assert len(first) == 1024
    assert math.isclose(math.sqrt(sum(value * value for value in first)), 1.0)


def test_ollama_adapter_rejects_wrong_dimensions() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[0.5, 0.5]]})

    client = httpx.Client(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    )
    adapter = OllamaEmbeddingAdapter(_manifest(provider="ollama"), client=client)

    with pytest.raises(EmbeddingError, match="dimension"):
        adapter.embed(["content"])

    client.close()


class FakeEmbeddingRepository:
    def __init__(self) -> None:
        self.chunks = (
            EmbeddingChunk(id="1", content="first", metadata={}),
            EmbeddingChunk(id="2", content="second", metadata={}),
            EmbeddingChunk(id="3", content="third", metadata={}),
        )
        self.stored: list[str] = []
        self.failed: list[str] = []
        self.report: EmbeddingRunReport | None = None

    def prepare_run(
        self,
        corpus_version: str,
        manifest: EmbeddingModelManifest,
    ) -> EmbeddingPreparation:
        assert corpus_version == "test-corpus"
        assert manifest.dimensions == 1024
        return EmbeddingPreparation(
            corpus_id="corpus-id",
            total_chunk_count=3,
            already_embedded_count=0,
            pending_chunks=self.chunks,
        )

    def store_embedding(
        self,
        chunk: EmbeddingChunk,
        vector: Sequence[float],
        model_key: str,
    ) -> None:
        assert len(vector) == 1024
        assert model_key
        self.stored.append(chunk.id)

    def record_embedding_error(
        self,
        chunk: EmbeddingChunk,
        error: str,
        model_key: str,
    ) -> None:
        assert error and model_key
        self.failed.append(chunk.id)

    def finish_run(self, report: EmbeddingRunReport) -> None:
        self.report = report


class FailSecondBatchAdapter:
    def __init__(self) -> None:
        self.manifest = _manifest(batch_size=2)
        self._calls = 0
        self._delegate = DeterministicHashEmbeddingAdapter(self.manifest)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self._calls += 1
        if self._calls == 2:
            raise EmbeddingError("fixture provider failure")
        return self._delegate.embed(texts)


def test_worker_records_partial_batch_failure_and_does_not_claim_success() -> None:
    repository = FakeEmbeddingRepository()

    report = EmbeddingWorker(repository, FailSecondBatchAdapter()).run("test-corpus")

    assert report.status == "partial"
    assert report.embedded_chunk_count == 2
    assert report.recorded_error_count == 1
    assert repository.stored == ["1", "2"]
    assert repository.failed == ["3"]
    assert repository.report == report
