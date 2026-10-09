# Current-stack repair and verification — 2026-10-08

Scope: repair and test the existing app. The frontend redesign remains deferred in [DEFERRED_FRONTEND_PLAN.md](DEFERRED_FRONTEND_PLAN.md).

## Confirmed problems and fixes

| Problem | Evidence / consequence | Repair |
| --- | --- | --- |
| Worker was not running | Flask review #80 was pending, attempt 0, no start time; worker heartbeat preceded its creation. API readiness returned 503 with only worker unavailable. | Started the separate worker, processed the existing request, documented required startup/readiness checks. Active review pages now show worker availability. |
| Completed detail rejected valid data | Live `/reviews/80` failed the frontend validator at `agent_runs[1].scanner_info`; the backend legitimately returns null when an agent has no scanner summary. | Type and runtime parser accept optional `string \| null`; regression test renders a fully recorded completed review with null summaries. |
| Disabled requests looked perpetually loading | A null resource key returned the loading snapshot despite making no request. | Disabled resources return an idle snapshot; regression verifies enabling them still fetches correctly. |
| Queued/running reviews looked like zero findings and missing coverage | Before completion the backend has not persisted agent results. | Explicit queued/running messages; pending results and coverage labels replace misleading zero-result presentation. |
| Test-gap agent proposed tests for test functions | Review #80 drafted a wrapper around `tests/test_billing.py::test_verify_account_status`. | Exclude recognized test files from gap targets, using the existing discovery rules. Four regression cases cover name/location patterns. Test discovery continues to inspect these files for production-code references. |
| Narrow-screen overflow | The navigation and long commit SHA exceeded the 348 px browser panel. | Navigation wraps and long main content breaks safely. Browser check confirmed document width equals viewport width. |

Readiness checks run every 15 seconds only while a review is active. Existing resource behavior pauses hidden/offline polling and backs off transient failures 10/20/40/60 seconds. Review status remains on its existing five-second cadence. The 503 readiness response is decoded as a structured not-ready state; other requests retain normal HTTP error handling. No fabricated per-agent progress was added.

## Verification results

- Backend: **459 passed, no skipped tests**, with `CODEGUARDIAN_TEST_POSTGRES=1` and `CODEGUARDIAN_TEST_RUNTIME=1`. Includes isolated PostgreSQL migration/queue tests and real scanner/Git/RAG integration; the integration test mocks LLM/GitHub delivery. Four existing pytest collection warnings concern imported classes named `Test*`.
- Frontend: **71 passed across 18 files**; production TypeScript/Vite build passed.
- Real browser: GitHub OAuth completed with user sign-in; connected repositories, Flask PR list, review details, saved report, analytics, Agent Fleet history, and settings loaded from the running API.
- Recovered review **#80** completed with 13 findings and all four agents successful. This historical snapshot retains the original false-positive test gap.
- Submitted fresh review **#81 through the frontend** for `DhyanMehta/flask-task-api` PR **#2**, commit `b126c02ce97f535e32d54c31333033a5cddd0f85`. Observed Queued → Running → Completed automatically.
- Review #81 ran from **21:04:03 to 21:06:18 IST** (~135 seconds), first attempt, **12 findings: 3 high, 2 medium, 3 low, 4 info**. All four agents succeeded. Semgrep, Bandit, and Gitleaks completed. The test-for-a-test finding/draft is absent.
- Verified the actual [GitHub report](https://github.com/DhyanMehta/flask-task-api/pull/2#issuecomment-6063456670) in the browser. Five eligible drafts were reported; no fix branch was created or approved during this live check.
- API readiness after recovery reported database, chromadb, worker, and configuration all `ok`.

## Boundaries

Automated tests exercise write contracts, authorization, retry/error behavior and autofix flows. Live settings changes, standards replacement, branch creation, approval/rejection, first-time installation, and externally induced outages were not performed on the user's installation. Browser layout verification used the available narrow panel; a requested desktop viewport override did not change its measured size, so desktop-specific visual verification is not claimed. Historical reviews are preserved, not rewritten.

The API, worker, and frontend must all remain running for local reviews. Current-stack fixes do not implement the deferred profile-wide policy control, onboarding redesign, live agent stages, new fleet graphs, or Groq optimization.
