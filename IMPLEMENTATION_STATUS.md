# Implementation Status

## Current Milestone

Milestone 9 - Incremental Sync and Corpus Activation: **Complete**

Next: Milestone 10 - Evaluation, Security, Recovery, and Release.

## Milestone 9 Completed

- Preserved revision-aware incremental ingestion and changed `make sync` to record incremental runs
  by default.
- Documented and verified the complete-regeneration strategy: build a full new corpus from current
  immutable revisions without editing active chunks in place.
- Added a database readiness validator covering lifecycle state, processing/embedding manifests,
  exact counts, complete current-page coverage, non-stale revisions, provenance, and embeddings.
- Added protected PostgreSQL activation and rollback RPCs that archive/activate versions in one
  transaction while preserving the one-active-corpus invariant.
- Added backend lifecycle adapters and CLI/Make commands for activation and rollback.
- Added deterministic gzip JSONL snapshot export containing corpus, pages, attributions, aliases,
  chunks, and embeddings.
- Added private Storage upload to deterministic paths, SHA-256 checksum and record-count manifests,
  and corpus-manifest audit metadata.
- Added standalone export plus automatic snapshot creation after normal activation.
- Added local integration acceptance for first activation, replacement/archive, private snapshot,
  rollback, and exact single-active-corpus state.

## Verification

Executed on 2026-07-15:

```text
uv run ruff format --check .                                 passed (95 files)
uv run ruff check .                                          passed
uv run mypy                                                  passed (95 source files)
uv run pytest -q                                             passed (44, 9 integration skipped)
npm run lint:web                                             passed
npm run typecheck:web                                        passed
npm run build:web                                            passed
npx supabase db reset                                        passed (6 migrations)
npx supabase db lint --local --schema knowledge              passed
npx supabase migration list --local                          passed (6 migrations)
live tests/integration/test_milestone9_lifecycle.py -q       passed (1 test)
```

The live test used the local development stack only and cleaned up its corpus rows and Storage
objects after proving activation, archive, snapshot integrity metadata, and rollback behavior.

## Unverified Criteria

- The release flow deliberately regenerates unchanged chunks instead of copying them. This is safer
  and simpler for the current corpus size but uses more processing and embedding work.
- Hosted-Supabase activation and snapshot upload were not performed; lifecycle acceptance used the
  local development stack.
- Scheduled synchronization is not configured because deployment scheduling depends on the selected
  release environment.

## Known Issues and Deferred Work

- The configured hosted project was not migrated or mutated; database verification used the local
  Supabase development stack.
- The PowerShell profile parse warning is environmental and did not change any command exit status.

## Completed Milestones

- Milestone 0 - Repository and Supabase Foundation (`7c99299`)
- Milestone 1 - Database, Extensions, and Storage (`10613e1`)
- Milestone 2 - Wiki Discovery and Raw Ingestion (`2f4ca03`)
- Milestone 3 - Processing, Classification, and Chunking (`5ed2f75`)
- Milestone 4 - Vietnamese Terminology and Alias Layer (`1b42ff1`)
- Milestone 5 - Embeddings and Search Indexes (`ece8130`)
- Milestone 6 - Hybrid Retrieval (`c6a0501`)
- Milestone 7 - Generation, Guardrails, and Citations (`6cc160b`)
- Milestone 8 - Web Interface (`baba297`)
- Milestone 9 - Incremental Sync and Corpus Activation
