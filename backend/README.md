# CELTM Backend

Production-grade FastAPI backend for the CELTM skill intelligence platform.

## What This Backend Covers

- Supabase as the primary runtime database
- CELTMIND CSV ingestion into Supabase
- MCQ delivery and assessment scoring from Supabase only
- Transcript-first interview evaluation
- Hidden skill detection and approval flow
- Learning path and trajectory APIs
- Dashboard projection and report generation
- Redis + Celery for all non-trivial background processing
- Neo4j as a derived skill graph
- Supabase `pgvector` as the retrieval layer for RAG-backed learning and interview context

## Structure

```text
backend/
  app/
    api/
    config/
    core/
    dependencies/
    integrations/
    models/
    repositories/
    schemas/
    services/
    tasks/
    utils/
  docs/
  scripts/
  sql/
```

## Environment

Copy `backend/.env.example` to `backend/.env` and fill in:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_ANON_KEY`
- `SUPABASE_DB_CONNECTION_STRING`
- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`
- `OPENAI_API_KEY`
- `REDIS_URL`
- `REDIS_ENABLED`
- `CELTMIND_DIR`
- `CELTMIND_SYNC_ENABLED`

The backend also accepts legacy Supabase env names already used in some local setups:

- `SUPABASE_SECRET_KEY` as a fallback for `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_PUBLISHABLE_KEY` as a fallback for `SUPABASE_ANON_KEY`

Celery configuration is optional:

- `REDIS_URL` is enough for local use
- `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` only matter if you want Celery to use a different Redis instance
- Celery does not require a separate account, API key, or hosted credential
- for production hosting, you only need a reachable Redis service URL, usually `redis://...` or `rediss://...`
- `pip install -r requirements.txt` already installs `celery[redis]`
- set `CELTMIND_SYNC_ENABLED=false` in hosted environments that do not mount the `CELTMIND` folder
- local-only fallback is supported with `REDIS_ENABLED=false`, `REDIS_FAIL_OPEN=true`, and `CELERY_EAGER_MODE=true`

## Setup

```powershell
cd backend
python -m pip install -r requirements.txt
```

Apply the Supabase schema in `backend/sql/supabase_schema.sql` before using the API.

If you have a valid Postgres connection string in `SUPABASE_DB_CONNECTION_STRING`, you can apply and ingest in one step:

```powershell
cd backend
python scripts/bootstrap_supabase.py
```

## Run Locally

API:

```powershell
cd backend
uvicorn app.main:app --reload
```

Lower-overhead local API command on Windows:

```powershell
cd backend
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
```

Celery worker on Windows:

```powershell
cd backend
celery -A app.tasks.celery_app:celery_app worker -l info -P solo
```

Celery beat:

```powershell
cd backend
celery -A app.tasks.celery_app:celery_app beat -l info
```

Manual CELTMIND ingestion:

```powershell
cd backend
python scripts/ingest_mcq.py
```

Verification:

```powershell
cd backend
python scripts/check_celtmind_supabase.py
```

## Docker

Backend-only Docker support is included through:

- `backend/Dockerfile`
- `backend/docker-compose.yml`

This compose file starts:

- API
- Celery worker
- Celery beat
- Redis

Supabase and Neo4j remain external services.

## API Surface

Versioned API base: `/api/v1`

Main route groups:

- `/auth/*`
- `/profile/*`
- `/settings/*`
- `/mcq/*`
- `/assessments/*`
- `/skills/*`
- `/learning/*`
- `/trajectory/*`
- `/interview/*`
- `/sessions`
- `/schedule/*`
- `/reports/*`
- `/dashboard/*`
- `/admin/*`

Compatibility aliases for the current frontend mock contract are also exposed under `/api/*`.

## Async Workflow

The request path emits domain events into `domain_events`. Celery processes those events and fans out to:

- dashboard projection refresh
- report generation
- interview evaluation
- hidden skill candidate creation
- Neo4j graph sync
- CELTMIND sync

## Notes

- The current implementation is intentionally transcript-first for interviews.
- CELTMIND CSV files are ingestion-only. Runtime APIs never read from CSV.
- Hosted runtime can skip CELTMIND resync entirely with `CELTMIND_SYNC_ENABLED=false`.
- Pagination defaults to cursor-based list responses with `limit <= 100`.
- Supabase-heavy reads are pushed toward projection tables to avoid large joins.
