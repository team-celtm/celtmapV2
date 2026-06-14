# CELTM Hosting, Security, And Scalability Review

Review date: 2026-06-04

This document covers the active Phase 1 runtime: FastAPI backend, Next.js
frontend, Supabase Auth/question bank, optional OpenAI analysis, SQLite for local
development, Postgres/Supabase Postgres for hosted mode, and private Supabase
Storage for hosted uploads.

## Executive Status

The original hosting blockers have been addressed in code. The app can now be
prepared for hosted deployment without changing the existing student,
assessment, admin, resume, certificate, dashboard, and career-aim flows.

Public deployment is still not just a code switch. The hosting environment must
provide real secrets, HTTPS origins, managed Postgres, private storage,
monitoring alerts, backup/restore operations, and edge protections.

## Implemented Hosting Controls

- `next` and related frontend packages were upgraded; `npm audit --omit=dev
  --audit-level=moderate` is clean.
- Next production responses set CSP, HSTS, frame protection, content-type
  protection, referrer policy, and permissions policy.
- FastAPI responses set matching security headers, with HSTS in hosted mode.
- App-level rate limits protect admin login, upload routes, AI routes,
  assessment routes, and general traffic.
- Hosted mode requires Redis-backed shared rate limiting. Local development
  still uses the memory limiter by default.
- AI routes have per-user and global limits; provider calls use an in-process
  response cache controlled by `AI_CACHE_*` settings.
- Resume analysis can run as a queued background job with
  `ASYNC_AI_JOBS_ENABLED=true`; the default remains synchronous for local/UI
  compatibility.
- Hosted mode fails startup unless Postgres/Supabase Postgres is configured.
- Hosted mode fails startup unless `STORAGE_BACKEND=supabase`,
  `SUPABASE_STORAGE_BUCKET` is set, and `ALLOW_LOCAL_FILE_SERVING=false`.
- Local `/files` static serving is only mounted when local file serving is
  enabled; hosted mode blocks it.
- Resume, artifact, avatar, and CSV uploads now enforce size, extension, MIME,
  magic-byte, and extracted-text limits.
- Optional ClamAV TCP upload scanning is available through
  `UPLOAD_SCAN_ENABLED=true`.
- Uploaded artifacts return signed URLs in API responses. A dedicated signed URL
  endpoint exists for artifact refresh.
- Supabase Storage uploads are private by default; signed URLs use
  `SIGNED_URL_TTL_SECONDS`.
- Profile-link crawling blocks loopback, private, reserved, link-local,
  multicast, and local-name targets, re-checks redirects, caps bytes, limits
  redirect count, and restricts content types.
- Admin login supports MFA codes. Hosted mode can require MFA with
  `ADMIN_MFA_REQUIRED=true`.
- Admins can enroll, verify, rotate, and disable account MFA from the admin
  console, subject to hosted MFA policy.
- Admin JWTs include token versions. Password changes and super-admin password
  resets bump token versions, invalidating older admin tokens.
- Admin login, failed login, MFA failures, password changes, resets, admin
  creates, question CSV ingest, student detail reads, and student exports write
  audit events.
- Protected runtime metrics are available at `/system/metrics` and
  `/api/v1/system/metrics` with `X-Monitoring-Token`.
- `backend/scripts/backup_runtime_data.py` supports JSON backup and restore for
  the Phase 1 runtime tables.
- `backend/scripts/migrate_runtime.py` records the runtime migration version
  after the idempotent schema pass.
- `.github/workflows/ci.yml` runs backend compile/Bandit and frontend
  test/lint/type/build/audit checks.
- `deploy/hosting.env.example`, `deploy/nginx.conf`, and
  `backend/scripts/check_hosted_health.py` provide hosted env, edge-limit, and
  monitoring check templates.

## Required Hosted Configuration

Backend:

```env
APP_ENV=production
FRONTEND_ORIGIN=https://your-frontend-domain
DATABASE_URL=postgresql://...
STORAGE_BACKEND=supabase
SUPABASE_STORAGE_BUCKET=celtm-private-uploads
SUPABASE_STORAGE_CREATE_BUCKET=false
ALLOW_LOCAL_FILE_SERVING=false
SIGNED_URL_TTL_SECONDS=900
RATE_LIMIT_BACKEND=redis
REDIS_URL=redis://...
RATE_LIMIT_AI_PER_HOUR=30
RATE_LIMIT_AI_GLOBAL_PER_MINUTE=120
AI_CACHE_ENABLED=true
AI_CACHE_TTL_SECONDS=86400
ASYNC_AI_JOBS_ENABLED=false
UPLOAD_SCAN_ENABLED=true
CLAMAV_TCP_HOST=clamav
MONITORING_TOKEN=strong-random-token
ADMIN_MFA_REQUIRED=true
ADMIN_MFA_SECRET=base32-totp-secret
CELTM_JWT_SECRET=strong-random-secret
ADMIN_USER=security-owned-admin-email
ADMIN_PASS=strong-random-password
ADMIN_GATEWAY_CODE=strong-random-code
```

Frontend:

```env
NEXT_PUBLIC_API_BASE_URL=https://your-backend-domain/api/v1
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-publishable-key
```

Hosted startup intentionally rejects missing secrets, default admin credentials,
localhost CORS origins, SQLite-only database configuration, public local file
serving, missing storage bucket, missing Redis shared rate limiting, missing
monitoring token, and missing MFA secret when MFA is required.

## Remaining Deployment Responsibilities

These items cannot be fully completed inside the repository:

- Create a private Supabase Storage bucket and verify only the backend service
  role can upload/sign/download private objects.
- Use a managed Postgres/Supabase Postgres plan with automated backups,
  point-in-time recovery where available, and connection pooling.
- Run and record a restore drill using
  `backend/scripts/backup_runtime_data.py --restore --input <backup-file>`.
- Add provider-level request body limits, WAF/bot rules, and IP throttling.
- Run the app behind Redis for shared throttling, and put the edge proxy/WAF in
  front of the FastAPI process. `deploy/nginx.conf` is a starter template.
- Deploy ClamAV or an equivalent upload scanning service before accepting
  sensitive uploads from broad public traffic.
- Add external uptime/error monitoring and alert routing for `/health` and
  `/system/metrics`.
- Rotate Supabase service-role keys, OpenAI keys, admin passwords, JWT secrets,
  monitoring tokens, and MFA secrets through the hosting provider secret store.
- Decide retention rules for resumes, certificates, extracted text, audit logs,
  reports, and generated AI output.
- Configure log redaction so resumes, certificate text, Supabase tokens, and
  OpenAI prompts are not emitted to hosted logs.
- Publish an incident contact and data export/delete process suitable for the
  target institution and jurisdiction.

## Scalability Needs

Good enough for hosted beta:

- Single or small FastAPI deployment behind HTTPS.
- Managed Postgres/Supabase Postgres.
- Private Supabase Storage.
- Redis-backed app rate limits plus provider-level edge limits.
- Optional OpenAI features with clear failures when keys are absent.
- Frontend request coalescing and normal Next production build output.

Pressure points for pilots:

- Certificate parsing, PDF generation, and CSV ingest still run in request
  handlers. Move them to background jobs when volume grows.
- Redis-backed rate limiting is required by hosted-mode validation. Keep
  provider gateway limits or WAF-backed counters in front of it.
- `backend/app/main.py` remains large. Split route groups into routers/services
  before more teams work on it.
- Add migration tooling before frequent schema changes.
- Add tenant-level quotas for AI calls, uploads, exports, and assessment
  attempts.

## Functional Needs Before Launch

- Role matrix for students, institution heads, department heads, and super admin.
- Admin recovery process that does not rely only on bootstrap environment
  values.
- Support flow for failed uploads, AI unavailability, invalid Supabase sessions,
  and unavailable question-bank subjects.
- CSV question-bank validation and rollback process.
- Assignment integrity and retake policy.
- Student data export/delete policy.
- Backup restore evidence for each hosted release.
- Release checklist that includes dependency audit, backend scan, frontend build,
  route smoke tests, and real login/browser checks.

## Verification Commands

Backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m compileall app scripts\backup_runtime_data.py
.\.venv\Scripts\python.exe -m bandit -r app -f txt
.\.venv\Scripts\python.exe scripts\migrate_runtime.py
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

Runtime smoke:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/system/metrics
```

Hosted metrics require:

```powershell
Invoke-RestMethod https://your-backend-domain/system/metrics `
  -Headers @{ "X-Monitoring-Token" = "your-monitoring-token" }
```

## Short Recommendation

Proceed with a hosted beta only after the hosted environment is configured with
the required production variables, managed Postgres backups, private storage,
monitoring alerts, edge request limits, and a tested restore. Do not turn off
the hosted-mode startup guards to make deployment easier.
