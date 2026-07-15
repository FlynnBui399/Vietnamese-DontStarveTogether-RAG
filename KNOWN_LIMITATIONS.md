# Known Limitations

- The release dataset has 150 balanced questions, but only 20 are marked executable against the
  current 30-page acceptance corpus. Metrics never treat unexecuted questions as passes.
- Live answer/citation quality depends on the configured Ollama model and has not been established for
  every release question. Deterministic validation cannot prove general semantic entailment.
- The reranker is heuristic rather than a multilingual neural cross-encoder.
- Incremental releases regenerate all current chunks instead of reusing unchanged vectors. This is
  safer for the MVP but costs more processing.
- Streaming is disabled so invalid citations cannot be shown before validation completes.
- The built-in chat limiter is process-local. Multi-instance public deployment requires a shared
  gateway/Redis limiter and trusted proxy configuration.
- Conversation state is in the browser only and is not persisted.
- Corpus sync is operator/scheduler driven; no scheduler is bundled because hosting is undecided.
- The UI browser visual pass depends on an available in-app browser. Build and HTTP checks do not
  replace cross-browser/manual accessibility testing.
- Supabase managed backup/PITR availability and cost depend on the selected project plan.
- The production dependency audit has an open moderate PostCSS advisory inherited from stable
  Next.js 16.2.10; `SECURITY.md` records the affected/patched versions and current mitigation.
- Only wiki text is ingested. Images, videos, mods, save files, and non-DST game versions are out of
  scope.
