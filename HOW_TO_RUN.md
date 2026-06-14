# CELTM Phase 1 - How To Run

## Requirements

- Python 3.11+
- Node.js 20+
- npm
- Windows PowerShell

## First-Time Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
cd ..\frontend
npm install
cd ..
```

Edit `backend\.env` with Supabase values before using student login.

## One-Command Start

From the project root:

```powershell
.\run-local.ps1
```

This starts:

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:3000`

Logs:

- `backend\dev-backend.out.log`
- `frontend\dev-frontend.out.log`

Open:

```text
http://127.0.0.1:3000/login
```

## Manual Backend

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## Manual Frontend

```powershell
cd frontend
npm run dev
```

## Local Admin

Default local-only credentials if not changed in `backend\.env`:

```text
Email: admin@celtm.com
Password: admin123
```

Hosted mode blocks these defaults only when `APP_ENV=production`, `prod`, or
`hosted`.

## Phase 1 Notes

- The old RAG/Celery/Neo4j backend has been removed from the current runtime.
  Redis is only needed for hosted shared rate limiting.
- Student login uses Supabase Auth.
- Institution and super-admin login uses backend admin login.
- Runtime app data is stored in `backend\data\celtm_phase1.sqlite3`.
- Local uploads are stored in `backend\data\uploads` and served by `/files` only
  when `ALLOW_LOCAL_FILE_SERVING=true`.
- Hosted mode uses Postgres/Supabase Postgres and private Supabase Storage with
  signed URLs.
- Hosted startup requires real production secrets, Redis-backed rate limiting,
  `MONITORING_TOKEN`, private storage configuration, and optional enforced admin
  MFA.
- Localhost does not require Redis, ClamAV, private object storage, or hosted
  secrets. Keep `RATE_LIMIT_BACKEND=memory` and `UPLOAD_SCAN_ENABLED=false` for
  normal local development.
- Resume, certificate, written assessment, career aim, and chat AI features use
  OpenAI only when `OPENAI_API_KEY` is configured.
- Assessments are server-scored and question-bank-backed.

## Verification

```powershell
cd backend
.\.venv\Scripts\python.exe -m compileall app
.\.venv\Scripts\python.exe scripts\migrate_runtime.py
```

```powershell
cd frontend
npm run test:logic
npm run lint
npm run build
npm audit --omit=dev --audit-level=moderate
```

For hosting/security checks, read
[docs/HOSTING_SECURITY_REVIEW.md](docs/HOSTING_SECURITY_REVIEW.md).
