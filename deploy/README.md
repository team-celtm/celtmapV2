# CELTM Render + Vercel Deployment

This repo is split into two hosted services:

- Render web service for `backend/`
- Vercel project for `frontend/`

## Render Backend

Create a Render Web Service from this GitHub repository.

- Root directory: `backend`
- Runtime: Python
- Build command: `pip install -r requirements.txt`
- Start command: `python scripts/migrate_runtime.py && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`

Pin Python with either `backend/.python-version` or the Render environment
variable `PYTHON_VERSION=3.12.8`.

Paste the variables from `deploy/hosting.env.example` into Render.

For a free single-instance Render backend, use:

```env
RATE_LIMIT_BACKEND=memory
REDIS_URL=
```

When scaling beyond one backend instance, switch to shared Redis or Upstash:

```env
RATE_LIMIT_BACKEND=redis
REDIS_URL=redis://...
```

Use Supabase Postgres for `DATABASE_URL` or `SUPABASE_DATABASE_URL`; do not use
SQLite on Render because its filesystem is ephemeral.

## Vercel Frontend

Import the same GitHub repository in Vercel.

- Root directory: `frontend`
- Framework preset: Next.js
- Build command: `npm run build`
- Install command: `npm install`

Paste the variables from `deploy/vercel.env.example` into Vercel.

`NEXT_PUBLIC_API_BASE_URL` must include the backend API prefix:

```env
NEXT_PUBLIC_API_BASE_URL=https://your-render-service.onrender.com/api/v1
```

After Vercel gives you the production URL, update the Render backend variable:

```env
FRONTEND_ORIGIN=https://your-vercel-project.vercel.app
```

Also add the Vercel URL in Supabase Auth settings as the Site URL and redirect
URL for browser login flows.
