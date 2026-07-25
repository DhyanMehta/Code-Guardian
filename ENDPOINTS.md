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
- `GET /reviews` — list past reviews (repo, PR #, status, summary, timestamp, finding
  count). Supports `limit` and `offset` query params. **[implemented — Session 5]**
- `GET /reviews/{id}` — full review detail incl. per-agent findings + auto-fix status.
  **[implemented — Session 5]**
- `GET /reviews/{id}/report` — rendered PR-comment markdown for a completed review.
  **[implemented — Session 5]**

## Code Health (dashboard-facing)
- `GET /metrics/trends` — code-health metrics over time for charts. **[planned — Session 6]**

## Auto-Fix Gate
- `POST /reviews/{id}/autofix` — create an auto-fix commit on a new branch (never
  merges). Applies drafted tests and docstrings with apply-time re-validation.
  Returns 201 with branch name and applied/skipped counts. Returns 422 for fork PRs,
  409 if already pending, 400 if no fixable findings. **[implemented — Session 5]**
- `POST /reviews/{id}/autofix/approve` — record explicit human approval for the
  auto-fix branch. Requires `{"approved_by": "username"}` in body. **[implemented — Session 5]**
- `POST /reviews/{id}/autofix/reject` — reject the auto-fix branch. **[implemented — Session 5]**

---
Update this file whenever a route is added, changed, or promoted from planned to implemented.
