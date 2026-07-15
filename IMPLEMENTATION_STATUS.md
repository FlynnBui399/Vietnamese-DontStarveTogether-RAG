# Implementation Status

## Current Milestone

Milestone 3 - Processing, Classification, and Chunking: **Complete**

Next: Milestone 4 - Vietnamese Normalization and Search Fields. Work is paused for user verification.

## Milestone 3 Completed

- Added a MediaWiki-aware cleaner that preserves heading hierarchy, paragraphs, lists, infobox
  facts, table field/value structure, and revision provenance while dropping navigation, gallery,
  reference, skin, asset, and other boilerplate sections and their descendants.
- Added evidence-recording page and section classification for `dst`, `dont_starve`, `mixed`, and
  `unknown` scope plus the planned entity and source-kind labels.
- Added deterministic page/section/subsection chunking with contextual headers, 450-token targets,
  60-token overlap, atomic table/infobox/list blocks, normalized content, search text, and SHA-256
  source/content keys.
- Added corpus validation for required metadata, empty chunks, exact duplicates, source-page
  coverage, and overall metadata completeness. Exact duplicate bodies are filtered only when the
  duplicate is explicitly reported.
- Added a backend-only corpus builder that reads immutable raw Storage objects, persists page
  classifications, inserts only a fully validated chunk set, records a validation manifest, and
  marks failed builds without inserting chunks.
- Added a safe rebuild policy for non-active corpus versions and changed source-key uniqueness from
  global to per-corpus so deterministic chunks can legitimately recur in later corpus versions.
- Added `build-corpus` script/Make targets, focused fixtures and unit tests, and an opt-in live local
  Supabase integration test.
- Built and inspected `milestone3-local-v1` locally: 30 source pages, 30 covered pages, 102 candidate
  chunks, 100 inserted chunks, two explained exact duplicates, zero empty chunks, zero missing
  required metadata fields, and zero retained boilerplate-section headings.

## Files Modified

- `Makefile`
- `pyproject.toml`
- `uv.lock`
- `src/config/settings.py`
- `src/processing/`
- `src/supabase_store/processing_repository.py`
- `src/supabase_store/__init__.py`
- `scripts/build_corpus.py`
- `supabase/migrations/20260715020000_processing_corpus_constraints.sql`
- `tests/fixtures/processing/`
- `tests/unit/test_processing_cleaner.py`
- `tests/unit/test_processing_classifier.py`
- `tests/unit/test_processing_chunker.py`
- `tests/unit/test_processing_validator.py`
- `tests/unit/test_corpus_builder.py`
- `tests/integration/test_milestone3_processing.py`
- `README.md`
- `IMPLEMENTATION_STATUS.md`

## Verification

Executed on 2026-07-15:

```text
uv run python -m scripts.build_corpus
  --version milestone3-local-v1                              passed (30 pages, 100 chunks)
same-version local corpus rebuild                           passed (safe and idempotent)
live corpus/database inspection                             passed
  source-page coverage                                      30 / 30
  metadata completeness                                     100%
  empty / duplicate inserted bodies                           0 / 0
  explained candidate duplicates                              2
  retained boilerplate headings                               0
  corpus state / embedding state                            building / pending
live tests/integration/test_milestone3_processing.py -q     passed (1 test)
uv run ruff format --check .                                passed
uv run ruff check .                                         passed
uv run mypy                                                 passed
uv run pytest -q                                            passed (21, 5 integration skipped)
npm run lint:web                                            passed
npm run typecheck:web                                       passed
npm run build:web                                           passed
npx supabase db lint --local --schema knowledge             passed (no schema errors)
npx supabase migration list --local                         passed (3 migrations applied)
git diff --check                                            passed
working-diff secret pattern scan                            passed (0 matches)
```

The five integration tests skip in the default suite because they require explicit local
credentials and, for Milestone 2, live wiki access. The Milestone 3 test was also executed
separately against the running local Supabase stack; it passed and created another valid corpus
version with the same deterministic source keys.

## Unverified Criteria

- Corpus processing was not executed against a hosted Supabase project; only the local stack was
  used.
- Hosted-project Storage quotas, key behavior, and network latency remain environment-specific.
- Retrieval quality is not evaluated in Milestone 3 because embeddings and hybrid search are
  introduced in Milestones 5 and 6.

## Known Issues and Deferred Work

- One structured block is approximately 721 tokens, above the normal 600-token ceiling. It remains
  atomic intentionally because splitting table/infobox facts would violate the chunking rule.
- The `pending-1024` embedding manifest is an explicit placeholder, not a model choice. Milestone 5
  must replace it before vectors are written.
- Accent-insensitive Vietnamese normalization, query expansion, embeddings, retrieval, and corpus
  activation are intentionally deferred to Milestones 4 through 6 and 9.
- The user's PowerShell profile contains an unrelated parse error and prints noise before command
  output. Repository commands still execute successfully.

## Completed Milestones

- Milestone 0 - Repository and Supabase Foundation (`7c99299`)
- Milestone 1 - Database, Extensions, and Storage (`10613e1`)
- Milestone 2 - Wiki Discovery and Raw Ingestion (`2f4ca03`)
- Milestone 3 - Processing, Classification, and Chunking
