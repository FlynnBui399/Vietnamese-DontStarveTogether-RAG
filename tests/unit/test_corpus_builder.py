"""Goal-level corpus builder test with an in-memory persistence adapter."""

from collections.abc import Sequence
from pathlib import Path

from src.processing import (
    CorpusValidator,
    PageClassifier,
    SectionChunker,
    WikiPageCleaner,
)
from src.processing.corpus_builder import CorpusBuilder
from src.processing.models import (
    ChunkDraft,
    PageClassification,
    SourcePage,
    ValidationReport,
)

FIXTURE = Path("tests/fixtures/processing/football_helmet.wiki")


class FakeProcessingRepository:
    def __init__(self) -> None:
        self.page = SourcePage(
            id="wiki-page-1",
            mediawiki_page_id=200315,
            title="Football Helmet",
            canonical_url="https://dontstarve.wiki.gg/wiki/Football_Helmet",
            revision_id=377548,
            revision_timestamp=None,
            preliminary_game_scope="dst",
            raw_storage_bucket="dst-wiki-raw",
            raw_storage_path="pages/200315/377548.json",
            metadata={},
        )
        self.inserted: tuple[ChunkDraft, ...] = ()
        self.finished = False
        self.failed = False

    def create_or_reset_corpus(
        self,
        *,
        version: str,
        embedding_model_key: str,
        embedding_dimensions: int,
    ) -> str:
        assert version == "test-v1"
        assert embedding_model_key == "pending-1024"
        assert embedding_dimensions == 1024
        return "corpus-1"

    def list_source_pages(self) -> list[SourcePage]:
        return [self.page]

    def download_wikitext(self, _page: SourcePage) -> str:
        return FIXTURE.read_text(encoding="utf-8")

    def update_page_classification(
        self,
        _page: SourcePage,
        classification: PageClassification,
    ) -> None:
        assert classification.game_scope == "dst"
        assert classification.entity_type == "armor"

    def insert_chunks(self, _corpus_id: str, chunks: Sequence[ChunkDraft]) -> None:
        self.inserted = tuple(chunks)

    def finish_processing(
        self,
        _corpus_id: str,
        *,
        page_count: int,
        source_revision_max: int,
        validation: ValidationReport,
        classification_counts: dict[str, int],
    ) -> None:
        assert page_count == 1
        assert source_revision_max == 377548
        assert validation.passed is True
        assert classification_counts["scope:dst"] == 1
        self.finished = True

    def mark_corpus_failed(
        self,
        _corpus_id: str,
        *,
        errors: Sequence[str],
        validation: ValidationReport | None,
    ) -> None:
        self.failed = True


def test_builder_inserts_only_validated_chunks_and_remains_building() -> None:
    repository = FakeProcessingRepository()
    classifier = PageClassifier()
    report = CorpusBuilder(
        repository,
        cleaner=WikiPageCleaner(),
        classifier=classifier,
        chunker=SectionChunker(classifier),
        validator=CorpusValidator(),
    ).build(
        version="test-v1",
        embedding_model_key="pending-1024",
        embedding_dimensions=1024,
    )

    assert report.status == "building"
    assert report.validation is not None and report.validation.passed is True
    assert report.inserted_chunk_count == len(repository.inserted)
    assert report.inserted_chunk_count > 0
    assert repository.finished is True
    assert repository.failed is False


def test_builder_marks_empty_corpus_failed_without_inserting_chunks() -> None:
    repository = FakeProcessingRepository()
    repository.list_source_pages = lambda: []  # type: ignore[method-assign]
    classifier = PageClassifier()

    report = CorpusBuilder(
        repository,
        cleaner=WikiPageCleaner(),
        classifier=classifier,
        chunker=SectionChunker(classifier),
        validator=CorpusValidator(),
    ).build(
        version="test-v1",
        embedding_model_key="pending-1024",
        embedding_dimensions=1024,
    )

    assert report.status == "failed"
    assert report.validation is not None and report.validation.passed is False
    assert repository.inserted == ()
    assert repository.finished is False
    assert repository.failed is True
