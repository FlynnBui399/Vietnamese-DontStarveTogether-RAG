"""Build and validate a non-active corpus version from private raw snapshots."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from src.processing.chunker import SectionChunker
from src.processing.classifier import PageClassifier
from src.processing.cleaner import WikiPageCleaner
from src.processing.models import (
    ChunkDraft,
    PageClassification,
    SourcePage,
    ValidationReport,
)
from src.processing.validator import CorpusValidator


class ProcessingRepository(Protocol):
    """Persistence operations needed by the corpus builder."""

    def create_or_reset_corpus(
        self,
        *,
        version: str,
        embedding_model_key: str,
        embedding_dimensions: int,
    ) -> str: ...

    def list_source_pages(self) -> list[SourcePage]: ...

    def download_wikitext(self, page: SourcePage) -> str: ...

    def update_page_classification(
        self,
        page: SourcePage,
        classification: PageClassification,
    ) -> None: ...

    def insert_chunks(self, corpus_id: str, chunks: Sequence[ChunkDraft]) -> None: ...

    def finish_processing(
        self,
        corpus_id: str,
        *,
        page_count: int,
        source_revision_max: int,
        validation: ValidationReport,
        classification_counts: dict[str, int],
    ) -> None: ...

    def mark_corpus_failed(
        self,
        corpus_id: str,
        *,
        errors: Sequence[str],
        validation: ValidationReport | None,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class CorpusBuildReport:
    """CLI-facing outcome of one processing build."""

    corpus_id: str
    version: str
    status: str
    source_page_count: int
    parsed_page_count: int
    chunk_candidate_count: int
    inserted_chunk_count: int
    classification_counts: dict[str, int]
    errors: tuple[str, ...]
    validation: ValidationReport | None

    def to_dict(self) -> dict[str, object]:
        return {
            "corpus_id": self.corpus_id,
            "version": self.version,
            "status": self.status,
            "source_page_count": self.source_page_count,
            "parsed_page_count": self.parsed_page_count,
            "chunk_candidate_count": self.chunk_candidate_count,
            "inserted_chunk_count": self.inserted_chunk_count,
            "classification_counts": self.classification_counts,
            "errors": list(self.errors),
            "validation": self.validation.to_dict() if self.validation is not None else None,
        }


class CorpusBuilder:
    """Process all current raw pages, validate in memory, then insert as one corpus."""

    def __init__(
        self,
        repository: ProcessingRepository,
        *,
        cleaner: WikiPageCleaner,
        classifier: PageClassifier,
        chunker: SectionChunker,
        validator: CorpusValidator,
    ) -> None:
        self._repository = repository
        self._cleaner = cleaner
        self._classifier = classifier
        self._chunker = chunker
        self._validator = validator

    def build(
        self,
        *,
        version: str,
        embedding_model_key: str,
        embedding_dimensions: int,
    ) -> CorpusBuildReport:
        """Build a validated corpus that deliberately remains non-active and unembedded."""
        corpus_id = self._repository.create_or_reset_corpus(
            version=version,
            embedding_model_key=embedding_model_key,
            embedding_dimensions=embedding_dimensions,
        )
        pages = self._repository.list_source_pages()
        errors: list[str] = []
        chunks: list[ChunkDraft] = []
        parsed_count = 0
        classifications: Counter[str] = Counter()

        for page in pages:
            try:
                wikitext = self._repository.download_wikitext(page)
                parsed = self._cleaner.parse(page, wikitext)
                classification = self._classifier.classify(parsed)
                page_chunks = self._chunker.chunk(parsed, classification)
                self._repository.update_page_classification(page, classification)
                chunks.extend(page_chunks)
                parsed_count += 1
                classifications[f"scope:{classification.game_scope}"] += 1
                classifications[f"entity:{classification.entity_type}"] += 1
                classifications[f"source:{classification.source_kind}"] += 1
            except Exception as exc:
                errors.append(f"{page.title}: {type(exc).__name__}: {exc}")

        validation = self._validator.validate(
            chunks,
            expected_page_ids={page.id for page in pages},
        )
        if not pages:
            errors.append("No current raw wiki pages were available")
        if not validation.passed:
            errors.append("Corpus processing validation failed")

        if errors:
            self._repository.mark_corpus_failed(
                corpus_id,
                errors=errors,
                validation=validation,
            )
            return CorpusBuildReport(
                corpus_id=corpus_id,
                version=version,
                status="failed",
                source_page_count=len(pages),
                parsed_page_count=parsed_count,
                chunk_candidate_count=len(chunks),
                inserted_chunk_count=0,
                classification_counts=dict(classifications),
                errors=tuple(errors),
                validation=validation,
            )

        try:
            self._repository.insert_chunks(corpus_id, validation.valid_chunks)
            self._repository.finish_processing(
                corpus_id,
                page_count=len(pages),
                source_revision_max=max(page.revision_id for page in pages),
                validation=validation,
                classification_counts=dict(classifications),
            )
        except Exception as exc:
            errors.append(f"Persistence: {type(exc).__name__}: {exc}")
            self._repository.mark_corpus_failed(
                corpus_id,
                errors=errors,
                validation=validation,
            )
            return CorpusBuildReport(
                corpus_id=corpus_id,
                version=version,
                status="failed",
                source_page_count=len(pages),
                parsed_page_count=parsed_count,
                chunk_candidate_count=len(chunks),
                inserted_chunk_count=0,
                classification_counts=dict(classifications),
                errors=tuple(errors),
                validation=validation,
            )

        return CorpusBuildReport(
            corpus_id=corpus_id,
            version=version,
            status="building",
            source_page_count=len(pages),
            parsed_page_count=parsed_count,
            chunk_candidate_count=len(chunks),
            inserted_chunk_count=validation.valid_chunk_count,
            classification_counts=dict(classifications),
            errors=(),
            validation=validation,
        )
