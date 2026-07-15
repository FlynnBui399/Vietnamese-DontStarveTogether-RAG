# DST Vietnamese Knowledge Assistant

An unofficial, source-grounded Vietnamese assistant for **Don't Starve Together**. The planned system uses FastAPI, Next.js, and Supabase PostgreSQL. Supabase is the production knowledge source; the browser communicates only with FastAPI.

Milestones 0 through 2 provide the verified application foundation, private Supabase knowledge platform, and bounded revision-aware wiki ingestion. Corpus processing, retrieval, and generation are implemented in subsequent milestones. See `planning.md` for the authoritative architecture and `IMPLEMENTATION_STATUS.md` for verified progress.

## Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and npm
- Docker Desktop for local Supabase

## Install

```bash
uv sync
npm install
```

Copy `.env.example` to `.env`. Do not commit `.env`. Start the development Supabase stack and print its local values:

```bash
npm run supabase:start
npm run supabase:status -- -o env
```

Put the local project URL and a local publishable, secret, or legacy service-role key in `.env`. Never put a secret/service-role key in a `NEXT_PUBLIC_*` variable.

Apply all migrations and seed the synthetic development fixture on a clean local database:

```bash
npx supabase db reset
```

## Database foundation

The `knowledge` schema stores pages, chunks, aliases, attributions, corpus versions, sync runs, and embedding-model manifests. All knowledge tables use RLS and deny `anon` and `authenticated` access. Backend and worker code must use a server-side secret/service-role credential.

The initial vector schema is fixed at 1024 dimensions. A model with another dimension requires a new migration and rebuilt corpus; vectors must not be coerced into the existing column.

The following private buckets are created by migration:

- `dst-wiki-raw`
- `dst-corpus-snapshots`
- `dst-evaluation-reports`

## Wiki discovery and raw ingestion

The version-controlled scope in `data/ingestion/discovery_config.json` starts from the main DST page
and `Category:Don't Starve Together`. It permits only article namespace `0`, rejects known
non-content namespaces and excluded title/category patterns, caps category depth and members, and
deduplicates by MediaWiki page ID. Change this file deliberately instead of adding a full hard-coded
page list.

Verify the endpoint and inspect its namespaces/license, then preview the include/exclude report
without writing to Supabase:

```bash
uv run python -m scripts.check_wiki
uv run python -m scripts.discover_pages --max-pages 30 --max-depth 1
```

Run raw ingestion with a backend-only Supabase secret or legacy service-role key:

```bash
uv run python -m scripts.sync_wiki --max-pages 30 --max-depth 1
```

Add `--report data/cache/milestone2-sync.json` to either discovery or sync to retain the report in
the disposable local cache. The sync report is always stored in `knowledge.sync_runs.details`.
`make wiki-check`, `make discover`, and `make sync` wrap the default forms of these commands.

The client sends an identifying User-Agent, gzip support, `maxlag`, serial throttling, bounded retry,
and caches only discovery/site-information requests. Latest revisions are fetched live in batches.
Raw objects use the deterministic private path `pages/{page_id}/{revision_id}.json`. A rerun checks
the immutable `(mediawiki_page_id, revision_id)` pair and does not upload or upsert an unchanged
revision. The current discovery policy assigns preliminary `dst` page scope from the explicitly DST
seed/category; Milestone 3 performs content-level scope and entity classification.

To rerun the live access-control checks in PowerShell without writing local credentials to a file:

```powershell
$status = npx supabase status -o json 2>$null | ConvertFrom-Json
$env:SUPABASE_TEST_URL = $status.API_URL
$env:SUPABASE_TEST_ANON_KEY = $status.ANON_KEY
$env:SUPABASE_TEST_SERVICE_ROLE_KEY = $status.SERVICE_ROLE_KEY
uv run pytest tests/integration/test_milestone1_access.py -q
Remove-Item Env:SUPABASE_TEST_URL, Env:SUPABASE_TEST_ANON_KEY, Env:SUPABASE_TEST_SERVICE_ROLE_KEY
```

## Run locally

Start both applications:

```bash
npm run dev
```

Or run them in separate terminals:

```bash
uv run uvicorn apps.api.main:app --reload
npm run dev --workspace @dst-rag/web
```

Open `http://127.0.0.1:3000`. The API health response is available at `http://127.0.0.1:8000/api/health`.

## Quality checks

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
npm run lint:web
npm run typecheck:web
npm run build:web
uv run python -m scripts.check_supabase
```

On systems with GNU Make, `make install`, `make check`, and `make supabase-check` wrap the same commands.

## Security and attribution

Use only development Supabase credentials locally. Raw corpus files, caches, keys, and generated builds are ignored. This is an unofficial project and is not affiliated with Klei Entertainment. Raw ingestion preserves the site-reported license, canonical URL, revision, and attribution; later processing must carry them into every chunk and citation.
