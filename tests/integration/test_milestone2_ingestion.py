"""Opt-in local Supabase and live MediaWiki acceptance test for Milestone 2."""

import os
from pathlib import Path

import pytest

from src.ingestion import DiscoveryPolicy, MediaWikiClient, SyncManager
from src.supabase_store import SupabaseIngestionRepository


def _live_environment() -> tuple[str, str]:
    if os.getenv("RUN_MILESTONE2_LIVE") != "1":
        pytest.skip("set RUN_MILESTONE2_LIVE=1 for bounded live ingestion")
    base_url = os.getenv("SUPABASE_TEST_URL")
    api_key = os.getenv("SUPABASE_TEST_SECRET_KEY") or os.getenv("SUPABASE_TEST_SERVICE_ROLE_KEY")
    if base_url is None or api_key is None:
        pytest.skip("local Supabase server credentials are not configured")
    return base_url, api_key


def test_thirty_page_sync_is_idempotent(tmp_path: Path) -> None:
    base_url, api_key = _live_environment()
    policy = DiscoveryPolicy.from_path(
        Path("data/ingestion/discovery_config.json"),
        max_depth=1,
        max_pages=30,
    )
    with (
        MediaWikiClient(
            api_url="https://dontstarve.wiki.gg/api.php",
            user_agent=(
                "DSTVietnameseAssistant/0.2 "
                "(https://github.com/FlynnBui399/Vietnamese-DontStarveTogether-RAG)"
            ),
            request_delay_seconds=0.5,
            cache_dir=tmp_path / "mediawiki-cache",
        ) as wiki_client,
        SupabaseIngestionRepository(
            base_url=base_url,
            api_key=api_key,
            raw_bucket="dst-wiki-raw",
        ) as repository,
    ):
        manager = SyncManager(wiki_client, repository)
        first = manager.run(policy, sync_type="incremental")
        second = manager.run(policy, sync_type="incremental")

    assert first.status == "succeeded"
    assert first.pages_discovered == 30
    assert first.pages_fetched == 30
    assert first.pages_changed + first.pages_unchanged == 30
    assert second.status == "succeeded"
    assert second.pages_changed == 0
    assert second.pages_unchanged == 30
    assert second.raw_objects_uploaded == 0
