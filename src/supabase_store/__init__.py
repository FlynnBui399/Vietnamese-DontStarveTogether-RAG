"""Backend-only Supabase persistence adapters."""

from src.supabase_store.alias_repository import SupabaseAliasError, SupabaseAliasRepository
from src.supabase_store.embedding_repository import (
    SupabaseEmbeddingError,
    SupabaseEmbeddingRepository,
)
from src.supabase_store.ingestion_repository import SupabaseIngestionRepository
from src.supabase_store.knowledge_repository import (
    EntityDetail,
    EntitySearchResult,
    PublicCorpusStatus,
    SourceDetail,
    SupabaseKnowledgeError,
    SupabaseKnowledgeRepository,
)
from src.supabase_store.processing_repository import SupabaseProcessingRepository
from src.supabase_store.retrieval_repository import (
    SupabaseRetrievalError,
    SupabaseRetrievalRepository,
)

__all__ = [
    "EntityDetail",
    "EntitySearchResult",
    "PublicCorpusStatus",
    "SourceDetail",
    "SupabaseAliasError",
    "SupabaseAliasRepository",
    "SupabaseEmbeddingError",
    "SupabaseEmbeddingRepository",
    "SupabaseIngestionRepository",
    "SupabaseKnowledgeError",
    "SupabaseKnowledgeRepository",
    "SupabaseProcessingRepository",
    "SupabaseRetrievalError",
    "SupabaseRetrievalRepository",
]
