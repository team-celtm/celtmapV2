# Security Policy

CELTM contains student profile, resume, certificate, assessment, and readiness
data. Treat hosted environments as sensitive systems.

## Supported Runtime

This repository currently supports the Phase 1 runtime documented in
[README.md](README.md) and [instructions.md](instructions.md). The old
RAG/Celery/Neo4j is not the active runtime for this checkout. Redis is used only
for hosted shared rate limiting when `RATE_LIMIT_BACKEND=redis`.

## Public Hosting Gate

The app now includes the code-level hosting controls requested in the security
review: patched frontend production audit baseline, app-level rate limits,
Redis-backed hosted rate limits, private-storage signed URL support, upload
validation, optional ClamAV scanning, SSRF-hardened profile link crawling,
Postgres-only hosted startup, security headers, audit logs, protected metrics,
admin MFA enrollment, and admin token revocation/versioning.

Before exposing a public environment, configure the deployment to actually use
those controls:

- Set `APP_ENV=production`, real HTTPS `FRONTEND_ORIGIN`, and strong admin/JWT
  secrets.
- Use `DATABASE_URL` or `SUPABASE_DATABASE_URL`; hosted mode rejects SQLite.
- Use `RATE_LIMIT_BACKEND=redis` and `REDIS_URL`; hosted mode rejects memory-only
  throttling.
- Use `STORAGE_BACKEND=supabase`, `SUPABASE_STORAGE_BUCKET`, and
  `ALLOW_LOCAL_FILE_SERVING=false`.
- Enable `UPLOAD_SCAN_ENABLED=true` with ClamAV or equivalent scanning before
  broad public uploads.
- Set `MONITORING_TOKEN`.
- Enable admin MFA with `ADMIN_MFA_REQUIRED=true` and `ADMIN_MFA_SECRET`.
- Configure managed backups, restore drills, edge body-size limits, WAF/bot
  rules, external uptime/error monitoring, and secret rotation.

The full checklist is in
[docs/HOSTING_SECURITY_REVIEW.md](docs/HOSTING_SECURITY_REVIEW.md).

## Secrets

- Never commit `.env`, `.env.local`, service-role keys, database URLs, or OpenAI
  keys.
- Only `NEXT_PUBLIC_*` values may be exposed to the browser.
- Supabase service-role keys must stay backend-only.
- Hosted mode must use strong `CELTM_JWT_SECRET`, `ADMIN_PASS`, and
  `ADMIN_GATEWAY_CODE`.

## Reporting

Until a formal security inbox exists, report vulnerabilities directly to the
project owner. Include the affected route, reproduction steps, expected impact,
and whether student/admin data can be read, modified, or deleted.
