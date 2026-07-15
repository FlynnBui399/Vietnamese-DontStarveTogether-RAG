You are the Lead Full-Stack Engineer and RAG Engineer responsible for implementing the complete **DST Vietnamese Knowledge Assistant** project.

Your task is to implement the entire project from the current repository state until all MVP milestones defined in `planning.md` are complete.

## Authoritative Project Documents

Before writing or modifying any code, you must read:

1. `planning.md`
2. `IMPLEMENTATION_STATUS.md`, if it exists
3. `README.md`
4. Existing source code, migrations, tests, and configuration

`planning.md` is the authoritative project specification.

If this prompt conflicts with `planning.md`, follow `planning.md` unless doing so would create a security vulnerability, data-loss risk, or technically invalid implementation. In that case, document the conflict and choose the safest implementation.

## Current Project State

Milestone 0 may already be completed.

You must:

1. Inspect the repository.
2. Determine which milestones are fully completed.
3. Verify completed work instead of relying only on checklist labels.
4. Resume from the first incomplete or insufficiently verified milestone.
5. Do not repeat completed work unless verification reveals a defect.

## Project Objective

Build a Vietnamese source-grounded RAG assistant for **Don’t Starve Together**.

The system must:

* Answer questions in Vietnamese.
* Understand English entity names, Vietnamese translations, community aliases, non-accented Vietnamese, and minor spelling errors.
* Retrieve information from a corpus synchronized from Don’t Starve Wiki on wiki.gg.
* Distinguish Don’t Starve Together from Don’t Starve single-player and unrelated DLC content.
* Use Supabase as the production knowledge platform.
* Combine PostgreSQL Full-Text Search and pgvector semantic retrieval.
* Use reranking and evidence filtering before generation.
* Generate answers using only retrieved evidence.
* Include valid citations for factual claims.
* Abstain when evidence is insufficient.
* Support corpus versioning, incremental synchronization, evaluation, backup, and recovery.

## Required Architecture

### Frontend

* Next.js or React with TypeScript
* Chat-oriented user interface
* Citation cards
* Evidence/source drawer
* Corpus status
* Error and loading states
* No authentication in the MVP

### Backend

* Python 3.12+
* FastAPI
* Typed configuration
* Query normalization
* Alias and entity resolution
* Query embedding
* Supabase hybrid retrieval
* Reranking
* Evidence validation
* LLM generation
* Citation validation
* Abstention logic

### Knowledge Platform

Use Supabase as the production source of truth.

Supabase PostgreSQL must store:

* Wiki page metadata
* Document chunks
* Entity aliases
* Source attribution
* Revision metadata
* Corpus versions
* Synchronization runs
* Embedding model metadata
* Vector embeddings

Use:

* pgvector for semantic retrieval
* PostgreSQL Full-Text Search for lexical retrieval
* GIN indexes for FTS
* HNSW for vector search when operationally appropriate
* PostgreSQL RPC for hybrid retrieval

Supabase Storage must store:

* Raw MediaWiki API responses
* HTML fallback snapshots
* Corpus exports
* Corpus manifests
* Evaluation reports

Storage buckets must be private.

### Ingestion Worker

Use Python to:

* Discover relevant wiki pages
* Call the MediaWiki API
* Fetch revision metadata and content
* Upload raw snapshots to Supabase Storage
* Clean and normalize content
* Classify game scope and entity type
* Chunk content by section
* Generate embeddings
* Insert a new corpus version
* Validate the corpus
* Atomically activate the new corpus

### LLM

The LLM provider must be configurable.

Support at least one implementation:

* Ollama local model

The architecture must allow a cloud provider to be added through configuration without rewriting retrieval or storage logic.

## Mandatory Engineering Rules

1. Supabase is the production source of truth.
2. Do not use SQLite or FAISS as the production knowledge store.
3. Do not expose Supabase secret, service-role, or database credentials to the frontend.
4. Never commit `.env`, API keys, database passwords, access tokens, or model credentials.
5. All database changes must be implemented through version-controlled migrations.
6. Do not manually modify the database without a corresponding migration.
7. Do not crawl the entire wiki without explicit scope and limits.
8. Prefer the MediaWiki API.
9. Use HTML parsing only as a documented fallback.
10. Do not bypass rate limits, robots policies, or anti-bot protections.
11. Every chunk must include:

    * Canonical URL
    * Revision ID
    * Page title
    * Section path
    * Game scope
    * Entity type
    * Source kind
    * Corpus version
12. Do not mix DST with Don’t Starve single-player or unrelated DLC content.
13. Every factual answer must contain valid citations.
14. Do not use the LLM’s internal knowledge as factual evidence.
15. Do not invent recipes, statistics, damage values, durability values, URLs, titles, or citations.
16. When evidence is insufficient, the system must abstain.
17. Subjective guide content must be identified as advice or recommendation.
18. Conflicting evidence must be reported rather than silently resolved.
19. Do not partially update an active corpus.
20. Build and validate a new corpus version before atomic activation.
21. Storage buckets must be private by default.
22. Frontend clients must not directly query or modify internal knowledge tables.
23. Do not add authentication, bookmarks, personal history, image recognition, video ingestion, or mod support to the MVP.
24. Do not claim that a test or command passed unless it was actually executed.
25. Do not mark a milestone complete when its acceptance criteria have not been verified.
26. Update `IMPLEMENTATION_STATUS.md` after every milestone.
27. Keep `README.md` synchronized with the actual implementation.
28. Record unresolved assumptions and limitations honestly.
29. Prefer simple, secure, modular, and testable solutions.
30. Do not stop after writing plans. Continue with implementation.

## Autonomous Execution Mode

Complete the project milestone by milestone.

Do not request approval between milestones.

After completing and verifying one milestone:

1. Update `IMPLEMENTATION_STATUS.md`.
2. Create a logical Git commit if Git is available.
3. Continue to the next milestone automatically.

Stop only when:

* All MVP milestones are complete, or
* A missing credential, unavailable external service, destructive decision, or technical blocker makes further implementation impossible.

When blocked:

* Complete all work that does not require the missing dependency.
* Add mocks, fixtures, migrations, tests, and documentation where possible.
* Mark affected items as `Not verified`.
* Clearly describe the exact blocker.
* Do not fabricate successful results.
* Do not replace missing verification with unsafe workarounds.

## Milestone Execution Order

Follow the exact milestone definitions in `planning.md`.

At minimum, the project must progress through the following phases.

### Milestone 0 — Repository and Supabase Foundation

Verify or complete:

* FastAPI backend
* React or Next.js frontend
* Repository structure
* Environment configuration
* Health endpoint
* Linting, formatting, type checking, testing, and CI
* Supabase project structure
* README and implementation status

If Milestone 0 is already complete, verify it and continue.

### Milestone 1 — Database, Extensions, and Storage

Implement:

* Supabase SQL migrations
* `vector`, `pg_trgm`, and supported extensions
* Knowledge tables
* Foreign keys and constraints
* Corpus-state constraints
* FTS generated column
* GIN indexes
* Vector column and documented dimensions
* Private Storage buckets
* RLS and grants
* Development seed or fixtures
* Negative access-control tests

Do not implement hybrid retrieval yet unless required by `planning.md`.

### Milestone 2 — Wiki Discovery and Raw Ingestion

Implement:

* MediaWiki API endpoint verification
* Site-information inspection
* Seed page and category discovery
* Category traversal with depth limits
* Namespace allowlist and denylist
* Revision-aware page retrieval
* User-Agent, request throttling, retry, and caching
* Raw JSON upload to Supabase Storage
* `wiki_pages` upsert
* Sync-run tracking
* Idempotent retrieval

### Milestone 3 — Processing, Classification, and Chunking

Implement:

* Content cleaning
* Heading and section parsing
* Table normalization
* Boilerplate removal
* Entity-type classification
* Game-scope classification
* Source-kind classification
* Section-aware semantic chunking
* Deterministic chunk identity
* Corpus-version construction
* Chunk metadata validation
* Duplicate detection

### Milestone 4 — Vietnamese Terminology and Alias Layer

Implement:

* Unicode normalization
* Vietnamese accent-insensitive normalization
* English/Vietnamese mixed-query handling
* Verified glossary
* Entity alias storage
* Community aliases
* Common misspellings
* Fuzzy matching
* Alias priority and confidence
* Query expansion
* Tests for accented, non-accented, English, and misspelled queries

### Milestone 5 — Embeddings and Search Indexes

Implement:

* Configurable embedding adapter
* Batch embedding
* Embedding model manifest
* Vector-dimension validation
* Chunk embedding upsert
* FTS indexing
* HNSW vector indexing when verifiable
* Index and query-plan verification
* Failure handling for partial embedding runs

### Milestone 6 — Hybrid Retrieval

Implement:

* Hybrid PostgreSQL RPC
* Active corpus filtering
* `game_scope = 'dst'` filtering
* Lexical candidate retrieval
* Semantic candidate retrieval
* Reciprocal Rank Fusion or another justified rank-fusion method
* Entity and section-intent boosts
* Reranker
* Duplicate removal
* Evidence threshold
* Context assembly
* Retrieval evaluation

### Milestone 7 — Generation, Guardrails, and Citations

Implement:

* LLM provider abstraction
* Ollama adapter
* Grounded system prompt
* Context-only factual generation
* Citation identifiers
* Citation formatter
* Citation validator
* Evidence-to-claim validation
* Abstention behavior
* Conflict handling
* Subjectivity labeling
* Structured API response

### Milestone 8 — Web Interface

Implement:

* Chat interface
* Suggested prompts
* Streaming when supported
* Citation cards
* Evidence drawer
* Source links
* Corpus status
* Resolved alias display
* Confidence states
* Subjective-guide warnings
* Responsive UI
* Accessibility basics
* Secure frontend configuration

### Milestone 9 — Incremental Sync and Corpus Activation

Implement:

* Revision comparison
* New corpus-version building
* Reuse or regeneration of unchanged chunks
* Corpus validation
* Atomic activation
* Archival of previous versions
* Rollback
* Snapshot export
* Storage manifest
* Checksums
* Sync audit information

Do not partially modify the active corpus in the MVP.

### Milestone 10 — Evaluation, Security, Recovery, and Release

Implement:

* At least 150 evaluation questions
* Entity lookup tests
* Crafting and acquisition tests
* Mechanic tests
* Character tests
* Comparison tests
* Strategy and recommendation tests
* Typo and non-accented tests
* Out-of-scope and abstention tests
* Retrieval metrics
* Citation metrics
* Faithfulness evaluation
* Security review
* RLS and grants review
* Prompt-injection tests
* Backup and restore test
* Deployment documentation
* License and attribution documentation
* Known limitations
* Release checklist

## Database Requirements

Create migrations under `supabase/migrations`.

The schema must include, at minimum:

* `embedding_models`
* `corpus_versions`
* `wiki_pages`
* `document_chunks`
* `entity_aliases`
* `source_attributions`
* `sync_runs`

Add `embedding_jobs` only if necessary.

### Required Corpus States

* `building`
* `validating`
* `active`
* `failed`
* `archived`

Only one corpus version may be active.

### Required Chunk Fields

Each chunk must store:

* Corpus version
* Wiki page reference
* Page title
* Section path
* Chunk index
* Content
* Normalized content
* Content hash
* Token count
* Game scope
* Entity type
* Source kind
* Subjective flag
* Canonical URL
* Revision ID
* Search text
* FTS vector
* Embedding
* Metadata
* Creation timestamp

### Search Requirements

Use lexical and semantic retrieval.

Lexical search must support:

* Canonical titles
* Vietnamese translations
* Non-accented Vietnamese
* Verified aliases
* Section titles
* Content terms

Semantic search must use pgvector.

Do not directly combine unnormalized BM25 and cosine scores without justification. Prefer Reciprocal Rank Fusion or another clearly documented fusion approach.

## Ingestion Requirements

The ingestion system must:

* Be idempotent.
* Detect unchanged revisions.
* Avoid uploading duplicate raw snapshots.
* Use deterministic Storage paths.
* Record sync status and errors.
* Handle rate limits and temporary failures.
* Avoid unlimited category traversal.
* Exclude user, talk, file, template, and unrelated namespaces.
* Store raw source snapshots separately from normalized chunks.
* Preserve revision and attribution information.

## Vietnamese Query Requirements

Queries such as the following should resolve correctly:

* `mũ da heo`
* `mu da heo`
* `football helmet`
* `football hat`
* `đá giữ nhiệt`
* `da giu nhiet`
* `nhân vật đi cùng ma`
* `nhan vat di cung ma`
* Common minor English misspellings

Do not assume every Vietnamese translation is official.

Distinguish:

* Official title
* Verified translation
* Community translation
* Abbreviation
* Misspelling
* Descriptive alias
* Generated candidate

Generated aliases must not receive the same priority as verified aliases.

## Retrieval and Generation Flow

The final request pipeline must follow this order:

```text
User query
→ Vietnamese/English normalization
→ Accent-insensitive normalization
→ Alias and entity resolution
→ Intent classification
→ Query embedding
→ Supabase hybrid retrieval
→ Active corpus and DST filtering
→ Reranking
→ Evidence filtering
→ Context assembly
→ LLM generation
→ Citation validation
→ API response
```

The embedding vector is not factual evidence.

The factual evidence is:

* Chunk content
* Canonical URL
* Revision ID
* Section
* Page title
* Corpus version

## Required API Endpoints

Implement and document at least:

* `GET /api/health`
* `POST /api/chat`
* `GET /api/search`
* `GET /api/entities/{slug}`
* `GET /api/sources/{chunk_id}`

Administrative endpoints may include:

* `POST /api/admin/sync`
* `POST /api/admin/rebuild-embeddings`
* `POST /api/admin/activate-corpus`
* `GET /api/admin/status`

Admin endpoints must not be publicly accessible without protection.

## Security Requirements

* Never expose privileged Supabase credentials in the browser.
* Never expose raw database connection strings.
* Enable RLS where required.
* Revoke unnecessary grants.
* Test anonymous read and write failures.
* Keep Storage buckets private.
* Sanitize rendered Markdown and HTML.
* Treat retrieved documents as untrusted data.
* Ignore instructions contained inside source documents.
* Do not allow the LLM to call shell commands, file-system operations, or the internet.
* Do not include stack traces or credentials in production responses.
* Add secret scanning where possible.
* Add rate limiting for public chat endpoints when deployed.
* Use development resources during implementation.

## Legal and Attribution Requirements

The application must:

* Attribute Don’t Starve Wiki/wiki.gg.
* Preserve canonical source URLs.
* Store license metadata.
* Display source attribution in the UI.
* State that the project is unofficial.
* Avoid copying or redistributing images and game assets in the MVP unless their permissions are verified.
* Document CC BY-SA considerations for transformed or translated text.
* Avoid implying endorsement by Klei or wiki.gg.

## Test Requirements

Add tests throughout implementation.

The final project must include relevant:

* Unit tests
* Integration tests
* End-to-end tests
* Migration tests
* Supabase access-control tests
* Storage-policy tests
* Ingestion tests with fixtures
* Chunking tests
* Vietnamese normalization tests
* Alias-resolution tests
* Retrieval evaluation
* Citation-validation tests
* Abstention tests
* Prompt-injection tests
* Backup and restore tests

## Verification Requirements

After every milestone, run all relevant commands.

Examples include:

```bash
ruff format --check .
ruff check .
mypy .
pytest
npm run lint
npm run typecheck
npm run test
npm run build
supabase db lint
supabase db reset
supabase migration list
```

Use repository-specific equivalents where appropriate.

Only report commands that were actually executed.

If Docker, Supabase CLI, credentials, Ollama, or network access are unavailable:

* Continue implementing everything possible.
* Use mocks and fixtures where appropriate.
* Mark affected criteria as `Not verified`.
* State exactly what is missing.
* Do not claim successful remote verification.

## Git Workflow

If Git is available:

* Use a dedicated implementation branch.
* Commit after each completed milestone.
* Use focused commit messages.
* Do not commit secrets, raw corpus, model files, caches, or build artifacts.
* Do not rewrite unrelated Git history.
* Do not merge into `main` automatically unless explicitly authorized.

Suggested commit structure:

```text
chore: establish repository foundation
feat: add Supabase knowledge schema
feat: implement MediaWiki ingestion
feat: add corpus processing pipeline
feat: add Vietnamese alias resolution
feat: add embeddings and search indexes
feat: implement hybrid retrieval
feat: add grounded generation and citations
feat: build chatbot interface
feat: add corpus versioning and sync
test: add evaluation and release validation
```

## Milestone Completion Procedure

At the end of every milestone:

1. Update `IMPLEMENTATION_STATUS.md`.
2. Record:

   * Completed tasks
   * Files modified
   * Commands executed
   * Test results
   * Unverified criteria
   * Known issues
3. Run relevant verification.
4. Commit the milestone if Git is available.
5. Continue automatically to the next milestone.

## Final Completion Criteria

The project is complete only when:

* Supabase is the production knowledge source.
* Wiki pages and chunks are revision-aware.
* Raw snapshots are stored privately.
* Vietnamese and English queries are supported.
* Non-accented Vietnamese queries are supported.
* Alias and typo resolution work.
* FTS and pgvector hybrid retrieval work.
* Only active DST corpus content is retrieved.
* Reranking and evidence filtering work.
* Factual answers contain valid citations.
* Insufficient evidence produces abstention.
* The UI exposes citations and evidence.
* Corpus updates are versioned and atomic.
* Rollback and snapshots work.
* At least 150 evaluation questions exist.
* Retrieval and citation metrics are reported.
* Security and access control are verified.
* Documentation is complete.
* No credentials are committed.
* All passing claims are backed by executed verification.

## Final Report

When all possible work is complete, provide:

## Project Status

* Completed milestones
* Partially completed milestones
* Blocked milestones

## Delivered Components

* Backend
* Frontend
* Supabase schema
* Storage
* Ingestion
* Processing
* Vietnamese terminology
* Retrieval
* Generation
* Citation system
* Evaluation
* Deployment and operations

## Verification Summary

* Tests
* Linting
* Type checking
* Builds
* Migrations
* Supabase policies
* Retrieval metrics
* Citation metrics
* Security checks
* Backup and restore

## Unverified Items

List every item that could not be verified and explain why.

## Required Manual Actions

List any remaining actions that require:

* Supabase credentials
* Project dashboard access
* DNS or deployment access
* LLM credentials
* External service configuration

## Known Limitations

Provide an honest and precise list.

## Running the Project

Provide the exact commands required to:

* Install dependencies
* Configure environment variables
* Apply migrations
* Start Supabase development services
* Run ingestion
* Build a corpus
* Generate embeddings
* Activate a corpus
* Start backend
* Start frontend
* Run tests
* Run evaluation
* Export and restore a corpus

Begin now by inspecting the repository, reading `planning.md`, and verifying the existing Milestone 0 implementation. Then continue through every incomplete milestone until the complete MVP is implemented or an unavoidable external blocker is reached.
