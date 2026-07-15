# Implementation Status

## Current Milestone

Milestone 4 - Vietnamese Terminology and Alias Layer: **Complete**

Next: Milestone 5 - Embeddings and Search Indexes.

## Milestone 4 Completed

- Added deterministic Unicode NFC, typography, whitespace, lowercase, and Vietnamese
  accent-insensitive normalization while retaining the original query for embeddings.
- Added a reviewed CSV glossary with 34 canonical, community, misspelling, and descriptive aliases
  across 12 DST entities.
- Added language hints for Vietnamese, English, and mixed queries without blindly translating
  proper names.
- Added exact-title, exact-alias, prefix/contained-entity, and fuzzy resolution with explicit alias
  priority, confidence, verification, and source evidence.
- Added bounded deterministic query expansion and guaranteed that unverified generated candidates
  cannot outrank an otherwise equivalent verified alias.
- Added backend-only, idempotent Supabase alias upserts and deterministic alias reads.
- Updated new corpus chunks so `content_normalized` is truly accent-insensitive.
- Fixed `WIKI_MAX_CONCURRENCY=1` environment parsing while retaining the required serial limit.

## Verification

Executed on 2026-07-15:

```text
required resolution: mu da heo                              Football Helmet
required resolution: da giu nhiet                           Thermal Stone
required resolution: nhan vat di cung ma                    Wendy
repository glossary                                         34 / 34 verified aliases
live alias sync twice                                       passed (stable row count)
live tests/integration/test_milestone4_aliases.py -q         passed (1 test)
uv run ruff format --check .                                passed (50 files)
uv run ruff check .                                         passed
uv run mypy                                                 passed (50 source files)
uv run pytest -q                                            passed (25, 6 integration skipped)
```

## Unverified Criteria

- Alias synchronization was verified against local Supabase, not the configured hosted project.
- The glossary is deliberately small for the milestone and requires continued human review as the
  corpus expands.

## Known Issues and Deferred Work

- Embeddings, vector indexes, hybrid retrieval, reranking, and retrieval evaluation begin in
  Milestones 5 and 6.
- The user's `.env` currently targets a hosted Supabase endpoint while database acceptance tests use
  explicit local credentials.
- The user's `prompt.md` modification and `milestone0.md` deletion remain untouched.

## Completed Milestones

- Milestone 0 - Repository and Supabase Foundation (`7c99299`)
- Milestone 1 - Database, Extensions, and Storage (`10613e1`)
- Milestone 2 - Wiki Discovery and Raw Ingestion (`2f4ca03`)
- Milestone 3 - Processing, Classification, and Chunking (`5ed2f75`)
- Milestone 4 - Vietnamese Terminology and Alias Layer
