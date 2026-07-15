# Repository Guidelines

## Project Structure & Module Organization

This repository is currently planning-only; `planning.md` is the implementation source of truth. The planned layout places the FastAPI application in `apps/api/`, the Next.js or React frontend in `apps/web/`, and reusable Python code in `src/`. Keep ingestion, Vietnamese normalization, retrieval, generation, and evaluation logic in their matching `src/` packages. Put Supabase migrations in `supabase/migrations/`, operational entry points in `scripts/`, fixtures and evaluation sets in `data/`, and tests in `tests/unit/`, `tests/integration/`, or `tests/e2e/`. Treat `data/cache/` as disposable; Supabase remains the production knowledge source.

## Build, Test, and Development Commands

The Makefile has not been created yet. Once the scaffold exists, preserve the command interface proposed in `planning.md`:

- `make install` — install backend and frontend dependencies.
- `make supabase-start && make supabase-migrate` — start and migrate local Supabase.
- `make sync` — fetch and process wiki revisions.
- `make evaluate` — run retrieval and answer evaluation.
- `make dev` — start local development services.
- `pytest` — run Python tests; use `pytest tests/unit` for a focused check.

Do not claim these commands work until their targets and dependency manifests are committed.

## Coding Style & Naming Conventions

Target Python 3.12+, four-space indentation, type hints, `snake_case` modules/functions, and `PascalCase` classes. Use TypeScript for frontend code, with `PascalCase` components and `camelCase` functions. Keep modules narrowly scoped and mirror existing names such as `mediawiki_client.py` and `citation_builder.py`. No formatter or linter is configured yet; add and document one before enforcing it in CI.

## Testing Guidelines

Use pytest and name files `test_<behavior>.py`. Unit-test deterministic normalization, chunking, aliases, and citations. Integration tests should cover MediaWiki fixtures, Supabase RPC/storage, idempotent upserts, and mocked LLM calls. Reserve E2E tests for chat, outage, invalid-secret, and corpus-activation flows. Any retrieval change must include benchmark results; protect citation correctness and DST scope filtering.

## Commit & Pull Request Guidelines

No Git history is available here, so no repository-specific convention can be inferred. Use short imperative subjects, for example `Add hybrid search migration`, and keep commits focused. Pull requests should explain the change, list validation commands, note schema/config effects, link an issue when available, and include UI screenshots for visible changes.

## Security & Configuration

Copy settings from `.env.example` when it is added; never commit `.env`, Supabase secret/service-role keys, or provider tokens. Keep privileged keys backend-only, buckets private, admin endpoints non-public, and all schema changes in migrations.
