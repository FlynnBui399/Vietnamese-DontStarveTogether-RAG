# Security Review

## Enforced controls

- Knowledge tables use RLS and revoke `anon`/`authenticated` privileges.
- Hybrid search, activation, rollback, and diagnostics are backend-only RPCs.
- Raw, snapshot, and evaluation buckets are private.
- FastAPI is the only browser data boundary; frontend code has no Supabase client or credential.
- Retrieved wiki text is delimited as untrusted content and source instructions are ignored.
- Generated factual text is withheld until citation IDs, active-corpus membership, claim coverage,
  and numbers pass deterministic validation.
- Chat requests are length limited and rate limited per process. Production must add a shared gateway
  limiter for multiple API replicas.
- React renders model text without raw HTML. Source links are stored canonical URLs and open with
  `rel="noreferrer"`.
- FastAPI and Next.js emit anti-framing, content-type, referrer, permissions, and CSP headers.
- CI runs gitleaks plus lint, type, test, and build checks.

Run the repository audit with:

```bash
uv run python -m scripts.security_review
```

The script scans tracked and unignored credential patterns, forbidden frontend markers/raw HTML injection, RLS
coverage, privileged grants, and private Storage declarations. It supplements—not replaces—gitleaks,
Supabase access tests, dependency updates, host hardening, and secret rotation.

## Deployment checklist

- [ ] Secrets come from the deployment secret manager and are absent from build logs.
- [ ] `knowledge` is exposed only as needed by the backend credential.
- [ ] Anonymous table/Storage read and write tests fail.
- [ ] Admin/lifecycle RPC execution fails for `anon` and `authenticated`.
- [ ] CORS uses the exact production frontend origin.
- [ ] TLS, proxy body limits, shared rate limiting, and timeouts are enabled.
- [ ] Ollama and database ports are not public.
- [ ] Managed backups and one checksum-verified restore drill pass.
- [ ] Incident contacts and key-rotation access are assigned.

## Open dependency advisory

As of 2026-07-15, `npm audit --omit=dev` reports two moderate findings for
[GHSA-qx2v-qp2m-jg93](https://github.com/advisories/GHSA-qx2v-qp2m-jg93). Stable Next.js 16.2.10
pins PostCSS 8.4.31, while the advisory is patched in 8.5.10. npm's proposed force-fix would install
Next.js 9.3.3 and is not accepted. The current UI does not accept user-authored CSS and does not
inject raw model HTML, which limits the documented attack path but does not remove the dependency
finding. Recheck stable Next.js releases before deployment and upgrade when its dependency is
patched; do not use `npm audit fix --force` blindly.
