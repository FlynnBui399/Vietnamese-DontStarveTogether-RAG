"""Provider-independent LLM contract and Ollama implementation."""

from __future__ import annotations

from typing import Any, Protocol

import httpx


class LLMError(RuntimeError):
    """Raised when a generation provider is unavailable or returns invalid output."""


class LLMAdapter(Protocol):
    """Small generation boundary independent from retrieval and persistence."""

    def generate(self, *, system_prompt: str, user_prompt: str) -> str: ...


class OllamaLLMAdapter:
    """Generate one non-streaming answer through Ollama's chat endpoint."""

    def __init__(
        self,
        *,
        model: str,
        base_url: str = "http://127.0.0.1:11434",
        temperature: float = 0.1,
        timeout_seconds: float = 120.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not model.strip():
            raise ValueError("LLM model is required")
        if not 0.0 <= temperature <= 1.0:
            raise ValueError("LLM temperature must be in [0, 1]")
        self.model = model
        self.temperature = temperature
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_seconds
        )

    def close(self) -> None:
        """Close the internally owned HTTP client."""
        if self._owns_client:
            self._client.close()

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return validated text from one Ollama response."""
        try:
            response = self._client.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "options": {"temperature": self.temperature},
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMError("Ollama generation request failed") from exc
        payload: Any = response.json()
        if not isinstance(payload, dict):
            raise LLMError("Ollama returned a non-object response")
        message = payload.get("message")
        if not isinstance(message, dict):
            raise LLMError("Ollama response has no message object")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LLMError("Ollama returned an empty answer")
        return content.strip()
