Read the complete `planning.md` file and then implement **Milestone 0 — Repository and Supabase Foundation**.

Only implement Milestone 0 in this task. Do not begin any later milestone.

## Scope

Complete the following work:

1. Inspect the current repository and report its existing structure.
2. Initialize the FastAPI backend.
3. Initialize the Next.js or React TypeScript frontend.
4. Create the repository structure defined in `planning.md`.
5. Create or update:

   * `README.md`
   * `IMPLEMENTATION_STATUS.md`
   * `.env.example`
   * `.gitignore`
   * `Makefile`
6. Configure basic formatting, linting, type checking, and testing.
7. Initialize the `supabase/` directory.
8. Create the `supabase/migrations/` directory.
9. Add the initial Supabase configuration files where appropriate.
10. Add the backend health endpoint:

    * `GET /api/health`
11. Add a minimal frontend page that calls the backend health endpoint and displays its status.
12. Add at least one backend unit test for the health endpoint.
13. Add frontend testing only if it can be done without unnecessary framework complexity.
14. Add a basic GitHub Actions workflow if this repository is hosted on GitHub.
15. Add safe environment-variable loading and validation.
16. Ensure that secrets and local environment files cannot be committed.

## Explicitly Out of Scope

Do not implement any of the following in this milestone:

* Knowledge database tables
* pgvector
* Full-Text Search
* Supabase Storage buckets
* Row Level Security policies
* MediaWiki crawling
* Wiki ingestion
* Document parsing
* Chunking
* Embeddings
* Hybrid retrieval
* Reranking
* LLM integration
* Chatbot functionality
* Corpus versioning
* Evaluation datasets

These belong to later milestones.

## Required Acceptance Criteria

Milestone 0 is complete only when:

* The backend starts successfully.
* The frontend starts successfully.
* `GET /api/health` returns a valid JSON response.
* The frontend can call and display the backend health status.
* Backend unit tests pass.
* Backend linting and formatting checks pass.
* Backend type checking passes, if configured.
* Frontend linting passes.
* Frontend type checking passes.
* The frontend production build passes.
* `.env` and credentials are excluded from Git.
* `.env.example` documents all currently required variables without containing real credentials.
* `README.md` contains clear local development instructions.
* `IMPLEMENTATION_STATUS.md` accurately reflects the completed work.
* The repository contains no Supabase secret key, service-role key, database password, or LLM API key.

## Required Working Process

Before modifying files:

1. Read the complete `planning.md`.
2. Inspect the repository.
3. Briefly report:

   * Current repository state
   * Milestone objective
   * Files expected to be created or modified
   * Dependencies to be installed
   * Technical risks and assumptions

Then proceed directly with implementation.

After implementation:

1. Run all relevant formatting, linting, type-checking, testing, and build commands.
2. Start or verify the backend health endpoint.
3. Verify the frontend build.
4. Update `IMPLEMENTATION_STATUS.md`.
5. Provide the completion report required by the master implementation prompt.

Do not claim successful verification unless the corresponding command was actually executed.

Do not continue to Milestone 1.
