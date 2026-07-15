"""Deterministic Vietnamese-aware Unicode and query normalization."""

from __future__ import annotations

import re
import unicodedata

from src.terminology.models import NormalizedQuery, QueryLanguage

WHITESPACE_PATTERN = re.compile(r"\s+")
SEARCH_PUNCTUATION_PATTERN = re.compile(r"[^\w\s-]", re.UNICODE)
VIETNAMESE_DIACRITIC_PATTERN = re.compile(
    r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩị"
    r"óòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]",
    re.IGNORECASE,
)
VIETNAMESE_HINTS = {
    "ban",
    "cach",
    "che",
    "con",
    "cung",
    "da",
    "de",
    "di",
    "giu",
    "lam",
    "ma",
    "mon",
    "mu",
    "nhan",
    "nhiet",
    "noi",
    "o",
    "vat",
}
ENGLISH_HINTS = {
    "armor",
    "character",
    "craft",
    "food",
    "helmet",
    "how",
    "item",
    "recipe",
    "stone",
    "the",
    "weapon",
}
TYPOGRAPHIC_TRANSLATION = str.maketrans(
    {
        "’": "'",
        "‘": "'",
        "`": "'",
        "–": "-",
        "—": "-",
        "‑": "-",
    }
)
VIETNAMESE_D_TRANSLATION = str.maketrans("đĐ", "dD")


def normalize_unicode(value: str) -> str:
    """Normalize Unicode, typography, and whitespace while preserving accents."""
    normalized = unicodedata.normalize("NFC", value).translate(TYPOGRAPHIC_TRANSLATION)
    return WHITESPACE_PATTERN.sub(" ", normalized).strip()


def remove_vietnamese_accents(value: str) -> str:
    """Remove combining marks and handle Vietnamese crossed-d explicitly."""
    decomposed = unicodedata.normalize("NFD", normalize_unicode(value))
    without_marks = "".join(
        character for character in decomposed if unicodedata.category(character) != "Mn"
    )
    return unicodedata.normalize("NFC", without_marks).translate(VIETNAMESE_D_TRANSLATION)


def normalize_search_text(value: str) -> str:
    """Create the lowercase, accent-insensitive form stored and matched by retrieval."""
    value_without_accents = remove_vietnamese_accents(value).casefold()
    value_without_punctuation = SEARCH_PUNCTUATION_PATTERN.sub(" ", value_without_accents)
    return WHITESPACE_PATTERN.sub(" ", value_without_punctuation).strip()


def detect_query_language(value: str) -> QueryLanguage:
    """Detect a practical Vietnamese/English/mixed retrieval hint without translation."""
    normalized = normalize_unicode(value).casefold()
    search_normalized = normalize_search_text(normalized)
    tokens = set(search_normalized.split())
    has_vi = bool(VIETNAMESE_DIACRITIC_PATTERN.search(normalized)) or bool(
        tokens & VIETNAMESE_HINTS
    )
    has_en = bool(tokens & ENGLISH_HINTS)
    if has_vi and has_en:
        return "mixed"
    if has_vi:
        return "vi"
    if has_en or any(character.isalpha() for character in normalized):
        return "en"
    return "unknown"


def normalize_query(value: str) -> NormalizedQuery:
    """Return every deterministic query form used by alias and retrieval stages."""
    normalized = normalize_unicode(value).casefold()
    return NormalizedQuery(
        original=value,
        normalized=normalized,
        search_normalized=normalize_search_text(normalized),
        language=detect_query_language(normalized),
    )
