# CELTM Phase 1 Handoff

This repository snapshot contains the Phase 1 CELTM web application prepared for
handoff to `team-celtm/celtmapV2`.

## Included Scope

- `frontend/`: Next.js App Router user interface for student, institution, and
  admin workflows.
- `backend/`: FastAPI runtime with local SQLite development support and
  hosted Postgres/Supabase configuration.
- `docs/`: API, hosting, security, and testing references.
- `deploy/`: hosting-oriented environment templates and deployment notes.
- Root runbooks: `README.md`, `instructions.md`, `HOW_TO_RUN.md`,
  `SECURITY.md`, `TRANSFER_SETUP.md`, `run-local.ps1`, and
  `setup-local.ps1`.

## Runtime Summary

- Frontend: Next.js, React, TypeScript, Tailwind CSS, Supabase JS.
- Backend: FastAPI, Pydantic settings, SQLite for local development, optional
  Postgres/Supabase Postgres for hosted mode.
- Auth: Supabase student sessions plus backend-issued JWTs for institution and
  super-admin access.
- Assessments: live Supabase question bank reads, scheduled assignments, and
  server-side scoring.
- AI: optional OpenAI-backed resume, certificate, written response, career aim,
  and chat analysis when `OPENAI_API_KEY` is configured.

## Local Start

Use PowerShell from the repository root:

```powershell
.\run-local.ps1
```

Then open:

```text
http://127.0.0.1:3000/login
```

For manual setup and hosted configuration, use `instructions.md` and
`README.md`.

## Publication Notes

- Do not commit local `.env` files, database files, upload data, build outputs,
  logs, or dependency folders.
- Recovery-code images are account credentials. A local
  `recovery codes.png` file is intentionally ignored by this handoff and should
  not be added to Git.
- Hosted deployments must use real secrets, private Supabase Storage, production
  CORS origins, and non-default admin credentials.

## Verification Commands

Recommended checks before release:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest

cd ..\frontend
npm run lint
npm run build
npm run test:logic
```
