# CELTM Web Run Instructions

These instructions are written for Windows PowerShell and match the current
project structure in this repository.

## 1. Prerequisites

Install:

- Git
- Python 3.11 or newer
- Node.js 20 or newer
- npm
- Docker Desktop, only if you want Redis or backend services through Docker

External services required by the full product:

- Supabase project with Auth, Postgres, Storage, and pgvector enabled
- Redis for Celery in non-eager mode
- Neo4j for the derived skill graph
- OpenAI API key for RAG, copilot, written scoring, and AI evaluation

## 2. Backend Environment

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill `backend/.env`.

Core values:

```env
APP_ENV=development
APP_DEBUG=true
FRONTEND_ORIGIN=http://127.0.0.1:3000,http://localhost:3000
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_ANON_KEY=
SUPABASE_DB_CONNECTION_STRING=
OPENAI_API_KEY=
REDIS_URL=redis://localhost:6379/0
CELTMIND_DIR=../CELTMIND
```

Optional compatibility names accepted by the backend:

- `SUPABASE_SECRET_KEY` can stand in for `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_PUBLISHABLE_KEY` can stand in for `SUPABASE_ANON_KEY`
- `SUPABASE_KEY` can also be used as a legacy service-key fallback

Graph and admin values:

```env
NEO4J_URI=
NEO4J_USER=
NEO4J_PASSWORD=
ADMIN_OVERRIDE_TOKEN=
ADMIN_USER=admin@celtm.com
ADMIN_PASS=admin123
ADMIN_GATEWAY_CODE=CELTM2026
```

## 3. Supabase Setup

Apply the main schema in Supabase SQL editor or through your normal database
migration workflow:

```text
backend/sql/supabase_schema.sql
```

Use reset or repair SQL files only when you intentionally want to rebuild or fix
an existing database:

```text
backend/sql/reset_schema.sql
backend/sql/repair_schema.sql
backend/sql/patch_schema_v2.sql
backend/sql/fix_missing_tables.sql
```

If `SUPABASE_DB_CONNECTION_STRING` is configured, this script can apply schema
work and ingest local data:

```powershell
cd backend
python scripts/bootstrap_supabase.py
```

Make sure the storage buckets named by these env values exist:

```env
PROFILE_BUCKET=profile-assets
ARTIFACT_BUCKET=career-artifacts
```

## 4. CELTMIND Data Ingestion

The local CSV source folder is `CELTMIND/`. The default backend value
`CELTMIND_DIR=../CELTMIND` assumes commands are run from `backend/`.

Ingest MCQ/CELTMIND data:

```powershell
cd backend
python scripts/ingest_mcq.py
```

Verify the local CSV set against Supabase:

```powershell
cd backend
python scripts/check_celtmind_supabase.py
```

For hosted deployments that do not mount the CSV folder, set:

```env
CELTMIND_SYNC_ENABLED=false
```

## 5. Frontend Environment

Install dependencies:

```powershell
cd frontend
npm install
```

Create `frontend/.env.local` manually if you are not using `run-local.ps1`:

```env
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` is accepted as a fallback for
`NEXT_PUBLIC_SUPABASE_ANON_KEY`.

The current frontend is Next.js, not Vite. The old Vite `USE_MOCKS` switch is
not part of the current `frontend/src/lib/api.ts` path; the frontend calls the
backend selected by `NEXT_PUBLIC_API_BASE_URL`.

## 6. Recommended Local Startup

From the repository root:

```powershell
.\run-local.ps1
```

The script:

- stops stale local backend/frontend processes on ports 8000 and 3000
- reads `backend/.env`
- writes `frontend/.env.local` from backend Supabase values
- starts FastAPI at `http://127.0.0.1:8000`
- starts Next.js at `http://127.0.0.1:3000`
- uses eager/background fallback mode when Redis is local or not configured

Keep the two PowerShell windows open while developing.

## 7. Manual Local Startup

Start Redis if you want real Celery processing:

```powershell
cd backend
docker compose up redis -d
```

Start the API:

```powershell
cd backend
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
```

Start the Celery worker on Windows:

```powershell
cd backend
celery -A app.tasks.celery_app:celery_app worker -l info -P solo
```

Start Celery beat:

```powershell
cd backend
celery -A app.tasks.celery_app:celery_app beat -l info
```

Start the frontend:

```powershell
cd frontend
npm run dev
```

Open:

```text
http://127.0.0.1:3000
```

## 8. Docker Backend

Backend Docker support is under `backend/`.

```powershell
cd backend
docker compose up --build
```

This can start the API, Celery worker, Celery beat, and Redis. Supabase, Neo4j,
and external AI providers still need to exist separately.

## 9. Useful URLs

Backend:

- Health: `http://127.0.0.1:8000/health`
- Metrics: `http://127.0.0.1:8000/system/metrics`
- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

Frontend:

- App: `http://127.0.0.1:3000`
- Login: `http://127.0.0.1:3000/login`
- Dashboard: `http://127.0.0.1:3000/dashboard`
- Assessments: `http://127.0.0.1:3000/assessments`

## 10. Verification Checklist

Backend health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected response shape:

```json
{
  "status": "ok",
  "services": {
    "supabase": true,
    "redis": false,
    "neo4j": false,
    "worker": false
  },
  "timestamp": "..."
}
```

Service booleans depend on your local credentials and whether Redis/Neo4j are
running. The API can still respond with `status: ok` while optional services are
offline in development.

Backend tests:

```powershell
cd backend
python -m pytest app/tests
```

Frontend checks:

```powershell
cd frontend
npm run lint
npm run build
```

Browser checks:

- Login page opens first for unauthenticated users.
- Supabase login succeeds with a confirmed account.
- Dashboard loads without a backend unavailable message.
- Assessments hub opens and can start MCQ, situational, and written flows.
- Profile/settings updates persist after refresh.

## 11. Common Problems

### Frontend says Supabase is not configured

Check `frontend/.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

Restart `npm run dev` after changing env files.

### Frontend cannot reach backend

Check:

- backend is running at `http://127.0.0.1:8000`
- `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1`
- `FRONTEND_ORIGIN` includes `http://127.0.0.1:3000`

Prefer `127.0.0.1` for both backend and frontend during local checks.

### Supabase calls fail

Check:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_SECRET_KEY`
- schema from `backend/sql/supabase_schema.sql`
- storage buckets for profile and career artifacts
- `SUPABASE_DB_CONNECTION_STRING` if running bootstrap or direct SQL scripts

### Celery worker does not process jobs

Check:

- Redis is running and matches `REDIS_URL`
- worker is started with `-P solo` on Windows
- beat is started if scheduled jobs are required
- `CELERY_EAGER_MODE=false` for real Redis/Celery processing

For local development without Redis, use:

```env
REDIS_ENABLED=false
REDIS_FAIL_OPEN=true
CELERY_EAGER_MODE=true
```

### CELTMIND ingestion finds no files

Check:

- `CELTMIND/` exists at the repository root
- commands are run from `backend/`
- `CELTMIND_DIR=../CELTMIND`

### Enhanced RAG routes fail on startup

Enhanced RAG is registered from `backend/enhanced_rag_integration.py`. Run the
API from `backend/` so that file is importable, and install all backend
requirements before starting the server.

## 12. GitHub Safety

Do not commit:

- `.env` or `.env.*`
- generated output under `output/`
- local screenshots from Playwright/debug runs
- scratch scripts containing one-off credentials or machine-specific data

The root `.gitignore` is configured for these local files.
