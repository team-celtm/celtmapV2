# CELTM Phase 1 Runbook

This checkout uses the lightweight Phase 1 runtime.

## Architecture

- Backend: FastAPI.
- Frontend: Next.js.
- Local database: SQLite at `backend\data\celtm_phase1.sqlite3`.
- Hosted database: Postgres/Supabase Postgres through `DATABASE_URL` or
  `SUPABASE_DATABASE_URL`.
- Hosted uploads: private Supabase Storage with signed URLs.
- Hosted rate limiting: Redis-backed shared counters through `RATE_LIMIT_BACKEND=redis`.
- Student auth: Supabase Auth token validation.
- Institution/super-admin auth: backend JWT.
- Question bank: Supabase-backed question rows for live assessments.
- AI usage: resume, certificate, written-response, career-aim, and chat analysis
  when `OPENAI_API_KEY` is configured.
- Removed from current backend runtime: RAG, Celery, Neo4j, and heavy sync
  workers. Redis is used only when hosted shared rate limiting is enabled.

## Local Startup

From the project root:

```powershell
.\run-local.ps1
```

Open:

```text
http://127.0.0.1:3000/login
```

Backend health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Logs:

```text
backend\dev-backend.out.log
frontend\dev-frontend.out.log
```

## First-Time Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend\.env`, then install frontend dependencies:

```powershell
cd ..\frontend
npm install
```

## Local Default Super Admin

Unless overridden in `backend\.env`:

```text
Email: admin@celtm.com
Password: admin123
Gateway code: CELTM2026
```

These defaults are for local development only. Hosted mode blocks them when
`APP_ENV=production`, `prod`, or `hosted`.

Use the Institution login tab for both super admin and institution heads.

## Student Flow

1. Student signs up or logs in with Supabase Auth.
2. Student selects institute and department from backend-managed dropdowns.
3. Login opens the dashboard.
4. Dashboard prompts for resume upload when no resume analysis exists.
5. Resume analysis generates match score, keywords, red flags, strengths,
   weaknesses, and institute help.
6. Assessments improve readiness through server-side scoring.
7. Career Aim saves AI-generated or rule-assisted direction for desired roles.

## Institution Flow

1. CELTM super admin creates institutes, departments, and head/HOD accounts.
2. Institution heads log in through the Institution tab.
3. They can search/rank students from their allowed institute/department scope.
4. Each student popup shows readiness, strong points, weak points, and how the
   institute can help.
5. Admins can export CSV/PDF reports and create scheduled assignments.

## Manual Backend

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Manual Frontend

```powershell
cd frontend
npm install
npm run dev
```

## Hosted Checklist

Before public hosting:

1. Set `APP_ENV=production`.
2. Set `FRONTEND_ORIGIN` to the real HTTPS frontend origin only.
3. Set `DATABASE_URL` or `SUPABASE_DATABASE_URL`; do not use SQLite.
4. Set `STORAGE_BACKEND=supabase`, `SUPABASE_STORAGE_BUCKET`, and
   `ALLOW_LOCAL_FILE_SERVING=false`.
5. Replace `ADMIN_USER`, `ADMIN_PASS`, `ADMIN_GATEWAY_CODE`, and set a strong
   `CELTM_JWT_SECRET`.
6. Set `MONITORING_TOKEN`.
7. Set `RATE_LIMIT_BACKEND=redis` and `REDIS_URL`.
8. Enable admin MFA with `ADMIN_MFA_REQUIRED=true` and `ADMIN_MFA_SECRET`, then
   enroll per-admin MFA from the admin console.
9. Enable upload scanning with `UPLOAD_SCAN_ENABLED=true` and a ClamAV service
   before broad public traffic.
10. Run `backend\scripts\migrate_runtime.py` against the hosted database.
11. Configure `NEXT_PUBLIC_API_BASE_URL` to the hosted backend `/api/v1`.
12. Run `npm audit --omit=dev --audit-level=moderate`.
13. Configure provider-level HTTPS, WAF/body-size limits, external monitoring,
    managed database backups, and a tested restore.

The codebase now includes app-level rate limits, upload validation, private
storage support, signed URLs, SSRF hardening, security headers, audit logs,
monitoring endpoints, admin token revocation, and admin MFA hooks. The hosted
environment must still be configured to use them.

Use [deploy/hosting.env.example](deploy/hosting.env.example) as the hosted
environment template and [deploy/nginx.conf](deploy/nginx.conf) as an edge-limit
starter.

Full analysis: [docs/HOSTING_SECURITY_REVIEW.md](docs/HOSTING_SECURITY_REVIEW.md).

## Data

Local runtime files:

```text
backend\data\celtm_phase1.sqlite3
backend\data\uploads
```

These are ignored by Git. Delete them only if you intentionally want to reset
local Phase 1 app data.

Hosted backup:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\backup_runtime_data.py --output data\backups\celtm-runtime-backup.json
.\.venv\Scripts\python.exe scripts\backup_runtime_data.py --restore --input data\backups\celtm-runtime-backup.json
```

Hosted migration, health check, and secret generation:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\migrate_runtime.py
.\.venv\Scripts\python.exe scripts\check_hosted_health.py --base-url https://your-backend-domain --monitoring-token $env:MONITORING_TOKEN
.\.venv\Scripts\python.exe scripts\generate_hosted_secrets.py
```

## Verification

```powershell
cd backend
.\.venv\Scripts\python.exe -m compileall app
.\.venv\Scripts\python.exe -m bandit -r app -f txt
```

```powershell
cd frontend
npm run test:logic
npm run lint
npx tsc --noEmit
npm run build
npm audit --omit=dev
```
