# CodeGuardian AI — API Contract (living document)

Base URL (local dev): `http://localhost:8000`

Status legend: **[implemented]** = live as of the current session · **[planned]** = stubbed / future session.

## Health
- `GET /health/live` — liveness probe. Returns 200 if the process is up. **[implemented — Session 1]**
- `GET /health/ready` — readiness probe. Checks DB + ChromaDB reachability; degrades
  gracefully when dependencies are unavailable. **[implemented — Session 1]**

## GitHub Webhooks
- `POST /webhooks/github` — receives GitHub PR events. Verifies the HMAC signature
  (`X-Hub-Signature-256`) against `GITHUB_WEBHOOK_SECRET`. On invalid signature returns
  401/403. On a valid `pull_request` `opened`/`synchronize`/`reopened` event, creates a
  Review row, dispatches the supervisor graph as a background task, and returns 202
  Accepted with `review_id`. **[implemented — Session 1 (signature) + Session 5 (dispatch)]**

## Reviews (dashboard-facing)
- `GET /reviews` — list past reviews, newest first. Query params: `limit` (1-200,
  default 50), `offset`, `repo`. Returns an **envelope**
  `{items, total, limit, offset}` — `total` is the unfiltered-by-page row count so
  the dashboard can paginate without a second request. Each item carries `id`,
  `repo_full_name`, `pr_number`, `commit_sha`, `status`, `summary`, `is_fork`,
  `created_at`, `completed_at`, `finding_count`, `severity_counts` (all six severity
  keys always present), `agent_counts` (all four agents always present),
  `fixable_count`, `autofix_status`, `autofix_branch`, and `degraded_agents`.
  **[implemented — Session 5, envelope + counts added Session 6]**
  *Breaking change in Session 6: previously returned a bare JSON array.*
- `GET /reviews/{id}` — full review detail. `findings` is a flat array **pre-ranked**
  by the report builder's own ordering with a 1-based `rank`, so a finding's number
  matches the posted PR comment; `findings_by_agent` retains the grouped view with
  the same ranks. Also returns `severity_counts`, `agent_counts`, `fixable_count`,
  `agent_runs` (per-agent `outcome`/`recorded`/`finding_count`/`failure_reason`/
  `notes`/`scanner_statuses`/`scanner_info`), and an `autofix` object including
  `applied_count` and the durable `skipped_fixes` list.
  **[implemented — Session 5, extended Session 6]**
- `GET /reviews/{id}/report` — rendered PR-comment markdown for a completed or failed
  review. 409 while still pending/running. Agent statuses are read from persisted
  `review_agent_runs` rows, so the output is byte-identical to the comment that was
  posted to GitHub. **[implemented — Session 5, fidelity fixed Session 6]**

## Code Health (dashboard-facing)
- `GET /metrics/trends` — code-health metrics over time for charts. Query params:
  `repo`, `limit` (1-500, default 50), `days`, `since`. Returns `{range, repos,
  points, totals}`. `points` are **chronological (oldest first)** so charts read left
  to right — the opposite of `GET /reviews`. Each point carries per-review
  `severity_counts`, `agent_counts`, a `weighted_index`, and three coverage fields so
  a coverage gap is never rendered as an improvement: `degraded_agents` (agents that
  recorded a non-OK outcome), `unrecorded_agents` (agents with no persisted run at
  all), and `coverage_recorded` / `coverage_complete`. **`coverage_complete` is true
  only when coverage is both known and clean** — a review predating agent-run
  persistence is `coverage_recorded: false`, never `coverage_complete: true`.
  `totals` additionally reports `coverage_recorded_reviews`,
  `coverage_complete_reviews`, and `reviews_with_coverage_gap` so the dashboard can
  state how much of the series is a trustworthy baseline.
  `totals.weights_used` discloses the severity weights behind the index. No duration
  series: `completed_at` only exists from Session 6 onward. **[implemented — Session 6]**
  *Corrected in Session 6 Checkpoint 3: `coverage_complete` previously inferred a
  complete run from an empty `review_agent_runs` relationship, which reported all six
  legacy reviews as verified-complete.*

## Auto-Fix Gate
- `POST /reviews/{id}/autofix` — create an auto-fix commit on a new branch (never
  merges). Applies drafted tests and docstrings with apply-time re-validation.
  Returns 201 with branch name and applied/skipped counts. Returns 422 for fork PRs,
  409 if already pending, 400 if no fixable findings. **[implemented — Session 5]**
- `POST /reviews/{id}/autofix/approve` — record explicit human approval for the
  auto-fix branch. Requires `{"approved_by": "username"}` in body. **[implemented — Session 5]**
- `POST /reviews/{id}/autofix/reject` — reject the auto-fix branch. **[implemented — Session 5]**

## Authentication & User Session (Session 8)
- `GET /auth/github/login` — returns the GitHub OAuth authorization URL (`{url, state}`) for dashboard login. **[implemented — Session 8]**
- `POST /auth/github/callback` — exchanges the OAuth authorization code with GitHub for a user access token, queries user identity and installations live, upserts `users` (without storing user access tokens), syncs `user_installations` links, and returns an HS256 session JWT (`{token, token_type, user}`). **[implemented — Session 8]**
- `GET /auth/me` — returns profile and linked active installations for the authenticated user (`Authorization: Bearer <jwt>`). **[implemented — Session 8]**
- `POST /auth/logout` — acknowledges client-side session discard. **[implemented — Session 8]**

## Installations & Repository Discovery (Session 8)
- `GET /installations` — list installations linked to the currently authenticated user. Requires Bearer token. **[implemented — Session 8]**
- `GET /installations/{id}/repos` — live query to GitHub's `GET /installation/repositories` using the scoped installation access token. Verifies user access and returns accessible repositories. **[implemented — Session 8]**
- `GET /installations/{id}/repos/{owner}/{repo}/pulls` — list pull requests for a repository accessible to the installation. Query param: `state` (open/closed/all, default open). Requires Bearer token. **[implemented — Session 8]**

---
Update this file whenever a route is added, changed, or promoted from planned to implemented.

## CORS
The dashboard runs on a separate dev-server origin, so `CORSMiddleware` is enabled
with an explicit origin list from `CORS_ALLOWED_ORIGINS` (default
`http://localhost:5173,http://127.0.0.1:5173`), methods `GET`/`POST`/`OPTIONS`,
`allow_headers=["Content-Type", "Authorization"]`, and credentials disabled.
Never `*`: these endpoints create branches and record human approvals. **[extended Session 8]**
