# DST Vietnamese Knowledge Assistant

An unofficial, source-grounded Vietnamese assistant for **Don't Starve Together**. The planned system uses FastAPI, Next.js, and Supabase PostgreSQL. Supabase is the production knowledge source; the browser communicates only with FastAPI.

Milestones 0 through 7 provide the verified application foundation, private Supabase knowledge
platform, revision-aware ingestion and processing, Vietnamese terminology, embeddings, hybrid
retrieval, and fail-closed grounded generation with validated citations. See `planning.md` for the
authoritative architecture and `IMPLEMENTATION_STATUS.md` for verified progress.

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

## Corpus processing and chunking

Build a new corpus from every active raw wiki revision with a backend-only Supabase credential:

```bash
uv run python -m scripts.build_corpus --version milestone3-local-v1
```

`make build-corpus` runs the same pipeline with an automatically timestamped version. The processor
parses MediaWiki sections and infobox facts, normalizes wiki tables, removes navigation and
boilerplate sections, classifies game scope and entity type with recorded evidence, and creates
deterministic section-aware chunks. Each chunk carries its title, section path, canonical URL,
revision, scope, entity type, source key, and normalization/search metadata.

Validation rejects empty content, incomplete provenance, unexplained duplicates, uncovered source
pages, and an empty corpus before any chunks are inserted. Exact duplicate bodies are filtered and
recorded as explained validation issues. Structured table and infobox blocks stay atomic even when
they exceed the normal 600-token chunk ceiling so a stat or recipe row is not split from its
context.

Milestone 3 deliberately leaves a successful corpus in `building` with a `pending-1024` embedding
manifest. It does not create vectors or activate the corpus; Milestones 5 and 6 complete those
steps. Rebuilding the same non-active version safely resets its chunks, while active and archived
versions are protected from reset.

## Vietnamese terminology and aliases

`data/glossary/dst_vi_glossary.csv` is the reviewed terminology source of truth. Synchronize it
with a backend-only credential:

```bash
uv run python -m scripts.sync_aliases
```

The normalizer retains the original query for later embeddings while producing Unicode NFC,
lowercase, punctuation-normalized, and Vietnamese accent-insensitive variants. The resolver ranks
canonical titles, verified translations, community aliases, abbreviations, common misspellings,
and descriptive aliases before unverified generated candidates. Query expansion is bounded and
uses only repository or stored aliases; it does not invent aliases with an LLM.

## Embeddings and search indexes

Embed one non-active corpus with the configured Ollama model:

```bash
uv run python -m scripts.embed_corpus --corpus-version milestone5-local-v1
```

The default contract is Ollama `bge-m3`, 1024 dimensions, cosine distance, normalized vectors, and
16-item batches. The worker validates batch cardinality, dimensions, finite values, and unit length;
records provider/database failures on every affected chunk; resumes only chunks still missing a
vector; and advances a fully embedded corpus to `validating`, never `active`. It sends
`truncate=false` so overlong content fails visibly instead of silently changing evidence.

For dependency-free local acceptance only, pass `--provider deterministic`. These hash vectors
exercise storage, dimensions, HNSW, FTS, retry, and query plumbing but are not a production semantic
model. The database exposes backend-only lexical and semantic diagnostic RPCs, a GIN FTS index, and
a cosine HNSW index. `make embed-corpus CORPUS_VERSION=<version>` wraps the worker.

## Hybrid retrieval

The backend retrieval service normalizes and expands the query, verifies that its query-embedding
model matches the active corpus, and calls a backend-only PostgreSQL RPC. The RPC independently
ranks FTS and cosine candidates, filters the single active corpus and exact `dst` scope, fuses ranks
with RRF, and adds bounded resolved-entity and section-intent boosts. The backend then applies an
auditable reranker, evidence threshold, body-hash deduplication, per-section limits, and an 1800-token
context budget with stable `CTX-*` identifiers.

Evaluate an active corpus against the version-controlled milestone set:

```bash
uv run python -m scripts.evaluate_retrieval
```

`make evaluate-retrieval` wraps the same command. Retrieval fails closed when no corpus is active or
when its embedding model differs from the query adapter. Milestone 6 acceptance temporarily activates
and restores a local test corpus; production activation and rollback remain Milestone 9 work.

## Grounded generation and citations

`POST /api/chat` runs the complete backend-only pipeline: stored alias resolution, query embedding,
active-corpus hybrid retrieval, reranking, bounded context assembly, Ollama generation, and citation
validation. The model receives only accepted chunks with stable `S1`, `S2`, ... identifiers. A
factual response is returned only when every citation exists in that evidence set, belongs to the
active corpus, and any numeric claim appears in its cited source. Invalid or missing citations are
replaced with a deterministic abstention instead of exposing ungrounded model output.

Explicit comparisons require evidence for every resolved entity. Structured source conflicts are
reported in the response, and guide evidence sets `subjective_warning`. Retrieved source text is
treated as untrusted data: instructions inside a wiki chunk are delimited and explicitly ignored by
the grounded system prompt.

With a validated active corpus, synchronized aliases, matching embedding configuration, and the
configured Ollama models running, call the API from PowerShell:

```powershell
$body = @{ message = "Mũ da heo bảo vệ như thế nào?" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/chat `
  -ContentType application/json -Body $body
```

The response includes `answer`, validated `citations`, `resolved_entities`, confidence, abstention
state/reason, corpus version, subjective/conflict flags, and measured stage latencies. The endpoint
returns a sanitized `503` when Supabase, embeddings, or Ollama are unavailable.

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

Use only development Supabase credentials locally. Raw corpus files, caches, keys, and generated builds are ignored. This is an unofficial project and is not affiliated with Klei Entertainment. Raw ingestion preserves the site-reported license, canonical URL, revision, and attribution; corpus processing carries source identity and revision provenance into every chunk for later citation construction.
