"""Provider-independent LLM contract with DeepSeek and Ollama implementations."""

from __future__ import annotations

import logging
from typing import Any, Protocol

import httpx

from src.config import Settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised when a generation provider is unavailable or returns invalid output."""


class LLMAdapter(Protocol):
    """Small generation boundary independent from retrieval and persistence."""

    def generate(self, *, system_prompt: str, user_prompt: str) -> str: ...


def _log_provider_http_error(provider: str, exc: httpx.HTTPError) -> None:
    """Log upstream response details without exposing request headers or API keys."""
    if isinstance(exc, httpx.HTTPStatusError):
        logger.error(
            "%s generation failed with HTTP %s: %s",
            provider,
            exc.response.status_code,
            exc.response.text[:1000],
        )
        return
    logger.error("%s generation request failed: %s", provider, exc)


class DeepSeekLLMAdapter:
    """Generate one non-thinking response through DeepSeek's chat API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "deepseek-v4-flash",
        base_url: str = "https://api.deepseek.com",
        temperature: float = 0.1,
        max_output_tokens: int = 1024,
        timeout_seconds: float = 120.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("DeepSeek API key is required")
        if not model.strip():
            raise ValueError("LLM model is required")
        if not 0.0 <= temperature <= 1.0:
            raise ValueError("LLM temperature must be in [0, 1]")
        if max_output_tokens <= 0:
            raise ValueError("LLM max output tokens must be positive")
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self._api_key = api_key
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_seconds
        )

    def close(self) -> None:
        """Close the internally owned HTTP client."""
        if self._owns_client:
            self._client.close()

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return validated answer text from one DeepSeek response."""
        try:
            response = self._client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self.model,
                    "stream": False,
                    "thinking": {"type": "disabled"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": self.temperature,
                    "max_tokens": self.max_output_tokens,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            _log_provider_http_error("DeepSeek", exc)
            raise LLMError("DeepSeek generation request failed") from exc
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise LLMError("DeepSeek returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise LLMError("DeepSeek returned a non-object response")
        choices = payload.get("choices")
        if (
            not isinstance(choices, list)
            or not choices
            or not isinstance(choices[0], dict)
        ):
            raise LLMError("DeepSeek response has no completion choice")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise LLMError("DeepSeek response has no message object")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LLMError("DeepSeek returned an empty answer")
        return content.strip()


class GroqLLMAdapter:
    """Generate one non-streaming answer through Groq's OpenAI-compatible API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.groq.com/openai/v1",
        temperature: float = 0.1,
        max_output_tokens: int = 1024,
        timeout_seconds: float = 120.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Groq API key is required")
        if not model.strip():
            raise ValueError("LLM model is required")
        if not 0.0 <= temperature <= 1.0:
            raise ValueError("LLM temperature must be in [0, 1]")
        if max_output_tokens <= 0:
            raise ValueError("LLM max output tokens must be positive")
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self._api_key = api_key
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_seconds
        )

    def close(self) -> None:
        """Close the internally owned HTTP client."""
        if self._owns_client:
            self._client.close()

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return validated answer text from one Groq response."""
        try:
            response = self._client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self.model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": self.temperature,
                    "max_tokens": self.max_output_tokens,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            _log_provider_http_error("Groq", exc)
            raise LLMError("Groq generation request failed") from exc
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise LLMError("Groq returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise LLMError("Groq returned a non-object response")
        choices = payload.get("choices")
        if (
            not isinstance(choices, list)
            or not choices
            or not isinstance(choices[0], dict)
        ):
            raise LLMError("Groq response has no completion choice")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise LLMError("Groq response has no message object")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LLMError("Groq returned an empty answer")
        return content.strip()


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
            _log_provider_http_error("Ollama", exc)
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


def create_llm_adapter(settings: Settings) -> LLMAdapter:
    """Create the configured generation adapter and validate provider secrets."""
    if settings.llm_provider == "deepseek":
        if settings.deepseek_api_key is None:
            raise ValueError("DEEPSEEK_API_KEY is required when LLM_PROVIDER=deepseek")
        return DeepSeekLLMAdapter(
            api_key=settings.deepseek_api_key.get_secret_value(),
            model=settings.llm_model,
            base_url=str(settings.deepseek_base_url),
            temperature=settings.llm_temperature,
            max_output_tokens=settings.llm_max_output_tokens,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if settings.llm_provider == "groq":
        if settings.groq_api_key is None:
            raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        return GroqLLMAdapter(
            api_key=settings.groq_api_key.get_secret_value(),
            model=settings.llm_model,
            base_url=str(settings.groq_base_url),
            temperature=settings.llm_temperature,
            max_output_tokens=settings.llm_max_output_tokens,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return OllamaLLMAdapter(
        model=settings.llm_model,
        base_url=str(settings.ollama_base_url),
        temperature=settings.llm_temperature,
        timeout_seconds=settings.llm_timeout_seconds,
    )
