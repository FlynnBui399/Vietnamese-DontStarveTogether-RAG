# Implementation Status

## Current Milestone

Milestone 10 - Evaluation, Security, Recovery, and Release: **Complete with recorded release
exceptions**

All implementation milestones in `prompt.md` are now represented in the repository. Production
deployment approval still depends on the explicitly unverified items below.

## Milestone 10 Completed

- Added a validated 150-question release dataset with the exact required category coverage and a
  separately marked 20-case executable subset for the current bounded acceptance corpus.
- Added Recall@1/5/10, MRR, duplicate-safe nDCG@10, entity-resolution, DST-scope, and p50/p95
  retrieval metrics. Reports state both total and executed case counts.
- Added explicit saved-answer evaluation for citation correctness/completeness, deterministic
  evidence traceability, relevance, numerical support, abstention precision/recall, and
  subjectivity labeling. Missing real observations are never counted as passes.
- Added private timestamped evaluation-report upload and local JSON output commands.
- Added checksum-verified gzip JSONL restore, dependency/page-ID reconstruction, embedding and
  provenance preservation, and a mandatory non-active `validating` restore state.
- Added a release orchestrator that stops on sync/build/embed failure and activates only as its last
  mutation.
- Added process-local chat rate limiting, API and Next.js security headers/CSP, tracked-secret and
  frontend-boundary scanning, RLS/grants/private-bucket review, lifecycle-RPC access tests, and
  retrieved prompt-injection tests.
- Made the synthetic seed page inactive by default so it cannot invalidate real current-revision
  coverage; lifecycle tests opt it in explicitly.
- Added deployment, operations/recovery, security, attribution/license, known-limitations, and
  release-checklist documents.

## Release Benchmark

Executed on 2026-07-15 against local Supabase, a live 30-page bounded wiki sync, 100 validated
chunks, and the explicit deterministic 1024-dimensional test adapter:

```text
dataset questions                  150
benchmark-ready questions           20
Recall@1 / Recall@5 / Recall@10     1.0000 / 1.0000 / 1.0000
MRR / nDCG@10                       1.0000 / 0.9807
entity resolution accuracy          1.0000
DST scope accuracy                  1.0000
retrieval p50 / p95                 14.832 ms / 19.035 ms
```

The report is versioned at `data/evaluation/reports/release_local.json` and was also uploaded to the
local private evaluation bucket. These numbers validate retrieval plumbing and the bounded corpus;
they do not claim production semantic quality for Ollama `bge-m3` or the configured generation
model.

## Verification

Executed on 2026-07-15:

```text
uv run ruff format --check .                                 passed (109 files)
uv run ruff check .                                          passed
uv run mypy                                                  passed (109 source files)
uv run pytest -q                                             passed (57, 10 opt-in skipped)
npm run lint:web                                             passed
npm run typecheck:web                                        passed
npm run build:web                                            passed
uv lock --check                                              passed
npm ci --ignore-scripts --dry-run                            passed
npx supabase db reset                                        passed (6 migrations)
npx supabase db lint --local --schema knowledge              passed
npx supabase migration list --local                          passed (6 migrations)
live access/lifecycle/snapshot/restore tests                  passed (5 tests)
uv run python -m scripts.security_review                     passed (5 checks)
git diff --check                                             passed
```

The live recovery test verified anonymous denials, backend CRUD, private Storage, protected
lifecycle RPCs, atomic activation/archive/rollback, snapshot checksum, zero-alias restore, preserved
source URL/revision/content, restored semantic retrieval, and cleanup. The bounded release run
verified activation readiness and exported a 30-page/100-chunk snapshot.

## Unverified or Open Release Criteria

- Real Ollama answer/citation/faithfulness observations have not been recorded. The evaluator and
  command exist, but fixture metrics are not presented as release evidence.
- Hosted Supabase migration, activation, recovery, managed backup/PITR, and deployment were not
  performed; all mutations used the local development stack.
- A manual cross-browser/accessibility pass could not run because no in-app browser instance was
  available. TypeScript, production build, and localhost HTTP checks passed in Milestone 8.
- Gitleaks is not installed in this environment. The built-in tracked-secret scan passed, but the
  release checklist keeps full-history Gitleaks verification open.
- `npm audit --omit=dev` reports two moderate findings for the PostCSS advisory documented in
  `SECURITY.md`. Stable Next.js 16.2.10 pins the affected PostCSS version, and npm's proposed fix is
  an unacceptable downgrade to Next.js 9.3.3.
- Production TLS/proxy limits, shared multi-replica rate limiting, monitoring, incident ownership,
  cost/quota selection, and scheduled sync require deployment-environment decisions.

## Environment Note

The recurring PowerShell profile `Unexpected token '}'` warning is outside this repository and did
not change command exit status. GNU Make is unavailable on this Windows host, so underlying CLI
commands were executed directly; the Makefile command surface was inspected but not invoked.

## Completed Milestones

- Milestone 0 - Repository and Supabase Foundation (`7c99299`)
- Milestone 1 - Database, Extensions, and Storage (`10613e1`)
- Milestone 2 - Wiki Discovery and Raw Ingestion (`2f4ca03`)
- Milestone 3 - Processing, Classification, and Chunking (`5ed2f75`)
- Milestone 4 - Vietnamese Terminology and Alias Layer (`1b42ff1`)
- Milestone 5 - Embeddings and Search Indexes (`ece8130`)
- Milestone 6 - Hybrid Retrieval (`c6a0501`)
- Milestone 7 - Generation, Guardrails, and Citations (`6cc160b`)
- Milestone 8 - Web Interface (`baba297`)
- Milestone 9 - Incremental Sync and Corpus Activation (`e6acca6`)
- Milestone 10 - Evaluation, Security, Recovery, and Release
