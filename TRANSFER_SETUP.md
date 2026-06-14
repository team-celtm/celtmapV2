# CELTM Transfer Setup

Use this file after unzipping the project on another Windows PC.

## What Is Included

This transfer package keeps the project source, docs, env files, lock files, and
install manifests. It intentionally excludes installed/generated dependency
folders and caches such as:

- `frontend/node_modules`
- `backend/.venv`
- `.next`
- `__pycache__`
- `.pytest_cache`
- npm and Python cache folders

The receiver should install dependencies locally from the included
`backend/requirements.txt` and `frontend/package-lock.json`.

## Requirements

Install these first:

- Python 3.11 or newer
- Node.js 20 or newer, which includes npm
- Windows PowerShell

## One Command Install

From the unzipped project root, run this in PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\setup-local.ps1
```

From Command Prompt, run:

```bat
powershell -ExecutionPolicy Bypass -File .\setup-local.ps1
```

The script creates `backend\.venv`, installs Python packages from
`backend\requirements.txt`, and installs frontend packages with `npm ci` when
`frontend\package-lock.json` is present.

## Start The App

After install, run this from the project root:

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

Logs are written to:

```text
backend\dev-backend.out.log
frontend\dev-frontend.out.log
```

## Environment Files

The package includes env files per the sender's request. If the receiver needs
to change Supabase, OpenAI, database, admin, or hosted settings, edit:

```text
backend\.env
frontend\.env.local
```

If either env file is missing, use `backend\.env.example` as the backend
template. `run-local.ps1` can regenerate `frontend\.env.local` from Supabase
values in `backend\.env`.

## Manual Install

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Frontend:

```powershell
cd ..\frontend
npm ci
```

Return to the root and start:

```powershell
cd ..
.\run-local.ps1
```

## Verification

Backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m compileall app
```

Frontend:

```powershell
cd frontend
npm run test:logic
npm run lint
npx tsc --noEmit
npm run build
```
