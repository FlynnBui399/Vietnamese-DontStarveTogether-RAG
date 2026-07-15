"""Backend-only Supabase persistence adapters."""

from src.supabase_store.alias_repository import SupabaseAliasError, SupabaseAliasRepository
from src.supabase_store.ingestion_repository import SupabaseIngestionRepository
from src.supabase_store.processing_repository import SupabaseProcessingRepository

__all__ = [
    "SupabaseAliasError",
    "SupabaseAliasRepository",
    "SupabaseIngestionRepository",
    "SupabaseProcessingRepository",
]
