"""Chunk completeness and exact-duplicate reporting tests."""

from dataclasses import replace

from src.processing.models import ChunkDraft
from src.processing.validator import CorpusValidator


def _chunk(source_key: str, *, wiki_page_id: str = "page-1") -> ChunkDraft:
    return ChunkDraft(
        wiki_page_id=wiki_page_id,
        mediawiki_page_id=1,
        source_key=source_key,
        page_title="Football Helmet",
        section_path="Crafting",
        chunk_index=0,
        content="Page: Football Helmet\n\nFactual body",
        content_normalized="page: football helmet factual body",
        content_hash="a" * 64,
        token_count=8,
        game_scope="dst",
        entity_type="armor",
        source_kind="factual_article",
        subjective=False,
        canonical_url="https://dontstarve.wiki.gg/wiki/Football_Helmet",
        revision_id=2,
        search_text="Football Helmet Crafting Factual body",
        metadata={"body_hash": "b" * 64},
    )


def test_exact_duplicate_is_excluded_and_explained() -> None:
    report = CorpusValidator().validate(
        (_chunk("1" * 64), _chunk("2" * 64)),
        expected_page_ids={"page-1"},
    )

    assert report.passed is True
    assert report.valid_chunk_count == 1
    assert report.duplicate_count == 1
    assert report.issues[0].code == "duplicate_content"
    assert report.issues[0].fatal is False


def test_missing_metadata_and_uncovered_page_fail_validation() -> None:
    invalid = replace(_chunk("3" * 64), section_path="")

    report = CorpusValidator().validate((invalid,), expected_page_ids={"page-1"})

    assert report.passed is False
    assert report.valid_chunk_count == 0
    assert {issue.code for issue in report.issues} == {
        "missing_metadata",
        "page_without_chunks",
    }
