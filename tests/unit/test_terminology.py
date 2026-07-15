"""Vietnamese terminology, alias resolution, and expansion tests."""

from src.terminology import (
    AliasRecord,
    AliasResolver,
    Glossary,
    QueryExpander,
    normalize_query,
    normalize_search_text,
)


def test_vietnamese_normalization_preserves_original_and_removes_accents() -> None:
    query = normalize_query("  Mũ da heo — CÁCH làm  ")

    assert query.normalized == "mũ da heo - cách làm"
    assert query.search_normalized == "mu da heo - cach lam"
    assert query.language == "vi"
    assert normalize_search_text("Đá giữ nhiệt") == "da giu nhiet"


def test_required_accentless_and_descriptive_queries_resolve() -> None:
    resolver = AliasResolver(Glossary.load().records)

    assert resolver.resolve("mu da heo", limit=1)[0].entity_title == "Football Helmet"
    assert resolver.resolve("da giu nhiet", limit=1)[0].entity_title == "Thermal Stone"
    assert resolver.resolve("nhan vat di cung ma", limit=1)[0].entity_title == "Wendy"
    assert resolver.resolve("fotball helmet", limit=1)[0].entity_title == "Football Helmet"


def test_verified_alias_outranks_generated_candidate_for_same_phrase() -> None:
    records = (
        AliasRecord(
            entity_title="Verified Entity",
            entity_slug="verified-entity",
            alias="same alias",
            alias_normalized="same alias",
            language="en",
            alias_type="community_translation",
            priority=85,
            confidence=0.95,
            verified=True,
            source="test",
            metadata={},
        ),
        AliasRecord(
            entity_title="Generated Entity",
            entity_slug="generated-entity",
            alias="same alias",
            alias_normalized="same alias",
            language="en",
            alias_type="generated_candidate",
            priority=10,
            confidence=0.5,
            verified=False,
            source="test",
            metadata={},
        ),
    )

    matches = AliasResolver(records).resolve("same alias", limit=2)

    assert [match.entity_title for match in matches] == ["Verified Entity", "Generated Entity"]


def test_mixed_query_expansion_is_bounded_and_uses_verified_aliases() -> None:
    glossary = Glossary.load()
    expanded = QueryExpander(AliasResolver(glossary.records), max_terms=8).expand(
        "Football Helmet cách làm"
    )

    assert expanded.query.language == "mixed"
    assert len(expanded.terms) <= 8
    assert any(term == "Football Helmet" for term in expanded.terms)
