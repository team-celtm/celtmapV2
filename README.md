# CELTM Web

CELTM Web is a full-stack skill intelligence platform for assessment, learning-path
generation, interview practice, profile evidence, and RAG-backed coaching.

The repository contains a Next.js frontend and a FastAPI backend. Supabase is the
primary database and auth provider, Redis/Celery handles background work, Neo4j
stores the derived skill graph, and Supabase pgvector supports retrieval for RAG.

## Main Capabilities

- Supabase login, onboarding, profile, settings, avatars, and career artifacts.
- Dashboard summary, skill profile, gaps, hidden skills, role fit, and reports.
- MCQ, situational, placement, and written assessment flows.
- Written assessment grading with score, feedback, insights, loopholes, and
  recommendations.
- Learning path and trajectory generation from the user's role and skill gaps.
- Interview sessions, transcript/media submission, and result retrieval.
- RAG-backed copilot replies and enhanced search endpoints.
- Admin CSV ingestion and CELTMIND synchronization.

## Tech Stack

- Frontend: Next.js 16, React 19, TypeScript, Tailwind CSS, Supabase JS.
- Backend: Python 3.11+, FastAPI, Pydantic, Supabase client, Celery, Redis.
- Data services: Supabase Postgres, Supabase Storage, pgvector, Neo4j.
- AI services: OpenAI chat and embedding models, with optional Gemini/DeepSeek
  keys exposed in backend settings.

## Repository Map

```text
.
  backend/                 FastAPI API, services, repositories, Celery tasks
  backend/app/api/         Versioned API routers
  backend/app/services/    Business logic for assessments, RAG, reports, etc.
  backend/app/schemas/     Pydantic request and response models
  backend/sql/             Supabase schema and repair SQL
  backend/scripts/         Bootstrap, ingest, and verification scripts
  frontend/                Next.js app
  frontend/src/app/        App Router pages and dashboard routes
  frontend/src/lib/        API client, Supabase client, storage helpers
  CELTMIND/                CSV source files for roles, skills, and questions
  docs/API.md              Backend endpoint reference
  instructions.md          Windows PowerShell runbook
  run-local.ps1            Local stack starter for backend and frontend
```

## Quick Start

Use PowerShell from the repository root.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill `backend/.env` with Supabase, Redis, Neo4j, and AI credentials. At minimum,
the backend needs:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_SECRET_KEY`
- `SUPABASE_ANON_KEY` or `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_DB_CONNECTION_STRING` for schema/bootstrap scripts
- `OPENAI_API_KEY` for LLM/RAG-backed features
- `REDIS_URL` if Celery should run through Redis
- `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` for graph sync

Install the frontend dependencies:

```powershell
cd ..\frontend
npm install
```

Then start both apps from the repository root:

```powershell
.\run-local.ps1
```

The script starts:

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:3000`

It also writes `frontend/.env.local` from the Supabase values in `backend/.env`
and points `NEXT_PUBLIC_API_BASE_URL` at `http://127.0.0.1:8000/api/v1`.

## Manual Startup

Backend API:

```powershell
cd backend
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
```

Frontend:

```powershell
cd frontend
npm run dev
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

## Data Setup

Apply the Supabase schema before using the app:

- `backend/sql/supabase_schema.sql`
- repair or reset SQL files in `backend/sql/` only when intentionally rebuilding
  or repairing the database

If `SUPABASE_DB_CONNECTION_STRING` is valid, the bootstrap script can apply
schema work and ingest local CELTMIND data:

```powershell
cd backend
python scripts/bootstrap_supabase.py
```

Manual MCQ/CELTMIND ingestion:

```powershell
cd backend
python scripts/ingest_mcq.py
python scripts/check_celtmind_supabase.py
```

## API Documentation

FastAPI serves generated docs when the backend is running:

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

The curated endpoint reference is in [docs/API.md](docs/API.md).

## Verification

After startup, check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Then open `http://127.0.0.1:3000`, sign in, and verify dashboard, assessment,
profile, and settings pages can load without backend unavailable messages.

Useful backend checks:

```powershell
cd backend
python scripts/check_celtmind_supabase.py
python -m pytest app/tests
```

Useful frontend checks:

```powershell
cd frontend
npm run lint
npm run build
```

## Security Notes

Do not commit real credentials. The root `.gitignore` excludes `.env` and
`.env.*` files while allowing `.env.example`.

Keep generated browser screenshots, debug output, local caches, and scratch
scripts out of GitHub unless they are intentionally promoted into maintained
test assets.

## More Documentation

- [instructions.md](instructions.md): detailed Windows setup and runbook.
- [backend/README.md](backend/README.md): backend-specific architecture and
  runtime notes.
- [docs/API.md](docs/API.md): endpoint reference and request examples.
