# CELTM Web API Reference

This document summarizes the backend routes implemented under
`backend/app/api/`. The backend also exposes FastAPI's generated Swagger UI at
`/docs` and OpenAPI JSON at `/openapi.json` when the server is running.

## Base URLs

Local development:

```text
System endpoints: http://127.0.0.1:8000
Versioned API:    http://127.0.0.1:8000/api/v1
Compat API:       http://127.0.0.1:8000/api
```

The Next.js frontend should use:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

## Authentication

Most `/api/v1` endpoints require a Supabase access token:

```http
Authorization: Bearer <supabase-access-token>
```

Admin ingestion endpoints use the token returned by `POST /api/v1/admin/login`.
The admin override endpoint requires:

```http
X-Admin-Override-Token: <ADMIN_OVERRIDE_TOKEN>
```

Public/system endpoints:

- `GET /health`
- `GET /system/metrics`
- enhanced RAG routes under `/api/v1/rag-enhanced/*`
- `POST /api/v1/admin/login`

## Error Shape

Application errors are returned as JSON:

```json
{
  "error_code": "unauthorized",
  "message": "Bearer token is required"
}
```

FastAPI validation errors use the standard `detail` field.

Rate-limited requests return `429` and include:

- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `Retry-After`

## System

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | No | API health with Supabase, Redis, Neo4j, and worker service flags. |
| GET | `/system/metrics` | No | Request counters, latency, queue length, worker heartbeat, and recent failures. |

Example:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## Auth

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/v1/auth/me` | Supabase bearer | Return the authenticated user resolved from the token. |

Example:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/auth/me `
  -Headers @{ Authorization = "Bearer $env:SUPABASE_ACCESS_TOKEN" }
```

## Profile

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/profile/me` | Read the current user's profile. |
| PATCH | `/api/v1/profile/me` | Update profile fields and metadata. |
| POST | `/api/v1/profile/me/avatar` | Upload an avatar file. |
| POST | `/api/v1/profile/me/artifacts` | Upload a resume, certificate, or other career artifact. |
| GET | `/api/v1/profile/me/artifacts` | List uploaded artifacts. |
| PUT | `/api/v1/profile/me/artifacts/{artifact_id}` | Replace an artifact file. |
| DELETE | `/api/v1/profile/me/artifacts/{artifact_id}` | Delete an artifact. |

Profile update body:

```json
{
  "full_name": "Zian Surani",
  "headline": "AI Engineer",
  "focus_role": "Machine Learning Engineer",
  "weekly_goal": "Finish two assessments",
  "metadata": {
    "location": "India",
    "target_industry": "AI"
  }
}
```

Artifact upload uses `multipart/form-data`:

- `file`: required upload file
- `file_type`: optional, defaults to `resume`

## Settings

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/settings/me` | Read notification and preference settings. |
| PATCH | `/api/v1/settings/me` | Update general preferences. |
| PATCH | `/api/v1/settings/me/notifications` | Update notification-specific preferences. |
| GET | `/api/v1/settings/me/security` | Read security settings. |
| PATCH | `/api/v1/settings/me/security` | Update security mode. |

Notification update body:

```json
{
  "desktop_notifications": true,
  "weekly_digest": true,
  "folio_reminders": false,
  "folio_focus": "assessment"
}
```

Security update body:

```json
{
  "security_mode": "standard"
}
```

## Dashboard and Reports

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/dashboard/summary` | Dashboard projection for the current user. Add `?refresh=true` to force refresh. |
| GET | `/api/v1/reports/me/latest` | Latest generated report, or `null`. |
| POST | `/api/v1/reports/me/generate` | Generate a new report and refresh dashboard projection. |
| GET | `/api/v1/reports/me/passport.pdf` | Download the skill passport PDF. |

## Skills and Skill Requests

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/skills/me` | List the user's skills. |
| GET | `/api/v1/skills/me/role-fit` | Return best role fit. |
| GET | `/api/v1/skills/me/gaps` | Return skill gaps. |
| GET | `/api/v1/skills/me/hidden` | List hidden skill candidates. |
| POST | `/api/v1/skills/me/hidden/{candidate_id}/approve` | Approve a hidden skill candidate. |
| POST | `/api/v1/skills/me/hidden/{candidate_id}/reject` | Reject a hidden skill candidate. |
| GET | `/api/v1/skills/requests` | List skill requests. |
| POST | `/api/v1/skills/requests` | Create a skill request. |
| GET | `/api/v1/skills/requests/{request_id}` | Read a skill request. |

Skill request body depends on `SkillRequestCreate` in
`backend/app/schemas/skill_request.py`.

## MCQ and Assessments

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/mcq/questions` | Fetch a question batch by category, difficulty, skill, request, type, and limit. |
| GET | `/api/v1/assessments/log` | Assessment history across assessment types. |
| GET | `/api/v1/assessments/subjects` | Discover subjects available for the current user. |
| GET | `/api/v1/assessments/subjects/{subject_key}` | Subject detail and availability. |
| POST | `/api/v1/assessments` | Create an assessment session. |
| POST | `/api/v1/assessments/{assessment_id}/answers` | Submit one or more answers. |
| POST | `/api/v1/assessments/{assessment_id}/complete` | Complete and score an assessment. |

Question query parameters:

```text
category=<subject or category>
difficulty=<optional difficulty>
skill_id=<optional UUID>
skill_request_id=<optional UUID>
question_type=MCQ|situational|written
limit=1..50
```

Create assessment body:

```json
{
  "category": "Machine Learning",
  "assessment_type": "mcq",
  "question_type": "MCQ",
  "skill_id": null,
  "skill_request_id": null
}
```

Submit answers body:

```json
{
  "answers": [
    {
      "question_id": "question-id",
      "selected_option_id": "option-id"
    },
    {
      "question_id": "written-question-id",
      "answer_text": "Free-form answer text"
    }
  ]
}
```

## Placement

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/placement/status` | Return whether the user completed placement. |
| GET | `/api/v1/placement/questions` | Fetch placement questions, optionally by `role_name`. |
| POST | `/api/v1/placement/submit` | Submit placement answers and bootstrap trajectory modules. |

Submit body:

```json
{
  "role_name": "Machine Learning Engineer",
  "answers": [
    {
      "question_id": "question-id",
      "selected_option_id": "option-id"
    }
  ]
}
```

## Written Assessments

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/written-assessments` | List written assessment sessions. |
| POST | `/api/v1/written-assessments` | Create a written session. |
| GET | `/api/v1/written-assessments/{session_id}` | Read one written session. |
| PATCH | `/api/v1/written-assessments/{session_id}` | Save submission text. |
| POST | `/api/v1/written-assessments/{session_id}/complete` | Queue or run evaluation and return latest session state. |

Create body:

```json
{
  "skill_id": null,
  "skill_request_id": null,
  "prompt": "Explain overfitting and how to prevent it.",
  "evaluator_mode": "teacher"
}
```

Save submission body:

```json
{
  "submission_text": "A complete answer with at least 20 characters.",
  "evaluator_mode": "strict_ai"
}
```

`evaluator_mode` accepts:

- `teacher`
- `liberal_ai`
- `strict_ai`

## Learning and Trajectory

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/learning/path` | Get the learning path for `role_name` or the user's resolved focus role. |
| GET | `/api/v1/learning/resources` | Get resources for required `skill_name`. |
| POST | `/api/v1/trajectory/bootstrap` | Generate trajectory modules for a role. |
| GET | `/api/v1/trajectory/{role_name}` | Read trajectory for a role. |
| GET | `/api/v1/trajectory/me/alternates` | Return alternate role trajectories. |

Bootstrap body:

```json
{
  "role_name": "Machine Learning Engineer"
}
```

## Interview and Sessions

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/interview/sessions` | Create an interview session. |
| GET | `/api/v1/interview/sessions` | List interview sessions with `cursor` and `limit`. |
| POST | `/api/v1/interview/sessions/{session_id}/transcript` | Submit transcript text. |
| POST | `/api/v1/interview/sessions/{session_id}/media` | Submit media reference. |
| POST | `/api/v1/interview/sessions/{session_id}/complete` | Complete and queue evaluation. |
| GET | `/api/v1/interview/sessions/{session_id}/results` | Read interview result. |
| GET | `/api/v1/sessions` | Compatibility paginated session list. |

Create body:

```json
{
  "role_name": "Machine Learning Engineer",
  "skill_request_id": null,
  "interview_type": "role"
}
```

Transcript body:

```json
{
  "transcript": "Question and answer transcript..."
}
```

Media body:

```json
{
  "media_reference": "supabase/storage/path-or-url"
}
```

## Schedule

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/schedule/events` | Create an event. |
| GET | `/api/v1/schedule/events` | List events with cursor pagination. |
| PATCH | `/api/v1/schedule/events/{event_id}` | Update an event. |
| DELETE | `/api/v1/schedule/events/{event_id}` | Delete an event. |

Event schemas are in `backend/app/schemas/schedule.py`.

## Copilot and RAG

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/api/v1/copilot/chat` | Supabase bearer | Build a RAG-backed copilot reply. |
| POST | `/api/v1/rag-enhanced/search` | No | Enhanced semantic search. |
| GET | `/api/v1/rag-enhanced/search/quick` | No | Low-latency search by query string. |
| POST | `/api/v1/rag-enhanced/search/with-keywords` | No | Keyword-emphasized search. |
| GET | `/api/v1/rag-enhanced/stats/performance` | No | Enhanced RAG performance stats. |
| GET | `/api/v1/rag-enhanced/stats/cache` | No | Enhanced RAG cache stats. |
| POST | `/api/v1/rag-enhanced/cache/clear` | No | Clear enhanced RAG cache. |
| GET | `/api/v1/rag-enhanced/health` | No | Enhanced RAG health. |

Copilot body:

```json
{
  "page_context": "dashboard",
  "message": "What should I work on next?"
}
```

Enhanced search body:

```json
{
  "query": "React hooks basics",
  "top_k": 5,
  "user_id": "optional-user-id",
  "use_expansion": true
}
```

## Admin

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/api/v1/admin/login` | No | Exchange admin username/password for admin token. |
| POST | `/api/v1/admin/ingest-csv` | Admin bearer | Upload and ingest a CSV file. |
| POST | `/api/v1/admin/sync-celtmind` | Admin bearer | Queue CELTMIND sync. |
| GET | `/api/v1/admin/sync-celtmind/status` | Admin bearer | Read latest sync status. |
| POST | `/api/v1/admin/skill-requests/{request_id}/override` | Override header | Apply admin decision to a skill request. |

Admin login body:

```json
{
  "username": "admin@celtm.com",
  "password": "admin123"
}
```

Admin CSV upload uses `multipart/form-data`:

- `file`: CSV file
- `role_name`: optional role context

Skill request override body:

```json
{
  "decision": "approved",
  "reason": "Verified by admin"
}
```

## Compatibility Routes

The backend also exposes compatibility aliases under `/api` for older frontend
contracts:

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/interview/start` | Create interview session and return `sessionId`. |
| POST | `/api/interview/submit` | Submit interview transcript/media and queue evaluation. |
| GET | `/api/learning-path` | Compact learning path payload. |
| GET | `/api/sessions` | Compact recent interview sessions. |
| GET | `/api/role-fit` | Compact role-fit payload. |
| GET | `/api/skills` | Compact skill name to score map. |

Use `/api/v1` for new frontend work.
