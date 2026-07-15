.PHONY: install format format-check lint typecheck test check dev run \
	supabase-start supabase-stop supabase-migrate supabase-check

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
