# Implementation Status

## Current Milestone

Milestone 7 - Generation, Guardrails, and Citations: **Complete**

Next: Milestone 8 - Web Interface.

## Milestone 7 Completed

- Added a provider-independent LLM boundary and an Ollama `/api/chat` adapter with bounded
  temperature, timeout, non-streaming output, and response validation.
- Added a Vietnamese context-only system prompt that treats retrieved documents as untrusted data,
  rejects instructions inside sources, and forbids internal-knowledge or internet supplementation.
- Converted accepted context blocks into stable `S1`, `S2`, ... source objects carrying chunk,
  canonical URL, section, revision, corpus, source-kind, and subjectivity metadata.
- Added fail-closed citation validation for unknown IDs, non-active-corpus chunks, uncited factual
  claims, and numeric values absent from their cited evidence.
- Added deterministic abstention for no evidence, incomplete comparison evidence, and any invalid
  generated citation output.
- Added structured conflict detection for differing field values on the same page and subjectivity
  warnings for guide evidence.
- Added the typed `POST /api/chat` contract with resolved aliases, confidence, abstention reason,
  corpus version, citations, conflicts, subjectivity, and measured pipeline latencies.
- Added sanitized service-unavailable responses without exposing provider details, stack traces, or
  credentials.

## Verification

Executed on 2026-07-15:

```text
uv run ruff format --check .                                 passed (83 files)
uv run ruff check .                                          passed
uv run mypy                                                  passed (83 source files)
uv run pytest -q                                             passed (38, 8 integration skipped)
npm run lint:web                                             passed
npm run typecheck:web                                        passed
npm run build:web                                            passed
npx supabase db lint --local --schema knowledge              passed
npx supabase migration list --local                          passed (5 migrations)
```

Focused generation acceptance covers valid active-corpus citations, fake citation rejection,
uncited-output abstention, no-evidence abstention, incomplete-comparison abstention, structured
conflict detection, Ollama request shape, and the public structured chat response.

## Unverified Criteria

- Live answer quality and latency with Ollama remain unverified because no corpus is left active and
  Milestone 9 owns validated production activation. Unit acceptance uses deterministic evidence and
  mocked LLM output; it does not claim model quality.
- Evidence-to-claim validation is deterministic and conservative: it proves citation membership,
  active-corpus provenance, per-claim citation presence, and numerical support. General semantic
  entailment remains an evaluation concern for Milestone 10.
- Streaming is not enabled because the citation validator must inspect the complete answer before any
  factual text is exposed. The UI may add streaming only if it preserves that fail-closed boundary.

## Known Issues and Deferred Work

- The web application still shows the foundation status page; the chat, citation cards, and source
  drawer begin in Milestone 8.
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
- Milestone 7 - Generation, Guardrails, and Citations
