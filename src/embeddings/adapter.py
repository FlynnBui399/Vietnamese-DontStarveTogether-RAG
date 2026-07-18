"""Configurable Ollama embeddings plus an explicit deterministic test adapter."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from typing import Any, Protocol

import httpx

from src.embeddings.models import EmbeddingModelManifest
from src.terminology.normalizer import normalize_search_text


class EmbeddingError(RuntimeError):
    """Raised when an embedding provider violates its configured contract."""


class EmbeddingAdapter(Protocol):
    """Minimal provider-independent batch embedding contract."""

    @property
    def manifest(self) -> EmbeddingModelManifest: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class OllamaEmbeddingAdapter:
    """Call Ollama's batch `/api/embed` endpoint without silent truncation."""

    def __init__(
        self,
        manifest: EmbeddingModelManifest,
        *,
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: float = 120.0,
        client: httpx.Client | None = None,
    ) -> None:
        if manifest.provider != "ollama":
            raise ValueError("Ollama adapter requires an ollama manifest")
        self._manifest = manifest
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_seconds
        )

    @property
    def manifest(self) -> EmbeddingModelManifest:
        return self._manifest

    def close(self) -> None:
        """Close the internally owned HTTP client."""
        if self._owns_client:
            self._client.close()

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Generate and validate one provider batch."""
        if not texts:
            return []
        if any(not text.strip() for text in texts):
            raise EmbeddingError("Embedding input cannot be empty")
        try:
            response = self._client.post(
                "/api/embed",
                json={
                    "model": self.manifest.model_name,
                    "input": list(texts),
                    "truncate": False,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmbeddingError("Ollama embedding request failed") from exc
        payload = response.json()
        if not isinstance(payload, dict):
            raise EmbeddingError("Ollama returned a non-object response")
        raw_embeddings = payload.get("embeddings")
        if not isinstance(raw_embeddings, list):
            raise EmbeddingError("Ollama response has no embeddings array")
        vectors = [self._coerce_vector(value) for value in raw_embeddings]
        validate_embedding_batch(vectors, len(texts), self.manifest)
        return vectors

    @staticmethod
    def _coerce_vector(value: Any) -> list[float]:
        if not isinstance(value, list):
            raise EmbeddingError("Ollama returned a non-array embedding")
        try:
            return [float(component) for component in value]
        except (TypeError, ValueError) as exc:
            raise EmbeddingError("Ollama returned a non-numeric embedding") from exc


class DeterministicHashEmbeddingAdapter:
    """Dependency-free lexical hash embeddings for tests and local acceptance only."""

    def __init__(self, manifest: EmbeddingModelManifest) -> None:
        if manifest.provider != "deterministic":
            raise ValueError("Deterministic adapter requires a deterministic manifest")
        self._manifest = manifest

    @property
    def manifest(self) -> EmbeddingModelManifest:
        return self._manifest

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Create stable unit vectors from normalized unigrams and bigrams."""
        vectors = [self._embed_one(text) for text in texts]
        validate_embedding_batch(vectors, len(texts), self.manifest)
        return vectors

    def _embed_one(self, text: str) -> list[float]:
        tokens = normalize_search_text(text).split()
        if not tokens:
            raise EmbeddingError("Embedding input cannot be empty")
        vector = [0.0] * self.manifest.dimensions
        features = [(token, 1.0) for token in tokens]
        features.extend(
            (f"{left}_{right}", 0.5) for left, right in zip(tokens, tokens[1:], strict=False)
        )
        for feature, weight in features:
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.manifest.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign * weight
        norm = math.sqrt(sum(component * component for component in vector))
        if norm == 0.0:
            raise EmbeddingError("Embedding input produced a zero vector")
        return [component / norm for component in vector]


def validate_embedding_batch(
    vectors: Sequence[Sequence[float]],
    expected_count: int,
    manifest: EmbeddingModelManifest,
) -> None:
    """Reject partial, non-finite, wrong-dimension, or non-normalized provider output."""
    if len(vectors) != expected_count:
        raise EmbeddingError(
            f"Embedding provider returned {len(vectors)} vectors for {expected_count} inputs"
        )
    for vector in vectors:
        if len(vector) != manifest.dimensions:
            raise EmbeddingError(
                f"Embedding dimension {len(vector)} does not match {manifest.dimensions}"
            )
        if any(not math.isfinite(component) for component in vector):
            raise EmbeddingError("Embedding contains a non-finite value")
        if manifest.normalized:
            norm = math.sqrt(sum(component * component for component in vector))
            if not math.isclose(norm, 1.0, rel_tol=0.05, abs_tol=0.05):
                raise EmbeddingError(f"Embedding norm {norm:.4f} is not unit length")
