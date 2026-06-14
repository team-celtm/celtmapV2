# CELTM Frontend

The frontend is a Next.js App Router application for the CELTM student,
institution, and admin web experience.

## Main Pages

- `/`: public landing page.
- `/login`: student Supabase login/sign-up and institution/admin login.
- `/onboarding`: student institution and profile setup.
- `/admin`: super-admin and institution-head console.
- Dashboard shell:
  - `/dashboard`
  - `/assessments`
  - `/assessments/[subjectId]`
  - `/assessments/quiz`
  - `/assessments/written-protocol`
  - `/career-aim`
  - `/competency-map`
  - `/hidden-skills`
  - `/interview-console`
  - `/learning-paths`
  - `/sessions`
  - `/settings`
  - `/skill-profile`
- `/assessment`: standalone assessment surface kept for compatibility.

## Local Setup

```powershell
cd frontend
npm install
npm run dev
```

The local dev server binds to `http://127.0.0.1:3000`.

When using `..\run-local.ps1`, `frontend/.env.local` is generated from
`backend/.env` if Supabase values are present.

## Required Environment

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-or-publishable-key
```

For hosted builds, `NEXT_PUBLIC_API_BASE_URL` must point to the hosted backend
`/api/v1` base path. The API client intentionally throws during module load when
the API base URL is missing.

## Hosted Notes

- Configure only HTTPS API and Supabase URLs.
- Keep admin JWTs in session storage only as a short-lived browser session. Treat
  XSS prevention as critical because bearer tokens are readable by client-side
  JavaScript.
- Production builds set CSP, HSTS, frame protection, content-type protection,
  referrer policy, and permissions policy through `next.config.ts`.
- `next.config.ts` allows localhost image hosts only outside production builds.
- Re-run `npm audit --omit=dev --audit-level=moderate` before release. The
  current production audit baseline is clean after upgrading Next and related
  packages.
- The institution/admin login form supports an optional MFA code. Hosted backend
  deployments can require it with `ADMIN_MFA_REQUIRED=true`.
- The admin console includes MFA enrollment, verification, rotation, and disable
  controls backed by `/api/v1/admin/mfa`.

## Checks

```powershell
cd frontend
npm run test:logic
npm run lint
npx tsc --noEmit
npm run build
npm audit --omit=dev --audit-level=moderate
```
