"""Fetch and prepare explicit Wiki pages for the small MVP corpus."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from src.processing.cleaner import WikiPageCleaner
from src.processing.models import SourcePage


class WikiError(RuntimeError):
    """Raised when a requested Wiki page cannot be fetched or parsed."""


@dataclass(frozen=True, slots=True)
class FetchedWikiPage:
    title: str
    page_id: int
    revision_id: int
    revision_timestamp: str | None
    url: str
    wikitext: str


@dataclass(frozen=True, slots=True)
class PreparedChunk:
    id: str
    page_title: str
    section: str
    content: str
    url: str
    revision_id: int


class WikiClient:
    """Minimal MediaWiki client for searching and fetching selected titles."""

    def __init__(
        self,
        *,
        api_url: str,
        base_url: str,
        user_agent: str,
        timeout_seconds: float = 20.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_url = api_url
        self.base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout_seconds,
            headers={"User-Agent": user_agent},
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def fetch(self, title: str) -> FetchedWikiPage:
        try:
            response = self._client.get(
                self.api_url,
                params={
                    "action": "query",
                    "format": "json",
                    "formatversion": "2",
                    "prop": "revisions",
                    "rvprop": "ids|timestamp|content",
                    "rvslots": "main",
                    "titles": title,
                },
            )
            response.raise_for_status()
            payload = response.json()
            page = payload["query"]["pages"][0]
            if page.get("missing"):
                raise WikiError(f"Wiki page does not exist: {title}")
            revision = page["revisions"][0]
            wikitext = revision["slots"]["main"]["content"]
            resolved_title = str(page["title"])
            return FetchedWikiPage(
                title=resolved_title,
                page_id=int(page["pageid"]),
                revision_id=int(revision["revid"]),
                revision_timestamp=revision.get("timestamp"),
                url=f"{self.base_url}/wiki/{quote(resolved_title.replace(' ', '_'))}",
                wikitext=str(wikitext),
            )
        except WikiError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise WikiError(f"Could not fetch Wiki page: {title}") from exc

    def search_titles(self, query: str, *, limit: int = 3) -> tuple[str, ...]:
        """Return top MediaWiki search result titles for a user query."""
        query = query.strip()
        if not query:
            return ()
        try:
            response = self._client.get(
                self.api_url,
                params={
                    "action": "query",
                    "format": "json",
                    "formatversion": "2",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": max(1, min(limit, 5)),
                    "srnamespace": "0",
                },
            )
            response.raise_for_status()
            payload = response.json()
            rows: Sequence[object] = payload["query"]["search"]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise WikiError(f"Could not search Wiki for: {query}") from exc
        titles: list[str] = []
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get("title"), str):
                titles.append(row["title"])
        return tuple(dict.fromkeys(titles))


def prepare_chunks(
    page: FetchedWikiPage,
    *,
    target_words: int = 300,
    overlap_words: int = 40,
) -> list[PreparedChunk]:
    """Clean one page and split its sections into small overlapping chunks."""
    source = SourcePage(
        id=str(page.page_id),
        mediawiki_page_id=page.page_id,
        title=page.title,
        canonical_url=page.url,
        revision_id=page.revision_id,
        revision_timestamp=page.revision_timestamp,
        preliminary_game_scope="dst",
        raw_storage_bucket="",
        raw_storage_path="",
        metadata={},
    )
    parsed = WikiPageCleaner().parse(source, page.wikitext)
    chunks: list[PreparedChunk] = []
    for section in parsed.sections:
        for index, body in enumerate(
            split_text(
                section.content,
                target_words=target_words,
                overlap_words=overlap_words,
            )
        ):
            content = f"Trang: {page.title}\nMục: {section.section_path}\n\n{body}"
            chunk_id = hashlib.sha256(
                f"{page.title}\n{section.section_path}\n{index}\n{content}".encode()
            ).hexdigest()
            chunks.append(
                PreparedChunk(
                    id=chunk_id,
                    page_title=page.title,
                    section=section.section_path,
                    content=content,
                    url=page.url,
                    revision_id=page.revision_id,
                )
            )
    return chunks


def split_text(text: str, *, target_words: int = 300, overlap_words: int = 40) -> list[str]:
    """Split plain text by word count; sufficient for a small Wiki chatbot."""
    if target_words <= 0 or overlap_words < 0 or overlap_words >= target_words:
        raise ValueError("Invalid chunk size")
    words = text.split()
    if not words:
        return []
    step = target_words - overlap_words
    chunks: list[str] = []
    start = 0
    while start < len(words):
        chunks.append(" ".join(words[start : start + target_words]))
        if start + target_words >= len(words):
            break
        start += step
    return chunks
