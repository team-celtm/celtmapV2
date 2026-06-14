# CELTM Phase 1 API Reference

This reference reflects the current `backend/app/main.py` route surface.
Generated OpenAPI docs are available at `/docs` and `/openapi.json` when the
backend is running.

## Base URLs

Local:

```text
System:   http://127.0.0.1:8000
API v1:   http://127.0.0.1:8000/api/v1
Files:    http://127.0.0.1:8000/files
```

`/files` is a local development convenience only. Hosted mode requires private
Supabase Storage and signed URLs returned by the API.

Frontend local env:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

## Authentication

Student endpoints require a Supabase access token:

```http
Authorization: Bearer <supabase-access-token>
```

Admin and institution endpoints require the admin token returned by
`POST /api/v1/admin/login`:

```http
Authorization: Bearer <admin-access-token>
```

Public endpoints:

- `GET /health`
- `GET /api/v1/institutions`
- `GET /files/*` for local uploaded files when `ALLOW_LOCAL_FILE_SERVING=true`

`GET /api/v1/question-bank/status` is unauthenticated in code but calls the live
question-bank health check. Do not expose operational details publicly without a
gateway or WAF rule.

System metrics endpoints require `X-Monitoring-Token` in hosted mode or whenever
`MONITORING_TOKEN` is configured.

## System And Public

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | No | Health and service flags for database, Supabase auth, question bank, OpenAI, Redis/rate limiter, RAG, and Neo4j. |
| GET | `/api/v1/institutions` | No | Public institution and department list for onboarding. |
| GET | `/api/v1/question-bank/status` | No | Verifies live Supabase question-bank availability. |
| GET | `/system/metrics` | Monitoring token in hosted mode | Runtime request, error, audit, storage, and database metrics. |
| GET | `/api/v1/system/metrics` | Monitoring token in hosted mode | API-v1 alias for runtime metrics. |
| GET | `/files/{path}` | No | Local development file serving from `backend/data/uploads` when enabled. |

## Profile, Settings, And Evidence

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/profile/me` | Read or create the current user profile. |
| PATCH | `/api/v1/profile/me` | Update profile, institution, department, role, avatar URL, and metadata. |
| POST | `/api/v1/profile/me/evidence-links` | Validate LinkedIn/GitHub/portfolio/certificate links and record readiness evidence. |
| POST | `/api/v1/profile/me/avatar` | Upload avatar file. |
| GET | `/api/v1/profile/me/artifacts` | List uploaded resume/certificate/evidence artifacts. |
| POST | `/api/v1/profile/me/artifacts` | Upload a profile artifact. |
| GET | `/api/v1/profile/me/artifacts/{artifact_id}/signed-url` | Refresh a short-lived signed URL for a private artifact. |
| PUT | `/api/v1/profile/me/artifacts/{artifact_id}` | Replace an existing artifact. |
| DELETE | `/api/v1/profile/me/artifacts/{artifact_id}` | Delete an artifact. |
| GET | `/api/v1/settings/me` | Read current preferences. |
| PATCH | `/api/v1/settings/me` | Update preferences. |
| PATCH | `/api/v1/settings/me/notifications` | Update notification preferences. |
| PATCH | `/api/v1/settings/me/security` | Update stored security preference mode. |

Artifact upload is `multipart/form-data`:

- `file`: required.
- `file_type`: optional, defaults to `certificate`.

Upload handlers enforce endpoint-specific size limits, extension allowlists,
MIME/magic-byte checks, and extracted-text caps. Hosted uploads are stored in
private object storage and returned as `signed_url`/`file_url` values.

Resume analysis is a separate endpoint because it creates both an artifact and a
resume analysis record:

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/resume/analyze` | Upload and analyze a resume for the active target role. |
| GET | `/api/v1/resume/latest` | Return the latest resume analysis. |
| GET | `/api/v1/jobs/{job_id}` | Poll an owned background job, including queued resume-analysis jobs. |

When `ASYNC_AI_JOBS_ENABLED=true`, `POST /api/v1/resume/analyze` returns:

```json
{
  "status": "queued",
  "job_id": "job_id",
  "artifact_id": "artifact_id",
  "poll_url": "/api/v1/jobs/job_id"
}
```

## Dashboard, Readiness, Skills

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/dashboard/summary` | Current readiness dashboard projection. |
| GET | `/api/v1/readiness/events` | Readiness event history. |
| GET | `/api/v1/skills/me` | Current skill/domain scores. |
| GET | `/api/v1/skills/me/gaps` | Skill/domain gaps. |
| GET | `/api/v1/skills/me/role-fit` | Current role fit summary. |
| GET | `/api/v1/skills/me/hidden` | Hidden skill candidates. |
| POST | `/api/v1/skills/me/hidden/{candidate_id}/{action}` | Approve or reject a hidden skill candidate. |
| GET | `/api/v1/skills/requests` | Skill request list. |
| POST | `/api/v1/skills/requests` | Create a skill request. |

Hidden skill `action` accepts `approve` or `reject`.

## Assessments

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/assessments/subjects` | Available assessment subjects. |
| GET | `/api/v1/assessments/subjects/{subject_id}` | Subject detail and availability. |
| GET | `/api/v1/assessments/assignments` | Assigned tests visible to the student. |
| POST | `/api/v1/assessments` | Create an assessment attempt. |
| GET | `/api/v1/assessments/{assessment_id}/questions` | Get assigned/next questions. |
| POST | `/api/v1/assessments/{assessment_id}/answer` | Submit one answer. |
| POST | `/api/v1/assessments/{assessment_id}/answers` | Submit a batch of answers. |
| POST | `/api/v1/assessments/{assessment_id}/complete` | Complete and score an assessment. |
| GET | `/api/v1/assessments/log` | Completed assessment log. |
| GET | `/api/v1/assessments/subject-progress` | Subject-progress summary. |
| GET | `/api/v1/mcq/questions` | Legacy question fetch route. |

Create assessment body:

```json
{
  "mode": "quick",
  "category": "Communication",
  "assessment_type": "capability",
  "question_type": "MIXED",
  "assignment_id": null
}
```

Single-answer body:

```json
{
  "question_id": "question-id",
  "selected_answer": "A",
  "selected_option_id": "A",
  "time_taken_seconds": 42
}
```

## Written Assessments

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/written-assessments` | List written sessions. |
| POST | `/api/v1/written-assessments` | Create written session. |
| GET | `/api/v1/written-assessments/{session_id}` | Read one written session. |
| PATCH | `/api/v1/written-assessments/{session_id}` | Save answer text and evaluator mode. |
| POST | `/api/v1/written-assessments/{session_id}/complete` | Complete and evaluate written answer. |

Create body:

```json
{
  "skill_id": null,
  "skill_request_id": null,
  "evaluator_mode": "central_unbiased_ai",
  "assignment_id": null
}
```

Patch body:

```json
{
  "submission_text": "A complete written answer.",
  "evaluator_mode": "central_unbiased_ai"
}
```

## Learning, Reports, Schedule, Career, Chat

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/learning/path` | Learning path for the current profile/role. |
| GET | `/api/v1/reports/me/latest` | Latest report payload. |
| GET | `/api/v1/reports/assessment/{assessment_id}.pdf` | Download assessment report PDF. |
| GET | `/api/v1/reports/me/passport.pdf` | Download student passport PDF. |
| GET | `/api/v1/reports/me/dashboard.pdf` | Download dashboard PDF. |
| GET | `/api/v1/reports/me/dashboard.csv` | Currently forbidden for students; admin CSV export is separate. |
| GET | `/api/v1/schedule/events` | List schedule events. |
| POST | `/api/v1/schedule/events` | Create schedule event. |
| PATCH | `/api/v1/schedule/events/{event_id}` | Update schedule event. |
| DELETE | `/api/v1/schedule/events/{event_id}` | Delete schedule event. |
| GET | `/api/v1/career-recommendations` | Recommended career aims. |
| POST | `/api/v1/career-recommendations/draft-personality` | Save draft digital personality signals. |
| POST | `/api/v1/career-aspirations` | Create one career aspiration. |
| POST | `/api/v1/career-aspirations/recommended` | Create multiple recommended aspirations. |
| POST | `/api/v1/career-aspirations/{aspiration_id}/reanalyze` | Re-run aspiration analysis. |
| GET | `/api/v1/career-aspirations` | List aspirations. |
| POST | `/api/v1/chat` | CELTM assistant response from user context. |

Schedule body:

```json
{
  "title": "Mock interview",
  "starts_at": "2026-06-04T10:00:00+05:30",
  "ends_at": "2026-06-04T10:30:00+05:30",
  "event_type": "task",
  "metadata": {}
}
```

Career aspiration body:

```json
{
  "desired_role": "AI Engineer"
}
```

Chat body:

```json
{
  "message": "Where do I see my assessment stats?",
  "history": []
}
```

## Admin And Institution

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/api/v1/admin/login` | No | Login with admin/institution credentials. |
| GET | `/api/v1/admin/me` | Admin | Current admin identity. |
| GET | `/api/v1/admin/mfa` | Admin | Current MFA status for the admin account. |
| POST | `/api/v1/admin/mfa/enroll` | Admin | Create a pending TOTP secret and otpauth URL. |
| POST | `/api/v1/admin/mfa/verify` | Admin | Verify a TOTP code and enable MFA. |
| DELETE | `/api/v1/admin/mfa` | Admin | Disable account MFA when policy allows it. |
| POST | `/api/v1/admin/change-password` | Admin | Change current admin password. |
| GET | `/api/v1/admin/institutions` | Admin | List visible institutions. |
| POST | `/api/v1/admin/institutions` | Super admin | Create institution. |
| POST | `/api/v1/admin/departments` | Super admin | Create department. |
| POST | `/api/v1/admin/heads` | Super admin | Create institution/department head account. |
| GET | `/api/v1/admin/admin-accounts` | Super admin | List admin accounts. |
| POST | `/api/v1/admin/admin-accounts/{account_id}/reset-password` | Super admin | Reset an admin account password. |
| GET | `/api/v1/admin/students` | Admin | Student readiness cards in admin scope. |
| GET | `/api/v1/admin/students/export.csv` | Admin | CSV export of visible students. |
| GET | `/api/v1/admin/students/export.pdf` | Admin | PDF export of visible students. |
| GET | `/api/v1/admin/students/{user_id}` | Admin | Student detail in admin scope. |
| GET | `/api/v1/admin/students/{target_user_id}/passport.pdf` | Admin | Student passport PDF in admin scope. |
| GET | `/api/v1/admin/questions/sample.csv` | Super admin | Download question CSV template. |
| POST | `/api/v1/admin/ingest-csv` | Super admin | Upload question CSV, optionally assign as test. |
| POST | `/api/v1/admin/sync-celtmind` | Super admin | Refresh question-bank status. |
| POST | `/api/v1/admin/questions/sync` | Super admin | Alias for question-bank sync. |
| POST | `/api/v1/admin/courses` | Admin | Create course within allowed institution. |
| POST | `/api/v1/admin/questions` | Super admin | Create one Supabase question. |
| GET | `/api/v1/admin/question-sets` | Admin | List question sets. |
| GET | `/api/v1/admin/assessment-assignments` | Admin | List visible assignments. |
| POST | `/api/v1/admin/assessment-assignments` | Admin | Create scheduled assignment. |
| POST | `/api/v1/admin/assessment-assignments/{assignment_id}/terminate` | Admin | Terminate scheduled assignment. |

Admin login body:

```json
{
  "email": "admin@celtm.com",
  "password": "change-this-before-hosting",
  "mfa_code": "123456"
}
```

`mfa_code` is optional locally. Hosted deployments can require it with
`ADMIN_MFA_REQUIRED=true`.

Assignment body:

```json
{
  "title": "Communication readiness test",
  "department_id": "dept_id",
  "category": "Communication",
  "question_type": "MIXED",
  "assessment_type": "capability",
  "mode": "quick",
  "starts_at": "2026-06-04T10:00:00+05:30",
  "ends_at": "2026-06-04T11:00:00+05:30",
  "duration_minutes": 60,
  "instructions": "Answer all questions.",
  "question_set_id": null,
  "question_ids": []
}
```

## Error Shapes

FastAPI validation errors return the standard `detail` field. Application errors
also generally use `detail`:

```json
{
  "detail": "Bearer token is required"
}
```

The frontend API client reads both `message` and `detail`.

Rate-limited requests return `429` with a `Retry-After` header.
