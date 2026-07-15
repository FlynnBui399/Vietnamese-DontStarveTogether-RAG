"""Vietnamese normalization, glossary loading, alias resolution, and query expansion."""

from src.terminology.glossary import DEFAULT_GLOSSARY_PATH, Glossary, GlossaryError
from src.terminology.models import AliasRecord, ExpandedQuery, NormalizedQuery, ResolvedEntity
from src.terminology.normalizer import (
    detect_query_language,
    normalize_query,
    normalize_search_text,
    normalize_unicode,
    remove_vietnamese_accents,
)
from src.terminology.resolver import AliasResolver, QueryExpander

__all__ = [
    "DEFAULT_GLOSSARY_PATH",
    "AliasRecord",
    "AliasResolver",
    "ExpandedQuery",
    "Glossary",
    "GlossaryError",
    "NormalizedQuery",
    "QueryExpander",
    "ResolvedEntity",
    "detect_query_language",
    "normalize_query",
    "normalize_search_text",
    "normalize_unicode",
    "remove_vietnamese_accents",
]
