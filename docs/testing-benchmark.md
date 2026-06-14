# CELTM Testing Benchmark

Use these cases before hosted release. Do not accept mock data, heuristic AI output, or silent fallback UI as a pass.

## Dashboard

1. Profile links only: save reachable LinkedIn/GitHub/portfolio links, do not upload a resume, and do not complete assessments. The dashboard must show profile-link readiness plus: "Add more about yourself and explore assessments to see insights." It must not show empty keyword or red-flag cards as if insights exist.
2. Resume breakdown: upload a real resume with weighted categories. Buckets such as education must render as points, for example `20/20`, and the bar should fill according to `score / max`, not `score / 100`.
3. Assessment insights: after completing an assessment, the dashboard must stop showing the links-only prompt and show assessment/subject insight sections from backend data.
4. Backend unavailable: if assessment log or subject-progress endpoints fail, the dashboard must show that insights are not available. It must not silently show empty history as a real state.

## Settings

1. Initial load: Settings must render the shell and active tab while secondary readiness evidence syncs. Users should see "Syncing readiness evidence..." instead of a frozen page.
2. Career suggestions: after building a draft digital personality, three career recommendations must appear in Settings.
3. Active career aim: clicking "Set as active career aim" on a recommendation must persist `profile.focus_role` and `settings.folio_focus`, update the visible Focus Role, and make the dashboard target match.
4. Link ingestion: saving LinkedIn, GitHub, portfolio, certificates, or additional links must call `/profile/me/evidence-links` and show validation status. If crawling fails, show not reachable/not available instead of invented evidence.

## Security And Hosted Configuration

1. Frontend build must fail if `NEXT_PUBLIC_API_BASE_URL` is not configured.
2. Hosted backend mode (`APP_ENV=production`, `prod`, or `hosted`) must fail fast when required secrets, database URL, frontend origin, or admin credentials are missing.
3. Hosted backend mode must reject default admin credentials and localhost CORS origins.
4. Production Next image config must not allow localhost image hosts.
5. `.env`, `.env.local`, and generated logs must stay ignored by git.

## AI And Fallbacks

1. If the AI provider returns no usable resume analysis, resume upload must return a clear 503 and mark the artifact analysis as failed. It must not create heuristic recruiter insights.
2. If the AI provider returns no usable written-assessment evaluation, the written session must become failed with a processing error. It must not create heuristic scores.
3. If the AI provider returns no usable credential evaluation, the credential artifact must be marked failed. It must not create heuristic credential scores.

## Commands

Run these checks before release:

```powershell
cd frontend
npm run test:logic
npm run lint
npx tsc --noEmit
npm run build

cd ..\backend
python -m compileall app
```
