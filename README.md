# DST Vietnamese Knowledge Assistant

An unofficial, source-grounded Vietnamese assistant for **Don't Starve Together**. The planned system uses FastAPI, Next.js, and Supabase PostgreSQL. Supabase is the production knowledge source; the browser communicates only with FastAPI.

Milestone 0 provides the verified repository foundation and health-check UI. Its baseline migration applies to a clean local Supabase database. Database schema, ingestion, retrieval, and generation are implemented in subsequent milestones. See `planning.md` for the authoritative architecture and `IMPLEMENTATION_STATUS.md` for verified progress.

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

Use only development Supabase credentials locally. Raw corpus files, caches, keys, and generated builds are ignored. This is an unofficial project and is not affiliated with Klei Entertainment. Wiki-derived content must retain its canonical URL, revision, and applicable attribution in later milestones.
