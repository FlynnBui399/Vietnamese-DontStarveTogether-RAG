# Implementation Status

## Current Milestone

Milestone 6 - Hybrid Retrieval: **Complete**

Next: Milestone 7 - Generation, Guardrails, and Citations. Work is paused for user verification.

## Milestone 6 Completed

- Added a backend-only PostgreSQL hybrid RPC with a single-active-corpus CTE, exact `dst` scope
  filtering, optional entity-type filtering, FTS and cosine candidate lists, and Reciprocal Rank
  Fusion.
- Added bounded resolved-entity and section-intent score boosts without combining incompatible raw
  BM25 and cosine scales.
- Added active-corpus/model-contract validation before query embedding and retrieval.
- Added a transparent reranker using normalized RRF, title/content overlap, semantic similarity,
  resolved entities, section intent, and a subjective-guide penalty.
- Added an evidence threshold, exact body-hash duplicate removal, hard DST defense, and fixed final
  result count.
- Added diverse context assembly with preferred resolved pages, at most two chunks per page/section,
  an 1800-token budget, and stable `CTX-*` identifiers.
- Added a 20-case version-controlled entity/natural-query benchmark, local p95 measurement, CLI/Make
  evaluation target, and opt-in live acceptance test.
- Expanded the glossary with current-corpus canonical titles and reviewed typo/descriptive aliases
  used by the entity benchmark.

## Verification

Executed on 2026-07-15:

```text
Milestone 6 evaluation cases                                  20
entity Recall@5                                             100% (target >= 90%)
natural-query Recall@10                                     100% (target >= 85%)
non-DST result count                                           0
local Supabase retrieval p95                              13.633 ms (target <= 250 ms)
sample typo: ancent archive                                  rank 1 / Ancient Archive
active corpus/model enforcement                              passed
context threshold/dedup/budget checks                        passed
live tests/integration/test_milestone6_retrieval.py -q       passed (1 test)
uv run ruff format --check .                                 passed
uv run ruff check .                                          passed
uv run mypy                                                  passed (69 source files)
uv run pytest -q                                             passed (32, 8 integration skipped)
npm run lint:web                                             passed
npm run typecheck:web                                        passed
npm run build:web                                            passed
npx supabase db lint --local --schema knowledge              passed
npx supabase migration list --local                          passed (5 migrations)
```

## Unverified Criteria

- The 20-case benchmark is a milestone acceptance set over the current 30-page local corpus, not the
  final 150+ question release benchmark required by Milestone 10.
- Retrieval quality was validated with deterministic test vectors. Ollama `bge-m3` quality, a neural
  cross-encoder reranker, and hosted-Supabase latency remain unverified.
- The configured hosted project was not migrated or mutated; all database acceptance used explicit
  local credentials.

## Known Issues and Deferred Work

- No corpus is left active after acceptance because production activation, rollback, and snapshots
  belong to Milestone 9. Retrieval intentionally fails closed until an active corpus exists.
- The heuristic reranker is auditable and benchmarked on the milestone set but is not equivalent to
  a multilingual neural cross-encoder.
- Generation, factual guardrails, and final citation validation begin in Milestone 7; `CTX-*` values
  are retrieval context identifiers, not yet user-facing citations.
- The user's `prompt.md` modification and `milestone0.md` deletion remain untouched.

## Completed Milestones

- Milestone 0 - Repository and Supabase Foundation (`7c99299`)
- Milestone 1 - Database, Extensions, and Storage (`10613e1`)
- Milestone 2 - Wiki Discovery and Raw Ingestion (`2f4ca03`)
- Milestone 3 - Processing, Classification, and Chunking (`5ed2f75`)
- Milestone 4 - Vietnamese Terminology and Alias Layer (`1b42ff1`)
- Milestone 5 - Embeddings and Search Indexes (`ece8130`)
- Milestone 6 - Hybrid Retrieval
