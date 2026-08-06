# Job Discovery & Matching — Integration Steps (DB → pipeline)

## 1. Integrating db

backend/alembic/versions/0003_job_discovery_matching.py


## 2. Wire up dependencies (uv)

From `backend/`:

```powershell
uv add langgraph rank-bm25 crawl4ai numpy
uv add httpx
uv run crawl4ai-setup
```


## 3. Register the module's ORM models with Alembic
```python
import src.job_discovery_matching.internal.models  # NEW
```

## 4. Run the migration

```powershell
cd backend
uv run alembic current          # should show 0002_career_recommendation
uv run alembic upgrade head     # applies 0003 — 4 new tables, public.jobs untouched
```

## 5. Add SearXNG to your infra

- create a docker image using docker compose up --build
- add the `SEARXNG_URL = "http://localhost:8090"`. in .env


## 6. Mount the router

In `src/app.py`, next to where `career_recommendation`/`resume_parsing`
are already mounted:

```python
from src.job_discovery_matching import register_job_discovery
# ...
register_job_discovery(app)
```

# 7. steps to integrate the job discovery module
```powershell
# Same profile_id you already got from resume-parsing + kept from career-recommendation:
curl.exe -s -X POST http://127.0.0.1:8000/jobs/search `
  -H "Content-Type: application/json" `
  -d '{\"profile_id\": \"9ce31268-862e-48f7-ae24-0e951d35797f\"}'

# Poll / re-fetch the latest result:
curl.exe -s http://127.0.0.1:8000/jobs/runs/9ce31268-862e-48f7-ae24-0e951d35797f
```

# 8. Getting started

uv run uvicorn main:app --reload  ( Creates error with crawl4AI)
uv run uvicorn main:app (use this instead)


