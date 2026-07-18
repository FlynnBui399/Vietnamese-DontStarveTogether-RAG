"""Ingest explicitly named Wiki pages into the small MVP vector table."""

from __future__ import annotations

import argparse

from src.config import get_settings
from src.embeddings.adapter import OllamaEmbeddingAdapter
from src.embeddings.models import EmbeddingModelManifest
from src.rag import SupabaseVectorStore
from src.wiki import WikiClient, prepare_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("titles", nargs="+", help="Exact Wiki page titles to ingest")
    args = parser.parse_args()

    settings = get_settings()
    if settings.supabase_url is None or settings.supabase_admin_api_key is None:
        raise SystemExit("Set SUPABASE_URL and SUPABASE_SECRET_KEY in .env first")
    if settings.embedding_provider != "ollama":
        raise SystemExit("MVP ingestion currently expects EMBEDDING_PROVIDER=ollama")

    manifest = EmbeddingModelManifest(
        model_key=f"{settings.embedding_model}-{settings.embedding_dimensions}",
        provider="ollama",
        model_name=settings.embedding_model,
        model_revision=settings.embedding_model_revision,
        dimensions=settings.embedding_dimensions,
        batch_size=settings.embedding_batch_size,
    )
    embedding = OllamaEmbeddingAdapter(
        manifest,
        base_url=str(settings.embedding_base_url),
        timeout_seconds=settings.embedding_timeout_seconds,
    )
    store = SupabaseVectorStore(
        base_url=str(settings.supabase_url),
        api_key=settings.supabase_admin_api_key.get_secret_value(),
    )
    wiki = WikiClient(
        api_url=str(settings.wiki_api_url),
        base_url=str(settings.wiki_base_url),
        user_agent=settings.wiki_user_agent,
        timeout_seconds=settings.wiki_request_timeout_seconds,
    )
    try:
        for title in args.titles:
            page = wiki.fetch(title)
            chunks = prepare_chunks(page)
            vectors = embedding.embed([chunk.content for chunk in chunks])
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
            store.replace_page(page.title, rows)
            print(f"Ingested {page.title}: {len(rows)} chunks")
    finally:
        wiki.close()
        store.close()
        embedding.close()


if __name__ == "__main__":
    main()
