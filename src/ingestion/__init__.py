"""Bounded, revision-aware MediaWiki ingestion."""

from src.ingestion.mediawiki_client import MediaWikiClient
from src.ingestion.page_discovery import DiscoveryPolicy, PageDiscovery
from src.ingestion.sync_manager import SyncManager

__all__ = ["DiscoveryPolicy", "MediaWikiClient", "PageDiscovery", "SyncManager"]
