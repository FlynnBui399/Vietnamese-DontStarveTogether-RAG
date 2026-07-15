.PHONY: install format format-check lint typecheck test check dev run \
	supabase-start supabase-stop supabase-migrate supabase-check \
	wiki-check discover sync build-corpus sync-aliases embed-corpus evaluate-retrieval \
	activate-corpus rollback-corpus export-corpus

install:
	uv sync
	npm install

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

lint:
	uv run ruff check .
	npm run lint:web

typecheck:
	uv run mypy
	npm run typecheck:web

test:
	uv run pytest

check: format-check lint typecheck test
	npm run build:web

dev:
	npm run dev

run:
	uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000

supabase-start:
	npm run supabase:start

supabase-stop:
	npm run supabase:stop

supabase-migrate:
	npx supabase db reset

supabase-check:
	uv run python -m scripts.check_supabase

wiki-check:
	uv run python -m scripts.check_wiki

discover:
	uv run python -m scripts.discover_pages

sync:
	uv run python -m scripts.sync_wiki --sync-type incremental

build-corpus:
	uv run python -m scripts.build_corpus

sync-aliases:
	uv run python -m scripts.sync_aliases

embed-corpus:
	uv run python -m scripts.embed_corpus --corpus-version "$(CORPUS_VERSION)"

evaluate-retrieval:
	uv run python -m scripts.evaluate_retrieval

activate-corpus:
	uv run python -m scripts.activate_corpus --version "$(CORPUS_VERSION)"

rollback-corpus:
	uv run python -m scripts.rollback_corpus --version "$(CORPUS_VERSION)"

export-corpus:
	uv run python -m scripts.export_corpus --version "$(CORPUS_VERSION)"
