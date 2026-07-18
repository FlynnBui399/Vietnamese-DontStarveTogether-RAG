# DST RAG Field Guide frontend

Dependency-free ES-module frontend for the Vietnamese DST Wiki RAG service. The interface keeps the
project's dark survival field-guide style, but its primary flow is now a real RAG workspace:

```text
question -> /api/chat -> grounded answer + Wiki sources
```

The FastAPI app serves this directory at `/`, so run the complete application from the repository
root:

```powershell
uv run uvicorn apps.api.main:app --reload
```

Then open `http://127.0.0.1:8000`. API documentation remains available at
`http://127.0.0.1:8000/docs`.

Development checks:

```powershell
Set-Location apps/web
npm run check:syntax
npm run lint
npm run typecheck
```

The page uses remote open-source fonts when internet access is available and falls back to local
serif, fantasy, and sans-serif system fonts when it is not.
