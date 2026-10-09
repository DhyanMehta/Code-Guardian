# CodeGuardian — final implementation plan

2026-10-09. Supersedes DEFERRED_FRONTEND_PLAN.md. The user resumed this work after the live Flask PR #2 verification. Work remains on Dhyan.

Implementation checkpoint, 2026-10-09: the subsequently approved remaining-flow order was onboarding → shared policy feedback → progress → completed results → Fleet/dashboard → measured Groq optimization → full verification. That work is now implemented. See FRONTEND_FLOW_VERIFICATION.md for checks and limits. The saved review #82 was reused; the later instruction not to rerun the PR supersedes the fresh-review step below.

## 1. Preserve verified repairs; align contracts

Keep the missing-worker explanation, nullable scanner_info contract, idle disabled queries, honest pending-result labels, test-file exclusion and responsive fixes. Baseline: 459 backend tests and 71 frontend tests; real review #81 completed in ~135 seconds with 12 findings and four successful agents.

The model/migrations store status as strings, not database enums. Current application Review.status values are pending, running, completed, failed, skipped. autofix_status is null, creating, pending_approval, approved, rejected, failed. Delivery remains null, pending, posted, failed. Do not conflate completed analysis with successful agents or successful delivery.

Add an append-only review_progress table (id, review_id, attempt, stage, agent nullable, status, created_at). Review detail gains attempt:number, heartbeat_at:string|null and progress:ProgressEvent[]. Each event has id:number, attempt:number, stage:string, agent:string|null, status:string, created_at:string. Stages: checkout, analysis, agent, aggregation. Statuses: started, ok, degraded, failed. Keep historical events, show only the current attempt in the active timeline, and never manufacture historical timestamps.

Persist events at actual boundaries and agent start/finish, using separate serialized database sessions rather than sharing a SQLAlchemy session across parallel nodes. Progress write failures must fail explicitly rather than claim success. Existing final findings/report remain atomically committed. A crashed attempt is shown as interrupted/retrying using authoritative review status and attempt, not as an agent success.

Existing nullable response fields remain unchanged: delivery_status:string|null, delivery_error:string|null, standards_version:string|null, findings[].evidence:object|null, agent_runs[].scanner_info:string|null (optional on legacy runs), agent_runs[].raw_findings:RawFinding[] (optional on legacy runs), autofix.commit_sha:string|null, autofix.error:string|null. Raw evidence stays separate from accepted finding counts.

## 2. Installation identity, authentication and onboarding

Keep HttpOnly session cookies, OAuth state validation, safe return paths and installation-scoped authorization. Public visitors see the landing page and a GitHub-colored sign-in action. After OAuth, users without an installation go to onboarding, then GitHub's actual repository-selection page. Returning installed users go to their requested page/dashboard. Cancelled or unavailable installation flows show a retry path rather than a redirect loop.

Expose a server-provided authenticated installation URL, using the configured GitHub App slug (or its persisted installation metadata). No hardcoded app name or fabricated repository selector. The GitHub setup URL returns to /auth/install; POST /auth/installations/refresh discovers access using the existing session automatically. Setup URL parameters are navigation signals only. Repository access is still verified server-side.

## 3. Profile review policy

Move the Auto/Manual control from repository settings to /profile. Show every active installation the user administers and explain that changes are shared with other users. Keep standards installation-scoped in repository settings. Members see policy but cannot change it.

GET /profile/review-mode returns installations:[{id:number,account_login:string,review_mode:'auto'|'manual'}], review_mode:'auto'|'manual'|'mixed'|null, version:string. PATCH accepts review_mode and version; live-check management access, reject stale scope/modes with 409, then update all eligible installations in one transaction. No partial save. Newly discovered installations retain their current policy until the user applies the setting again; show mixed state honestly. Existing queued work is not cancelled by switching modes. Auto controls new eligible PR webhooks across installed repositories; manual review remains available in both modes.

## 4. Active review and results UI

Show an animated, reduced-motion-aware progress panel with checkout/analysis/agent states, attempt and heartbeat. Do not estimate percentages or imply per-agent substeps that are not recorded. No final zero-findings/coverage summary while active.

Polling: review every 5 seconds while pending/running or autofix creating; readiness every 15 seconds while review active; transient failures back off 10,20,40,60 seconds and honor Retry-After. Pause hidden/offline, resume immediately when visible/online, never overlap requests. Stop analysis polling on completed/failed/skipped; pending/failed GitHub delivery polls every 15 seconds for at most three visible minutes, then exposes manual refresh. Terminal reports are retained through transient errors. No browser timeout turns a server job into a fake failure.

After completion show severity totals, filterable findings, evidence, scanner coverage, agent outcomes and delivery separately. Retain one review-level Create fix branch action: POST /reviews/{id}/autofix, with all eligible drafts. Never add a per-finding trigger; approval never merges.

## 5. Agent Fleet

Charts summarize loaded real review outcomes by agent: successful, degraded, failed, unrecorded. Active reviews are separate from completed coverage. State the loaded-history denominator and keep exact accessible counts beside graphics. Keep existing chronological analytics and explicit incomplete-coverage explanations.

## 6. Groq and reliability

Retain the existing shared concurrency gate, token reservations/reconciliation, finite retries and hard worker deadline. Audit request bounds and provider Retry-After handling; fix demonstrated gaps without changing provider/model silently. Model routing, caching and paid quota increases require measured evaluation and remain later optimization choices. Parallel agents do not imply unrestricted parallel model calls.

## 7. Verification and final handoff

Test event ordering/isolation, retries, migration round-trip, policy authorization/atomicity/stale edits, onboarding missing/success/denied states, polling stop/backoff and truthful graphs. Run complete backend tests including PostgreSQL/scanners, frontend tests and production build. Apply migration locally, restart the API/worker safely, and perform a fresh Flask PR #2 review from the frontend. Verify actual agent progress, completion, evidence and GitHub delivery. Do not create/approve branches or change installed repository selection merely for testing. Record actual results and remaining limitations; do not claim tests prove every possible input.
