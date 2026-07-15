# Implementation Status

## Current Milestone

Milestone 1 - Database, Extensions, and Storage: **Complete**

Next: Milestone 2 - Wiki Discovery and Raw Ingestion. Work is paused for user verification.

## Milestone 1 Completed

- Enabled `vector`, `pg_trgm`, and `unaccent` through a version-controlled migration.
- Created the `knowledge` schema and all seven required MVP tables:
  `embedding_models`, `corpus_versions`, `wiki_pages`, `document_chunks`,
  `entity_aliases`, `source_attributions`, and `sync_runs`.
- Added foreign keys, value checks, deterministic uniqueness constraints, the single-active-corpus
  constraint, the generated FTS column, GIN/trigram indexes, and supporting B-tree indexes.
- Fixed the initial embedding column at `vector(1024)` and documented the migration requirement for
  dimension changes.
- Enabled RLS on every knowledge table, revoked `anon` and `authenticated` privileges, and granted
  backend-only access to `service_role`.
- Created `dst-wiki-raw`, `dst-corpus-snapshots`, and `dst-evaluation-reports` as private buckets.
- Added idempotent synthetic development fixtures without representing them as wiki facts.
- Added live integration tests for anonymous read/write denial, service-role CRUD, and private object
  access.

## Files Modified

- `.env.example`
- `supabase/config.toml`
- `supabase/migrations/20260715010000_knowledge_schema_and_storage.sql`
- `supabase/seed.sql`
- `tests/integration/test_milestone1_access.py`
- `README.md`
- `IMPLEMENTATION_STATUS.md`

## Verification

Executed on 2026-07-15:

```text
npx supabase db reset                                      passed (both migrations and seed)
npx supabase db lint --local --schema knowledge            passed (no schema errors)
npx supabase migration list --local                        passed (2 migrations applied)
live tests/integration/test_milestone1_access.py            passed (3 tests)
database schema inspection                                 passed
  extensions                                               pg_trgm, unaccent, vector
  knowledge tables                                         7
  RLS-enabled knowledge tables                             7
  embedding type                                           vector(1024)
  private required buckets                                 3
uv run ruff format --check .                               passed (13 files)
uv run ruff check .                                        passed
uv run mypy                                                passed
uv run pytest -q                                           passed (4, 3 integration skipped)
npm run lint:web                                           passed
npm run typecheck:web                                      passed
npm run build:web                                          passed
```

The three integration tests skip in the default suite because they require explicit local test
credentials. They were also executed separately against the reset local Supabase stack and all
three passed.

## Unverified Criteria

- The migration was not applied to a hosted Supabase project; only the clean local stack was used.
- Hosted-project extension availability and service-role behavior remain environment-specific.

## Known Issues and Deferred Work

- HNSW creation and vector query-plan verification belong to Milestone 5, after embeddings exist.
- The user's PowerShell profile contains an unrelated parse error and prints noise before command
  output. Repository commands still execute successfully.

## Completed Milestones

- Milestone 0 - Repository and Supabase Foundation (`7c99299`)
- Milestone 1 - Database, Extensions, and Storage

