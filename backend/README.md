# CELTM Phase 1 Backend

The backend is a FastAPI service that keeps the current CELTM runtime lightweight:
Supabase validates student sessions, backend JWTs protect institution/admin
routes, SQLite is used for local development, and Postgres/Supabase Postgres is
available for hosted deployments through `DATABASE_URL` or
`SUPABASE_DATABASE_URL`.

## Main Responsibilities

- Validate Supabase student bearer tokens.
- Issue and verify admin/institution JWTs.
- Store profiles, preferences, artifacts, readiness events, assessments,
  assignments, admin accounts, aspirations, and schedule events.
- Read/write Supabase question-bank rows for live assessments.
- Score objective assessments server-side.
- Evaluate resumes, certificates, written answers, career aims, and chat prompts
  with OpenAI when configured.
- Export dashboard, passport, assessment, and admin reports as PDF/CSV.

## Local Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe run_dev.py
```

The API serves at `http://127.0.0.1:8000`.

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## Environment

Use [backend/.env.example](.env.example) as the source template.

Important variables:

- `APP_ENV`: set to `production`, `prod`, or `hosted` in public deployments.
- `FRONTEND_ORIGIN`: comma-separated allowed browser origins.
- `SUPABASE_URL`: Supabase project URL.
- `SUPABASE_ANON_KEY` or `SUPABASE_PUBLISHABLE_KEY`: key used with student token
  validation.
- `SUPABASE_SERVICE_ROLE_KEY`: server-only key for question-bank writes.
- `DATABASE_URL` or `SUPABASE_DATABASE_URL`: hosted Postgres connection string.
- `CELTM_POSTGRES_SCHEMA`: defaults to `celtm_app`.
- `STORAGE_BACKEND`: `local` for development, `supabase` for hosted mode.
- `SUPABASE_STORAGE_BUCKET`: private upload bucket for hosted mode.
- `ALLOW_LOCAL_FILE_SERVING`: keep `true` only for local development.
- `SIGNED_URL_TTL_SECONDS`: signed upload URL lifetime.
- `RATE_LIMIT_BACKEND`: `memory` for local or a single free Render instance,
  `redis` for shared throttling across scaled instances.
- `REDIS_URL`: required only when `RATE_LIMIT_BACKEND=redis`.
- `RATE_LIMIT_AI_PER_HOUR` and `RATE_LIMIT_AI_GLOBAL_PER_MINUTE`: AI cost and
  provider-pressure controls.
- `AI_CACHE_ENABLED`, `AI_CACHE_TTL_SECONDS`, `AI_CACHE_MAX_ENTRIES`: provider
  response cache controls.
- `ASYNC_AI_JOBS_ENABLED`: optional queued resume-analysis mode.
- `UPLOAD_SCAN_ENABLED`, `CLAMAV_TCP_HOST`, `CLAMAV_TCP_PORT`: optional ClamAV
  upload scanning.
- `MONITORING_TOKEN`: required for hosted `/system/metrics`.
- `ADMIN_MFA_REQUIRED` and `ADMIN_MFA_SECRET`: hosted admin TOTP enforcement.
- `OPENAI_API_KEY`: enables AI-backed analysis.
- `ALLOW_HEURISTIC_AI_FALLBACKS`: keep `false` for release benchmarks.
- `ADMIN_USER`, `ADMIN_PASS`, `ADMIN_GATEWAY_CODE`, `CELTM_JWT_SECRET`: required
  admin security settings.

Hosted mode intentionally fails startup when default admin values, missing
secrets, missing database URL, public local file serving, missing private
storage, an invalid rate-limit backend, missing monitoring token, missing
required MFA secret, or localhost CORS origins are detected.

## Data Stores

Local development:

```text
backend/data/celtm_phase1.sqlite3
backend/data/uploads/
```

Hosted deployment:

- Use Postgres/Supabase Postgres through `DATABASE_URL` or
  `SUPABASE_DATABASE_URL`.
- Use private Supabase Storage for uploaded resumes, avatars, certificates, and
  written evidence. API responses include short-lived signed URLs. Local `/files`
  serving is acceptable for development only and is blocked by hosted-mode
  validation when `ALLOW_LOCAL_FILE_SERVING=true`.
- Use Redis/Upstash for hosted rate limiting before scaling beyond one backend
  instance. A single free Render instance can use `RATE_LIMIT_BACKEND=memory`.
- Enable ClamAV or an equivalent scanner with `UPLOAD_SCAN_ENABLED=true` before
  accepting broad public uploads.
- Use `scripts/migrate_runtime.py` during deployment before starting app
  instances.
- Keep Supabase service-role credentials server-side only.
- Back up runtime tables with `scripts/backup_runtime_data.py` and verify restore
  before public release.

## Route Groups

- Public/system: `/health`, `/api/v1/institutions`; `/system/metrics` and
  `/api/v1/system/metrics` require `X-Monitoring-Token` in hosted mode.
- Student: `/api/v1/profile/*`, `/settings/*`, `/resume/*`, `/dashboard/*`,
  `/skills/*`, `/assessments/*`, `/written-assessments/*`, `/learning/path`,
  `/reports/me/*`, `/schedule/events`, `/career-*`, `/chat`.
- Admin/institution: `/api/v1/admin/*`.
- Jobs: `/api/v1/jobs/{job_id}` for owned background processing status.
- Static local files: `/files/*` only when `ALLOW_LOCAL_FILE_SERVING=true`.

See [../docs/API.md](../docs/API.md) for the route inventory.

## Checks

```powershell
cd backend
.\.venv\Scripts\python.exe -m compileall app
.\.venv\Scripts\python.exe -m bandit -r app -f txt
.\.venv\Scripts\python.exe scripts\migrate_runtime.py
```

Current security observations are tracked in
[../docs/HOSTING_SECURITY_REVIEW.md](../docs/HOSTING_SECURITY_REVIEW.md).

Backup and restore:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\backup_runtime_data.py --output data\backups\celtm-runtime-backup.json
.\.venv\Scripts\python.exe scripts\backup_runtime_data.py --restore --input data\backups\celtm-runtime-backup.json
```

Hosted health check:

```powershell
.\.venv\Scripts\python.exe scripts\check_hosted_health.py --base-url https://your-backend-domain --monitoring-token $env:MONITORING_TOKEN
```

Secret generation for rotation:

```powershell
.\.venv\Scripts\python.exe scripts\generate_hosted_secrets.py
```
