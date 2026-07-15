# Implementation Status

## Current Milestone

Milestone 5 - Embeddings and Search Indexes: **Complete**

Next: Milestone 6 - Hybrid Retrieval.

## Milestone 5 Completed

- Added a configurable embedding adapter contract and an Ollama `/api/embed` implementation using
  explicit batch input and `truncate=false`.
- Added manifest validation for provider, model, revision, dimensions, cosine distance,
  normalization behavior, and batch size.
- Added deterministic hash embeddings strictly for dependency-free unit/local acceptance testing.
- Added resumable batch processing that embeds only missing chunks, validates every vector, records
  per-chunk errors, and never advances a partial run beyond `building`.
- Added backend-only model manifest creation, corpus/model binding, vector persistence, and protected
  lexical/semantic diagnostic RPCs.
- Added the 1024-dimensional cosine HNSW index; the existing generated FTS column and GIN index are
  retained.
- Added CLI/Make targets and an opt-in live acceptance test covering corpus rebuild, 100% vector
  population, FTS search, vector search, and a zero-work resumable rerun.

## Verification

Executed on 2026-07-15:

```text
local corpus                                                100 / 100 chunks embedded
embedding retry                                             passed (0 new vectors)
vector dimensions / distance                                1024 / cosine
semantic sample                                             correct page ranked first
FTS sample                                                  correct page ranked first
HNSW EXPLAIN                                                document_chunks_embedding_hnsw_idx
FTS EXPLAIN                                                 document_chunks_fts_idx
live tests/integration/test_milestone5_embeddings.py -q     passed (1 test)
uv run ruff check .                                         passed
uv run mypy                                                 passed (58 source files)
uv run pytest -q                                            passed (28, 7 integration skipped)
npx supabase db lint --local --schema knowledge             passed
npx supabase migration list --local                         passed (4 migrations)
```

## Unverified Criteria

- Ollama `bge-m3` was not downloaded or executed; the production adapter is contract-tested with a
  mock response and local acceptance uses the explicitly marked deterministic provider.
- Embedding and index acceptance was run against local Supabase, not the configured hosted project.
- Semantic quality is measured in Milestone 6 rather than inferred from deterministic test vectors.

## Known Issues and Deferred Work

- A corpus-filtered nearest-neighbor query on the current 100-row corpus chooses the selective
  corpus B-tree index plus sort; the HNSW plan is verified for the unfiltered nearest-neighbor shape.
- Hybrid fusion, alias/entity boosts, reranking, evidence thresholds, context assembly, and retrieval
  metrics are Milestone 6 work.
- Corpus activation remains intentionally deferred to Milestone 9.
- The user's `prompt.md` modification and `milestone0.md` deletion remain untouched.

## Completed Milestones

- Milestone 0 - Repository and Supabase Foundation (`7c99299`)
- Milestone 1 - Database, Extensions, and Storage (`10613e1`)
- Milestone 2 - Wiki Discovery and Raw Ingestion (`2f4ca03`)
- Milestone 3 - Processing, Classification, and Chunking (`5ed2f75`)
- Milestone 4 - Vietnamese Terminology and Alias Layer (`1b42ff1`)
- Milestone 5 - Embeddings and Search Indexes
