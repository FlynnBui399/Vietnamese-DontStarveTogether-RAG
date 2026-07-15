# MVP Release Checklist

## Build and data

- [ ] `uv sync --frozen` and `npm ci` pass.
- [ ] Six Supabase migrations apply on a clean project.
- [ ] Incremental sync succeeds with bounded include/exclude audit data.
- [ ] Corpus processing and embeddings report complete success.
- [ ] Atomic activation creates a checksum-verified private snapshot.
- [ ] Exactly one corpus is active and rollback target is retained.

## Quality

- [ ] The 150-question dataset validates with the required category counts.
- [ ] Executable retrieval Recall@5 is at least 90% and Recall@10 at least 85%.
- [ ] DST scope accuracy is at least 98%; factual no-evidence answers remain 0%.
- [ ] Citation correctness is at least 95% on recorded answer observations.
- [ ] Faithfulness, numerical support, abstention, and subjectivity metrics are recorded honestly.
- [ ] Real Ollama latency/quality results are attached or explicitly marked unverified.

## Security and recovery

- [ ] Ruff, mypy, pytest, ESLint, TypeScript, and production build pass.
- [ ] Local database lint, RLS/grants access tests, and `scripts.security_review` pass.
- [ ] Gitleaks passes on the complete branch history.
- [ ] The open PostCSS advisory is cleared by a compatible stable Next.js upgrade or accepted by the
  deployment security owner with the mitigation in `SECURITY.md`.
- [ ] Prompt-injection, invalid-citation, provider-outage, and invalid-secret tests pass.
- [ ] Restore drill verifies SHA-256, imports into `validating`, and preserves retrieval/citations.
- [ ] Production TLS, exact CORS, shared rate limiting, secrets, backup/PITR, and monitoring are set.

## Product and legal

- [ ] Responsive chat, error states, citations, and source drawer receive a manual browser/a11y pass.
- [ ] Wiki attribution, license link, unofficial status, and known limitations are visible/reviewed.
- [ ] No unverified images/game assets are distributed.
- [ ] Deployment and incident owners approve `DEPLOYMENT.md`, `OPERATIONS.md`, and `SECURITY.md`.
