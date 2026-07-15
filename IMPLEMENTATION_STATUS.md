# Implementation Status

## Current Milestone

Milestone 8 - Web Interface: **Complete**

Next: Milestone 9 - Incremental Sync and Corpus Activation.

## Milestone 8 Completed

- Replaced the foundation page with a responsive Vietnamese chat interface and suggested prompts.
- Added loading, empty-corpus, backend-error, abstention, and confidence states without leaving the
  composer or conversation in a hanging state.
- Added safe answer rendering through React text nodes, inline citation buttons, citation cards, and
  a source drawer showing exact evidence, section, revision, corpus, source kind, original link, and
  attribution.
- Added resolved-alias display, subjective-guide warnings, source-conflict warnings, response
  latency, corpus version, and public active-corpus status.
- Added keyboard Escape handling for the drawer, explicit labels, ARIA live/status regions, visible
  focus states, responsive layouts, and reduced-motion behavior.
- Added backend-only public read endpoints for corpus status, alias autocomplete, active-corpus
  entity detail, and active/archived source evidence.
- Added source membership validation so building/validating/failed corpus chunks cannot be exposed
  through `/api/sources/{chunk_id}`.
- Kept the browser configuration limited to `NEXT_PUBLIC_API_BASE_URL`; no Supabase URL, key, or
  internal table client is included in the frontend.

## Verification

Executed on 2026-07-15:

```text
uv run ruff format --check .                                 passed (87 files)
uv run ruff check .                                          passed
uv run mypy                                                  passed (87 source files)
uv run pytest -q                                             passed (42, 8 integration skipped)
npm run lint:web                                             passed
npm run typecheck:web                                        passed
npm run build:web                                            passed
npx supabase db lint --local --schema knowledge              passed
npx supabase migration list --local                          passed (5 migrations)
```

Focused UI/API acceptance covers public corpus status, exact/fuzzy alias autocomplete ordering,
entity deduplication, rejection of source evidence from a building corpus, and the public endpoint
contract. The local Next.js page returned HTTP 200, contained the application title, and the API
returned HTTP 200 for corpus status when launched with explicit local Supabase credentials.

## Unverified Criteria

- A visual/interactive in-app browser pass was attempted, but no in-app browser instance was
  available to the browser-control skill. Production build and localhost HTTP behavior passed; no
  screenshot or manual visual-pass claim is made.
- End-to-end successful chat rendering with real Ollama remains unverified because no corpus is left
  active. Milestone 9 owns validated production activation.
- Streaming remains disabled because the citation validator must inspect the complete answer before
  factual text is exposed.

## Known Issues and Deferred Work

- No corpus is left active after acceptance. Atomic activation, rollback, and snapshots begin in
  Milestone 9.
- The configured hosted project was not migrated or mutated; database verification used the local
  Supabase development stack.
- The PowerShell profile parse warning is environmental and did not change any command exit status.

## Completed Milestones

- Milestone 0 - Repository and Supabase Foundation (`7c99299`)
- Milestone 1 - Database, Extensions, and Storage (`10613e1`)
- Milestone 2 - Wiki Discovery and Raw Ingestion (`2f4ca03`)
- Milestone 3 - Processing, Classification, and Chunking (`5ed2f75`)
- Milestone 4 - Vietnamese Terminology and Alias Layer (`1b42ff1`)
- Milestone 5 - Embeddings and Search Indexes (`ece8130`)
- Milestone 6 - Hybrid Retrieval (`c6a0501`)
- Milestone 7 - Generation, Guardrails, and Citations (`6cc160b`)
- Milestone 8 - Web Interface
