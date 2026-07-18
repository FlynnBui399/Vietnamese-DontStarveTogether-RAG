"""On-demand Wiki ingestion used when chat has no stored evidence yet."""

from __future__ import annotations

from src.embeddings.adapter import EmbeddingAdapter
from src.rag import VectorStore
from src.wiki import WikiClient, WikiError, prepare_chunks


class WikiAutoIngestor:
    """Search a few Wiki pages for one query, embed them, and store them."""

    def __init__(
        self,
        *,
        wiki: WikiClient,
        embedding: EmbeddingAdapter,
        store: VectorStore,
        max_pages: int = 3,
    ) -> None:
        self.wiki = wiki
        self.embedding = embedding
        self.store = store
        self.max_pages = max(1, min(max_pages, 5))

    def ingest_for_query(self, query: str) -> int:
        """Return the number of pages successfully ingested for a query."""
        ingested = 0
        for title in self.wiki.search_titles(query, limit=self.max_pages):
            try:
                page = self.wiki.fetch(title)
                chunks = prepare_chunks(page)
                vectors = self.embedding.embed([chunk.content for chunk in chunks])
                rows = [
                    {
                        "id": chunk.id,
                        "page_title": chunk.page_title,
                        "section": chunk.section,
                        "content": chunk.content,
                        "url": chunk.url,
                        "revision_id": chunk.revision_id,
                        "embedding": vector,
                    }
                    for chunk, vector in zip(chunks, vectors, strict=True)
                ]
                self.store.replace_page(page.title, rows)
                ingested += 1
            except WikiError:
                continue
        return ingested
