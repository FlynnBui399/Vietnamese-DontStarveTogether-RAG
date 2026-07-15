# Deployment Guide

## Supported MVP topology

- Frontend: Next.js on Vercel or another Node 22+ host.
- API: FastAPI on a long-running Python 3.12+ service.
- Knowledge platform: Supabase PostgreSQL and private Storage.
- Generation: Ollama on a network-restricted host reachable only by FastAPI.
- Scheduled worker: the same Python package on a trusted runner.

The browser communicates only with FastAPI. Do not put a Supabase secret/service-role key, database
URL, Ollama endpoint, or admin credential in a `NEXT_PUBLIC_*` variable.

## Backend environment

Start from `.env.example`. Production requires at least:

```text
APP_ENV=production
FRONTEND_ORIGIN=https://your-frontend.example
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SECRET_KEY=<secret manager value>
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=bge-m3
OLLAMA_BASE_URL=http://private-ollama:11434
LLM_MODEL=qwen2.5:7b-instruct
```

Expose the `knowledge` schema in the Supabase Data API configuration. Apply migrations from CI or a
trusted operator with `npx supabase db push`; do not edit production tables in the dashboard. The
backend needs a server secret/service-role credential because all knowledge tables and lifecycle
RPCs deny `anon` and `authenticated`.

## Frontend environment

```text
NEXT_PUBLIC_API_BASE_URL=https://your-api.example
```

Build with `npm ci && npm run build:web`. Response security headers and the API origin are emitted by
`next.config.ts`. Keep frontend and API on HTTPS. Update `FRONTEND_ORIGIN` exactly; the API does not
allow wildcard CORS.

## Release sequence

```bash
uv sync --frozen
npm ci
npx supabase db push
uv run python -m scripts.check_supabase
make release-corpus CORPUS_VERSION=2026-07-15.1
make evaluate
uv run uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
```

`release-corpus` stops on sync, build, or embedding failure. Activation is the last stage and creates
a private snapshot. Run the release benchmark immediately afterward; if a replacement version misses
quality targets, roll back to the archived version.

## Production controls

- Put FastAPI behind a reverse proxy with TLS, body-size limits, request timeouts, and a shared or
  gateway rate limiter. The built-in limiter is per process and is only a last line of defense.
- Keep Ollama private; do not expose it to the browser or public internet.
- Use a Supabase region near the API and monitor database/storage quotas, connection count, and egress.
- Configure worker scheduling only after choosing a platform. One weekly incremental sync is a
  reasonable starting assumption; the MediaWiki client remains serial and rate limited.
- Configure Supabase managed backups/PITR according to the paid plan. Application snapshots are an
  additional recovery layer, not a substitute for database backups.

## Cost and quota assumptions

The MVP stores text, metadata, 1024-dimensional vectors, raw JSON, evaluation reports, and compressed
snapshots; it does not copy game images or video. Main cost drivers are Supabase database compute,
vector index size, Storage/egress, API hosting, and Ollama hardware. Monitor actual page/chunk/vector
counts before choosing a plan. HNSW builds and full regeneration temporarily require extra compute,
and keeping many archived snapshots increases Storage usage. No fixed monthly cost is claimed.
