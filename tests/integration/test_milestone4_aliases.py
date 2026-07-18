"""Opt-in local Supabase acceptance test for Milestone 4 alias synchronization."""

import os

import pytest

from src.supabase_store import SupabaseAliasRepository
from src.terminology import AliasResolver, Glossary


def _live_environment() -> tuple[str, str]:
    if os.getenv("RUN_MILESTONE4_LIVE") != "1":
        pytest.skip("set RUN_MILESTONE4_LIVE=1 for live alias synchronization")
    base_url = os.getenv("SUPABASE_TEST_URL")
    api_key = os.getenv("SUPABASE_TEST_SECRET_KEY") or os.getenv("SUPABASE_TEST_SERVICE_ROLE_KEY")
    if base_url is None or api_key is None:
        pytest.skip("local Supabase server credentials are not configured")
    return base_url, api_key


def test_alias_sync_is_idempotent_and_required_queries_resolve() -> None:
    base_url, api_key = _live_environment()
    glossary = Glossary.load()
    with SupabaseAliasRepository(base_url=base_url, api_key=api_key) as repository:
        first_count = repository.sync_aliases(glossary.records)
        rows_after_first = repository.list_aliases()
        second_count = repository.sync_aliases(glossary.records)
        rows_after_second = repository.list_aliases()

    assert first_count == second_count == len(glossary.records)
    assert len(rows_after_first) == len(rows_after_second)
    resolver = AliasResolver(rows_after_second)
    assert resolver.resolve("mu da heo", limit=1)[0].entity_title == "Football Helmet"
    assert resolver.resolve("da giu nhiet", limit=1)[0].entity_title == "Thermal Stone"
    assert resolver.resolve("nhan vat di cung ma", limit=1)[0].entity_title == "Wendy"
