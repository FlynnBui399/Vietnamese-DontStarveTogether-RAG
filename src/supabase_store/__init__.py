"""Backend-only Supabase persistence adapters."""

from src.supabase_store.ingestion_repository import SupabaseIngestionRepository
from src.supabase_store.processing_repository import SupabaseProcessingRepository

__all__ = ["SupabaseIngestionRepository", "SupabaseProcessingRepository"]
