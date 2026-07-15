"""Deterministic section-aware semantic chunking tests."""

from src.processing.chunker import ChunkingConfig, SectionChunker
from src.processing.classifier import PageClassifier
from src.processing.models import (
    PageClassification,
    ParsedPage,
    ParsedSection,
    SourcePage,
)


def _page(content: str) -> ParsedPage:
    source = SourcePage(
        id="wiki-page-1",
        mediawiki_page_id=42,
        title="Thermal Stone",
        canonical_url="https://dontstarve.wiki.gg/wiki/Thermal_Stone",
        revision_id=99,
        revision_timestamp=None,
        preliminary_game_scope="dst",
        raw_storage_bucket="dst-wiki-raw",
        raw_storage_path="pages/42/99.json",
        metadata={},
    )
    return ParsedPage(
        source=source,
        sections=(ParsedSection(("Usage",), content),),
        categories=("Items", "Don't Starve Together"),
        template_names=("Object Infobox",),
        scope_hints=("Don't Starve Together",),
        infobox_facts=(),
    )


def _classification() -> PageClassification:
    return PageClassification(
        game_scope="dst",
        entity_type="item",
        source_kind="factual_article",
        subjective=False,
        scope_reason="category",
        entity_reason="category",
        source_reason="article_default",
    )


def test_long_section_splits_deterministically_with_overlap() -> None:
    content = " ".join(f"Sentence {index} explains temperature behavior." for index in range(220))
    chunker = SectionChunker(
        PageClassifier(),
        ChunkingConfig(target_tokens=120, max_tokens=160, overlap_tokens=20),
    )

    first = chunker.chunk(_page(content), _classification())
    second = chunker.chunk(_page(content), _classification())

    assert len(first) > 2
    assert [chunk.source_key for chunk in first] == [chunk.source_key for chunk in second]
    assert all(chunk.section_path == "Usage" for chunk in first)
    assert all(chunk.content.startswith("Page: Thermal Stone") for chunk in first)
    assert all(chunk.token_count > 0 for chunk in first)
    assert len({chunk.source_key for chunk in first}) == len(first)


def test_table_block_remains_atomic_even_above_soft_limit() -> None:
    table = "Table:\n" + "\n".join(f"Row {index}: Value {index}" for index in range(100))
    chunker = SectionChunker(
        PageClassifier(),
        ChunkingConfig(target_tokens=40, max_tokens=60, overlap_tokens=10),
    )

    chunks = chunker.chunk(_page(table), _classification())

    assert len(chunks) == 1
    assert "Row 99: Value 99" in chunks[0].content
