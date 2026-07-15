# Implementation Status

## Current Milestone

Milestone 2 - Wiki Discovery and Raw Ingestion: **Complete**

Next: Milestone 3 - Processing, Classification, and Chunking. Work is paused for user verification.

## Milestone 2 Completed

- Verified `https://dontstarve.wiki.gg/api.php` and recorded MediaWiki version, namespace map, and
  the site-reported CC BY-SA 4.0 license.
- Added a serial MediaWiki client with an identifying User-Agent, gzip, `maxlag`, request throttling,
  bounded exponential retry, disposable cache, continuation support, and batched revision fetches.
- Added a version-controlled discovery policy with seed page/category, namespace allowlist and
  denylist, title/category denylists, page/member caps, breadth-first depth limits, page-ID
  deduplication, and an explicit include/exclude report.
- Added revision-aware raw retrieval that preserves page ID, canonical URL, latest revision ID and
  timestamp, MediaWiki SHA-1, raw wikitext, and a schema-compatible SHA-256 content hash.
- Added backend-only Supabase persistence for deterministic private Storage objects,
  `wiki_pages` revision upserts, prior-revision deactivation, source attribution, and complete
  `sync_runs` counters/details.
- Added idempotency checks that skip Storage upload and database upsert for an existing immutable
  `(mediawiki_page_id, revision_id)` pair.
- Added `wiki-check`, `discover`, and `sync` scripts/Make targets plus fixture-based unit tests and an
  opt-in live 30-page ingestion test.
- Stored 30 locally verified pages discovered directly from the DST seed/category. All 30 have
  deterministic raw paths, preliminary `dst` scope, attribution rows, and private raw objects.

## Files Modified

- `.env.example`
- `Makefile`
- `data/ingestion/discovery_config.json`
- `src/config/settings.py`
- `src/ingestion/`
- `src/supabase_store/`
- `scripts/check_wiki.py`
- `scripts/discover_pages.py`
- `scripts/sync_wiki.py`
- `tests/fixtures/mediawiki/`
- `tests/unit/test_mediawiki_client.py`
- `tests/unit/test_page_discovery.py`
- `tests/unit/test_sync_manager.py`
- `tests/integration/test_milestone2_ingestion.py`
- `README.md`
- `IMPLEMENTATION_STATUS.md`

## Verification

Executed on 2026-07-15:

```text
uv run python -m scripts.check_wiki                         passed (MediaWiki 1.43.6)
uv run python -m scripts.discover_pages --max-pages 30
  --max-depth 1                                             passed (30 included, 1 duplicate excluded)
uv run python -m scripts.sync_wiki --max-pages 30
  --max-depth 1                                             passed (30 changed, 30 uploaded, 0 errors)
uv run python -m scripts.sync_wiki --max-pages 30
  --max-depth 1 --sync-type incremental                     passed (0 changed, 30 unchanged,
                                                                    0 uploaded, 0 errors)
live database/Storage inspection                            passed
  wiki pages / preliminary DST scope                        30 / 30
  attribution rows                                          30
  malformed deterministic raw paths                         0
  private raw-object sample reads with server key            3 / 3
  anonymous raw-object read                                 denied (HTTP 400)
  incremental sync include/exclude report                   30 / 1
live tests/integration/test_milestone2_ingestion.py -q      passed (1 test)
uv run ruff format --check .                                passed (26 files)
uv run ruff check .                                         passed
uv run mypy                                                 passed
uv run pytest -q                                            passed (10, 4 integration skipped)
npm run lint:web                                            passed
npm run typecheck:web                                       passed
npm run build:web                                           passed
npx supabase db lint --local --schema knowledge             passed (no schema errors)
npx supabase migration list --local                         passed (2 migrations applied)
git diff --check                                            passed
working-diff secret pattern scan                            passed (0 matches)
```

The four integration tests skip in the default suite because they require explicit local
credentials and, for Milestone 2, live wiki access. The Milestone 2 test was also executed
separately against the running local Supabase stack and live bounded API; it passed.

## Unverified Criteria

- The ingestion was not executed against a hosted Supabase project; only the local stack was used.
- Hosted-project Storage quotas, key behavior, and network latency remain environment-specific.
- HTML fallback was not required because the Action API returned current revision content. The MVP
  rule remains to use HTML only as a documented fallback without bypassing robots or anti-bot rules.

## Known Issues and Deferred Work

- Page scope is preliminary and comes from the explicitly DST discovery seed/category. Milestone 3
  must classify actual page/section content and correct mixed-version pages before chunking.
- The local MediaWiki cache stores only site information and discovery responses; latest revision
  content is always fetched live. `data/cache/` remains disposable.
- Processing, classification, chunking, embeddings, and active-corpus construction are intentionally
  deferred to Milestones 3 through 5.
- The user's PowerShell profile contains an unrelated parse error and prints noise before command
  output. Repository commands still execute successfully.

## Completed Milestones

- Milestone 0 - Repository and Supabase Foundation (`7c99299`)
- Milestone 1 - Database, Extensions, and Storage (`10613e1`)
- Milestone 2 - Wiki Discovery and Raw Ingestion
