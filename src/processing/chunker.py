"""Section-aware semantic chunking with deterministic source identities."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

from src.processing.classifier import PageClassifier
from src.processing.models import ChunkDraft, PageClassification, ParsedPage

TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
SUBJECTIVE_MARKERS = ("guide", "recommendation", "strategy", "tips")
GAME_LABELS = {
    "dst": "Don't Starve Together",
    "dont_starve": "Don't Starve",
    "reign_of_giants": "Reign of Giants",
    "shipwrecked": "Shipwrecked",
    "hamlet": "Hamlet",
    "mixed": "Mixed game scope",
    "unknown": "Unknown game scope",
}


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    """Small deterministic chunking policy matching the planning targets."""

    target_tokens: int = 450
    max_tokens: int = 600
    overlap_tokens: int = 60

    def __post_init__(self) -> None:
        if self.target_tokens <= 0 or self.max_tokens < self.target_tokens:
            raise ValueError("Chunk token targets are invalid")
        if not 0 <= self.overlap_tokens < self.target_tokens:
            raise ValueError("Chunk overlap must be smaller than the target")


class SectionChunker:
    """Chunk within section boundaries and keep tables/lists as atomic blocks."""

    def __init__(
        self,
        classifier: PageClassifier,
        config: ChunkingConfig | None = None,
    ) -> None:
        self._classifier = classifier
        self.config = config or ChunkingConfig()

    def chunk(self, page: ParsedPage, classification: PageClassification) -> list[ChunkDraft]:
        """Create stable chunk candidates for one parsed revision."""
        chunks: list[ChunkDraft] = []
        for section in page.sections:
            section_scope = self._classifier.classify_section_scope(
                classification.game_scope,
                section.section_path,
            )
            bodies = self._chunk_section(section.content)
            for chunk_index, body in enumerate(bodies):
                header = (
                    f"Page: {page.source.title}\n"
                    f"Section: {section.section_path}\n"
                    f"Game: {GAME_LABELS[section_scope]}\n"
                    f"Entity type: {classification.entity_type}"
                )
                content = f"{header}\n\n{body.strip()}"
                content_hash = self._sha256(content)
                body_hash = self._sha256(body.strip())
                source_key = self._sha256(
                    "\n".join(
                        (
                            str(page.source.mediawiki_page_id),
                            str(page.source.revision_id),
                            section.section_path,
                            str(chunk_index),
                            content_hash,
                        )
                    )
                )
                normalized = self._normalize(content)
                subjective = classification.subjective or any(
                    marker in section.section_path.casefold() for marker in SUBJECTIVE_MARKERS
                )
                chunks.append(
                    ChunkDraft(
                        wiki_page_id=page.source.id,
                        mediawiki_page_id=page.source.mediawiki_page_id,
                        source_key=source_key,
                        page_title=page.source.title,
                        section_path=section.section_path,
                        chunk_index=chunk_index,
                        content=content,
                        content_normalized=normalized,
                        content_hash=content_hash,
                        token_count=self.token_count(content),
                        game_scope=section_scope,
                        entity_type=classification.entity_type,
                        source_kind=classification.source_kind,
                        subjective=subjective,
                        canonical_url=page.source.canonical_url,
                        revision_id=page.source.revision_id,
                        search_text=f"{page.source.title}\n{section.section_path}\n{content}\n{normalized}",
                        metadata={
                            "body_hash": body_hash,
                            "categories": list(page.categories),
                            "template_names": list(page.template_names),
                            "scope_reason": classification.scope_reason,
                            "entity_reason": classification.entity_reason,
                            "source_reason": classification.source_reason,
                            "parser": "mwparserfromhell-0.7.2",
                            "chunking": {
                                "target_tokens": self.config.target_tokens,
                                "max_tokens": self.config.max_tokens,
                                "overlap_tokens": self.config.overlap_tokens,
                            },
                        },
                    )
                )
        return chunks

    def _chunk_section(self, content: str) -> list[str]:
        blocks = [block.strip() for block in re.split(r"\n\s*\n", content) if block.strip()]
        pieces: list[str] = []
        for block in blocks:
            pieces.extend(self._split_large_block(block))
        if not pieces:
            return []

        chunks: list[str] = []
        current: list[str] = []
        for piece in pieces:
            candidate = "\n\n".join((*current, piece))
            if current and self.token_count(candidate) > self.config.max_tokens:
                emitted = "\n\n".join(current).strip()
                chunks.append(emitted)
                overlap = self._tail(emitted, self.config.overlap_tokens)
                current = [overlap, piece] if overlap else [piece]
            else:
                current.append(piece)
            if current and self.token_count("\n\n".join(current)) >= self.config.target_tokens:
                emitted = "\n\n".join(current).strip()
                chunks.append(emitted)
                overlap = self._tail(emitted, self.config.overlap_tokens)
                current = [overlap] if overlap else []
        if current:
            remainder = "\n\n".join(current).strip()
            if not chunks or remainder != self._tail(chunks[-1], self.config.overlap_tokens):
                chunks.append(remainder)
        return chunks

    def _split_large_block(self, block: str) -> list[str]:
        if self.token_count(block) <= self.config.max_tokens or self._is_atomic(block):
            return [block]
        sentences = [value.strip() for value in SENTENCE_BOUNDARY.split(block) if value.strip()]
        if len(sentences) <= 1:
            return self._split_by_token_span(block)
        pieces: list[str] = []
        current: list[str] = []
        for sentence in sentences:
            candidate = " ".join((*current, sentence))
            if current and self.token_count(candidate) > self.config.max_tokens:
                pieces.append(" ".join(current))
                current = [sentence]
            else:
                current.append(sentence)
        if current:
            pieces.append(" ".join(current))
        return [subpiece for piece in pieces for subpiece in self._split_by_token_span(piece)]

    def _split_by_token_span(self, value: str) -> list[str]:
        matches = list(TOKEN_PATTERN.finditer(value))
        if len(matches) <= self.config.max_tokens:
            return [value]
        output: list[str] = []
        for offset in range(0, len(matches), self.config.max_tokens):
            batch = matches[offset : offset + self.config.max_tokens]
            output.append(value[batch[0].start() : batch[-1].end()].strip())
        return output

    @staticmethod
    def _is_atomic(block: str) -> bool:
        lines = block.splitlines()
        return block.startswith(("Infobox:", "Table:")) or (
            bool(lines) and all(line.startswith("- ") for line in lines)
        )

    @staticmethod
    def token_count(value: str) -> int:
        """Count deterministic Unicode word/punctuation tokens without a model tokenizer."""
        return len(TOKEN_PATTERN.findall(value))

    @staticmethod
    def _tail(value: str, count: int) -> str:
        if count <= 0:
            return ""
        matches = list(TOKEN_PATTERN.finditer(value))
        if not matches:
            return ""
        start = matches[max(0, len(matches) - count)].start()
        return value[start:].strip()

    @staticmethod
    def _normalize(value: str) -> str:
        normalized = unicodedata.normalize("NFC", value).casefold()
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _sha256(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
