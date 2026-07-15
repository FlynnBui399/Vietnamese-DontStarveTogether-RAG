# Operations and Recovery

## Install and local services

```bash
make install
make supabase-start
make supabase-migrate
make supabase-check
```

`supabase-migrate` resets the local development database. Use `npx supabase db push` for an existing
hosted project after reviewing the migration plan.

## Corpus release

```bash
make sync
uv run python -m scripts.build_corpus --version 2026-07-15.1
uv run python -m scripts.embed_corpus --corpus-version 2026-07-15.1
make activate-corpus CORPUS_VERSION=2026-07-15.1
make evaluate
```

Or run the first four stages as one command:

```bash
make release-corpus CORPUS_VERSION=2026-07-15.1
```

After activation, record retrieval metrics and any saved answer observations:

```bash
uv run python -m scripts.evaluate_release --output data/evaluation/reports/release.json --upload
uv run python -m scripts.evaluate_answers \
  --observations data/evaluation/answer_observations.json \
  --output data/evaluation/reports/answers.json --upload
```

The answer command scores only provided observations. If real Ollama responses have not been
recorded, mark answer quality unverified rather than substituting deterministic fixture results.

Never patch chunks in an active corpus. Failed build/embedding versions remain non-active. Inspect
`knowledge.sync_runs.details`, `corpus_versions.manifest`, and CLI JSON before retrying.

## Snapshot and rollback

```bash
make export-corpus CORPUS_VERSION=2026-07-15.1
make rollback-corpus CORPUS_VERSION=2026-07-01.1
```

Rollback accepts only an internally complete archived corpus with embeddings. It switches versions
in a database transaction and does not depend on current MediaWiki revision flags.

## Restore drill

Restore into a clean, isolated project after applying every migration:

```bash
make restore-corpus SOURCE_VERSION=2026-07-15.1 TARGET_VERSION=restore-drill-2026-07-15
uv run python -m scripts.evaluate_release
make activate-corpus CORPUS_VERSION=restore-drill-2026-07-15
```

The restore downloads private objects in memory, checks SHA-256 and record counts before writes,
recreates model/page/attribution/alias/chunk dependencies, remaps page IDs, preserves embeddings and
citations, and leaves the version `validating`. Do not activate until retrieval and citation checks
pass. Delete the drill version and objects after recording the result.

## Incident runbooks

### Supabase unavailable or paused

Keep the UI in its degraded state, restore service/quota, verify `/api/health` and
`/api/corpus/status`, then run retrieval evaluation. Do not fall back to a local JSON/FAISS store.

### Partial embeddings or vector corruption

Do not activate. Rerun `scripts.embed_corpus` for missing vectors. For suspected corruption, build a
new corpus/model version or restore a known snapshot; never overwrite active vectors in place.

### Bad activation

Run the release benchmark, then `make rollback-corpus` to the last accepted archived version. Keep the
failed replacement archived for audit until the incident is understood.

### Missing Storage object

Raw snapshots can be fetched again only under the bounded MediaWiki policy. Corpus snapshots should
also exist in managed backups. Verify checksums; do not restore an object whose manifest differs.

### Secret exposure

Revoke/rotate the Supabase and provider key immediately, update the secret manager and backend,
invalidate affected deployments, inspect logs without copying secrets, and rerun the security review.
No key rotation is complete until the old key fails.

### Failed migration

Stop release automation. Preserve the current active corpus, inspect the migration error and local
reproduction, and apply a forward corrective migration. Do not rewrite an already-applied migration.
