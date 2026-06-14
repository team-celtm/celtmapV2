# CELTM Web Master

CELTM Web Master is a Phase 1 skill-readiness web app for students,
institutions, and CELTM administrators. It combines Supabase student auth,
institution/admin management, resume and credential evidence, assessments,
career-aim planning, readiness reporting, and optional OpenAI-assisted analysis.

This checkout is not the old RAG/Celery/Neo4j runtime. Redis is used only for
hosted shared rate limiting. The current app is a lighter hosted-first stack:

- Frontend: Next.js App Router, React, TypeScript, Tailwind CSS, Supabase JS.
- Backend: FastAPI, Pydantic, SQLite for local dev, optional Postgres/Supabase
  Postgres for hosted mode.
- Auth: Supabase access tokens for students; backend-issued JWTs for institution
  admins and super admin.
- Assessments: server-side deterministic scoring, live question bank reads from
  Supabase tables, scheduled institution assignments.
- AI: OpenAI-backed resume, certificate, written-response, career-aim, and chat
  analysis when `OPENAI_API_KEY` is configured. Heuristic AI fallbacks are off by
  default.
- Files: local uploads under `backend/data/uploads` in development; hosted mode
  requires private Supabase Storage with short-lived signed URLs.

## Current Product Surface

Student-facing functions:

- Supabase sign up and login.
- Onboarding with institution and department selection.
- Dashboard readiness summary, resume prompt, exam analytics, subject progress,
  career and skill signals.
- Resume upload and analysis.
- Credential/profile evidence uploads and link validation.
- MCQ, situational, mixed, and written assessment flows.
- Assigned tests from institution heads.
- Career Aim recommendations and aspiration tracking.
- Skill profile, gaps, hidden skill candidates, learning path, sessions,
  competency map, settings, and chat assistant.

Admin and institution functions:

- Institution/super-admin login.
- Super-admin creation of institutions, departments, and head accounts.
- Question CSV ingestion into the Supabase question bank.
- Question set and scheduled assessment assignment management.
- Student search, readiness cards, detail views, CSV/PDF exports, and student
  passport downloads.

## Repository Map

```text
.
  backend/                 FastAPI app, database layer, security, AI helpers
  backend/app/main.py      Current route surface and application composition
  backend/app/database.py  SQLite/Postgres-compatible schema and access layer
  backend/app/settings.py  Environment configuration and hosted-mode guards
  backend/app/security.py  Supabase token validation and admin JWT helpers
  backend/app/supabase_bank.py  Supabase question bank integration
  backend/data/            Local ignored SQLite/upload runtime data
  docs/API.md              Current API endpoint reference
  docs/HOSTING_SECURITY_REVIEW.md  Hosting, security, and scalability analysis
  docs/testing-benchmark.md  Manual and automated release benchmark
  frontend/                Next.js app
  frontend/src/app/        App Router pages
  frontend/src/lib/        API, Supabase, storage, and dashboard helpers
  instructions.md          Local and hosted runbook
  HOW_TO_RUN.md            Short local startup guide
  run-local.ps1            One-command local backend/frontend starter
```

## Quick Start

Use PowerShell from the repository root.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env`. For local development, keep the default local admin values
only if the app is not exposed publicly.

```powershell
cd ..\frontend
npm install
cd ..
.\run-local.ps1
```

The script starts:

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:3000`

It also writes `frontend/.env.local` from `backend/.env` when Supabase values are
available.

## Required Environment

Backend variables are documented in [backend/.env.example](backend/.env.example).
For hosted mode, set at least:

- `APP_ENV=production`
- `FRONTEND_ORIGIN=https://your-frontend-domain`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY` or `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `DATABASE_URL` or `SUPABASE_DATABASE_URL`
- `CELTM_JWT_SECRET`
- `ADMIN_USER`
- `ADMIN_PASS`
- `ADMIN_GATEWAY_CODE`
- `OPENAI_API_KEY` if AI-backed analysis should work
- `STORAGE_BACKEND=supabase`
- `SUPABASE_STORAGE_BUCKET`
- `ALLOW_LOCAL_FILE_SERVING=false`
- `RATE_LIMIT_BACKEND=memory` for a single free Render instance, or `redis` with
  `REDIS_URL` when using shared Redis/Upstash or multiple backend instances
- `MONITORING_TOKEN`
- `ADMIN_MFA_REQUIRED=true` and `ADMIN_MFA_SECRET` for hosted admin MFA

Frontend variables:

- `NEXT_PUBLIC_API_BASE_URL=https://your-backend-domain/api/v1`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` or `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`

## Hosted Readiness

The repo now includes the hosting hardening requested in the security review:

- Frontend dependencies were updated and production `npm audit --omit=dev
  --audit-level=moderate` is clean.
- FastAPI has app-level rate limits for admin login, uploads, AI routes,
  assessment routes, and general traffic. A single free Render instance can use
  in-memory throttling; Redis/Upstash is recommended before scaling out.
- AI calls are capped per user and globally, use a response cache, and can be
  moved to queued resume-analysis jobs with `ASYNC_AI_JOBS_ENABLED=true`.
- Hosted mode requires Postgres/Supabase Postgres and rejects SQLite.
- Hosted mode requires private Supabase Storage; local `/files` serving is
  disabled unless explicitly allowed for development.
- Upload handlers enforce endpoint-specific size, extension, MIME, magic-byte,
  and extracted-text limits before storage or AI processing.
- Upload malware scanning can be enforced with `UPLOAD_SCAN_ENABLED=true` and a
  ClamAV TCP service.
- Profile-link crawling blocks private/reserved network targets, re-checks
  redirects, caps response size, limits redirects, and restricts content types.
- FastAPI and production Next responses set CSP/security headers.
- Admin actions are written to `audit_logs`; admin password resets/changes bump
  token versions so old admin JWTs are rejected.
- Hosted admin MFA can be required with `ADMIN_MFA_REQUIRED=true`, and admins can
  enroll/rotate MFA from the admin console.
- `/system/metrics` and `/api/v1/system/metrics` expose protected runtime
  metrics when called with `X-Monitoring-Token`.
- `backend/scripts/backup_runtime_data.py` can export and restore runtime tables.
- `backend/scripts/migrate_runtime.py` runs the idempotent runtime migrations.
- `.github/workflows/ci.yml` runs backend compile/Bandit and frontend
  test/lint/type/build/audit checks.
- `deploy/hosting.env.example` and `deploy/nginx.conf` provide hosted env and
  edge-limit templates.

Public hosting still requires real provider setup: managed Postgres backups,
private Supabase Storage bucket permissions, HTTPS domains, external monitoring
alerts, WAF/body-size limits at the edge, secret rotation, and a tested restore.
See [docs/HOSTING_SECURITY_REVIEW.md](docs/HOSTING_SECURITY_REVIEW.md).

When `APP_ENV` is `production`, `prod`, or `hosted`, backend startup fails if
required secrets are missing, default admin values are still configured,
localhost is left in `FRONTEND_ORIGIN`, Postgres is not configured, private
storage is not configured, an invalid rate-limit backend is configured, or
monitoring/MFA requirements are incomplete.

## Local Verification

Backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m compileall app
.\.venv\Scripts\python.exe -m bandit -r app -f txt
.\.venv\Scripts\python.exe scripts\migrate_runtime.py
Invoke-RestMethod http://127.0.0.1:8000/health
```

Frontend:

```powershell
cd frontend
npm run test:logic
npm run lint
npx tsc --noEmit
npm run build
npm audit --omit=dev --audit-level=moderate
```

API docs while the backend is running:

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`
- Curated reference: [docs/API.md](docs/API.md)

## Documentation

- [HOW_TO_RUN.md](HOW_TO_RUN.md): short local startup guide.
- [instructions.md](instructions.md): local and hosted runbook.
- [backend/README.md](backend/README.md): backend-specific setup and deployment.
- [frontend/README.md](frontend/README.md): frontend-specific setup and deployment.
- [docs/API.md](docs/API.md): current endpoint inventory.
- [docs/HOSTING_SECURITY_REVIEW.md](docs/HOSTING_SECURITY_REVIEW.md): security,
  scalability, and release-readiness analysis.
- [docs/testing-benchmark.md](docs/testing-benchmark.md): release test cases.
