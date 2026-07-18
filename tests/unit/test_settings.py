"""Configuration validation tests."""

import pytest
from pydantic import ValidationError

from src.config import Settings


def test_supabase_url_requires_a_key() -> None:
    """A partial Supabase configuration must fail before a request is attempted."""
    with pytest.raises(ValidationError, match="must be configured together"):
        Settings(_env_file=None, supabase_url="http://127.0.0.1:54321")


def test_secret_values_are_masked() -> None:
    """Pydantic representations must not reveal configured secrets."""
    settings = Settings(
        _env_file=None,
        supabase_url="http://127.0.0.1:54321",
        supabase_secret_key="development-secret-placeholder",
    )

    assert "development-secret-placeholder" not in repr(settings)


def test_wiki_ingestion_is_serial_by_configuration() -> None:
    """The bounded worker must not be configured to fan out wiki requests."""
    with pytest.raises(ValidationError):
        Settings.model_validate({"wiki_max_concurrency": 2})


def test_deepseek_is_the_default_generation_provider() -> None:
    settings = Settings(_env_file=None)

    assert settings.llm_provider == "deepseek"
    assert settings.llm_model == "deepseek-v4-flash"
    assert str(settings.deepseek_base_url) == "https://api.deepseek.com/"
    assert settings.llm_max_output_tokens == 1024


def test_deepseek_api_key_is_masked() -> None:
    settings = Settings(_env_file=None, deepseek_api_key="test-deepseek-secret")

    assert "test-deepseek-secret" not in repr(settings)


def test_groq_api_key_is_masked() -> None:
    settings = Settings(_env_file=None, groq_api_key="test-groq-secret")

    assert "test-groq-secret" not in repr(settings)
