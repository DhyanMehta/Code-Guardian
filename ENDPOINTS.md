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
  401/403. On a valid `pull_request` `opened`/`synchronize` event, dispatches a review
  and returns 202 Accepted. **[implemented — Session 1: signature verification + 202;
  actual review dispatch is a labeled stub until Session 5]**

## Reviews (dashboard-facing)
- `GET /reviews` — list past reviews (repo, PR #, status, summary, timestamp). **[planned — Session 5/6]**
- `GET /reviews/{id}` — full review detail incl. per-agent findings + ranking. **[planned — Session 5/6]**
- `GET /reviews/{id}/report` — rendered PR-comment markdown for a review. **[planned — Session 5/6]**

## Code Health (dashboard-facing)
- `GET /metrics/trends` — code-health metrics over time for charts. **[planned — Session 6]**

## Auto-Fix Gate
- `POST /reviews/{id}/autofix` — create an auto-fix commit on a new branch (never merges). **[planned — Session 5]**
- `POST /reviews/{id}/autofix/approve` — record explicit human approval for the auto-fix branch. **[planned — Session 5]**

---
Update this file whenever a route is added, changed, or promoted from planned to implemented.
