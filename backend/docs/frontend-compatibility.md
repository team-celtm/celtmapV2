# Frontend Compatibility

This phase does not modify the frontend. The backend now exposes the contracts the current UI can be wired to later.

## Current Mock Aliases

The existing frontend mock layer expects these endpoints:

- `POST /api/interview/start`
- `POST /api/interview/submit`
- `GET /api/learning-path`
- `GET /api/sessions`
- `GET /api/role-fit`
- `GET /api/skills`

Those compatibility aliases now exist and map to the versioned backend services.

Compatibility payload notes:

- `POST /api/interview/start` accepts optional `{ "roleName": "..." }`
- `POST /api/interview/submit` accepts `{ "sessionId"?, "roleName"?, "transcript"?, "mediaReference"? }`
- `POST /api/interview/submit` queues evaluation only when `transcript` or `mediaReference` is supplied
- `POST /api/interview/submit` returns `pending_input` with a `sessionId` when the frontend still needs to upload transcript or media

## Screen Mapping

`/dashboard`
- Ready for `/api/v1/dashboard/summary`

`/sessions`
- Ready for `/api/v1/sessions`
- Compatibility alias: `/api/sessions`

`/learning-path`
- Ready for `/api/v1/learning/path`
- Compatibility alias: `/api/learning-path`

`/interview`
- Ready for:
  - `/api/v1/interview/sessions`
  - `/api/v1/interview/sessions/{id}/transcript`
  - `/api/v1/interview/sessions/{id}/complete`
- Compatibility aliases:
  - `/api/interview/start`
  - `/api/interview/submit`

`/hidden-skills`
- Ready for:
  - `/api/v1/skills/me/hidden`
  - `/api/v1/skills/me/hidden/{id}/approve`
  - `/api/v1/skills/me/hidden/{id}/reject`

`/assessment`
- Ready for:
  - `/api/v1/mcq/questions`
  - `/api/v1/assessments`
  - `/api/v1/assessments/{id}/answers`
  - `/api/v1/assessments/{id}/complete`

`/assessment/live`
- Backend-ready for the same MCQ and assessment endpoints
- Live proctoring or media capture is not implemented in this phase

`/settings`
- Ready for:
  - `/api/v1/settings/me`
  - `/api/v1/settings/me/notifications`
  - `/api/v1/settings/me/security`

`/competency-map`
- Ready for:
  - `/api/v1/skills/me`
  - `/api/v1/skills/me/gaps`
  - `/api/v1/skills/me/role-fit`

`/profile`
- Ready for:
  - `/api/v1/profile/me`
  - `/api/v1/profile/me/avatar`
  - `/api/v1/profile/me/artifacts`

## Remaining Frontend Work

The frontend still needs a later wiring pass to:

- stop forcing mocks in `frontend/src/api.js`
- attach Supabase access tokens to API requests
- map current local component state to the new backend payloads
- handle async interview/report/dashboard refresh states
