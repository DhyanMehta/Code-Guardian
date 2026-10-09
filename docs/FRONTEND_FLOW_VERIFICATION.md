# Remaining frontend flow — implementation and verification

2026-10-09 · branch `Dhyan`. No commit, push, new PR review, fix branch, or live policy change was performed during this implementation.

## Delivered in the approved order

1. **Onboarding:** the installation return page automatically calls `POST /auth/installations/refresh`, updates session access and invalidates cached installation/repository data. It no longer requires a second OAuth login. The backend discovers access through GitHub, ignores setup IDs as authorization, reconciles membership/suspension, and preserves existing review policies. Cancellation, no installation and refresh errors retain a recovery action. Concurrent StrictMode calls share one request.
2. **Shared policy:** Profile lists administered installations, explains shared scope and newly connected installation behavior, handles mixed modes, disables duplicate/in-flight saves, and confirms the server-returned mode and installation count. Existing atomic authorization and stale-version checks remain in place; conflicts never show a saved message.
3. **Active reviews:** repository, PR, revision and status lead the page. The animated timeline uses persisted events; readiness distinguishes an unavailable worker from queued work. Pending results remain pending rather than displaying a fabricated clean result.
4. **Completed results:** summary, coverage and severity counts lead into filterable findings. Execution history is collapsed. Evidence, advisory labels, raw scanner results, draft previews, delivery and fix status remain distinct. There is one review-level Create fix branch action.
5. **Fleet/dashboard:** real outcome charts separate terminal, active and unavailable records. History checks every 5 seconds when loaded reviews are active, otherwise every 30 seconds; analytics refreshes every 30 seconds. Detail requests remain bounded to two concurrent requests. A changed review status bypasses the detail cache immediately; active detail cache TTL is 5 seconds, terminal TTL 30 seconds. Hidden/offline behavior uses the shared resource controller.
6. **Groq:** each agent emits a structured `agent_llm_metrics` log with repo/PR/revision, logical calls, actual requests, retries, responses reporting usage, reported total tokens, estimated reservations, gate wait, scheduled token/retry waits and total agent duration. Missing provider usage is identifiable from the reporting count; estimated reservations are not billed usage. Logs contain no prompt or response text. Spawned workers configure INFO logging. Security triage uses compact JSON and matching batch-size accounting; a regression test proves the parsed evidence is unchanged and the prompt is shorter. Existing model, evidence gates, quota controls and bounded retries remain unchanged.

## Polling contract

- Review: 5 seconds while pending/running or fix creation is active.
- Readiness: 15 seconds while analysis is active.
- Delivery pending/failed after terminal analysis: 15 seconds, capped at 3 visible minutes; then manual refresh remains available.
- Transient polling failures: 10/20/40/60-second backoff, honoring longer Retry-After values. Existing displayed data is retained.
- Hidden or offline: abort/pause; resume when visible/online, respecting any outstanding backoff. No overlapping requests. Terminal analysis without pending delivery/fix work stops polling.

## Verification results

- **472 backend tests passed**, with `CODEGUARDIAN_TEST_POSTGRES=1` and `CODEGUARDIAN_TEST_RUNTIME=1`: isolated PostgreSQL migration round-trip, worker locking/recovery, real Git/scanners/RAG, persisted reports, auth/permissions, progress, policy and LLM retry/limiter checks. Four existing pytest collection warnings concern imported Test* dataclasses/classes.
- The telemetry test initially depended on logging state changed by migration tests; it now restores its logger within the test. Full suite rerun passed.
- After enabling logging in spawned workers, all **4 PostgreSQL/runtime integration tests passed again**.
- **81 frontend tests passed** across 20 files; TypeScript and Vite production build passed.
- Browser with the real signed-in account: automatic installation refresh returned to Connected Repositories without OAuth; Profile showed the real administered installation and current Automatic mode; Fleet showed five terminal reviews with the genuine historical Quality degradation; review #82 showed 11 findings, 4/4 successful agents, evidence and posted delivery.
- Desktop viewport 1280px and mobile viewport 375px checked for review/Fleet layout and horizontal overflow. Browser console checks showed no errors or warnings during tested flows.
- API, PostgreSQL, ChromaDB, worker and configuration readiness returned `ready` with all four checks `ok`. Queue was empty; latest review remained #82.

## Boundaries

The real first-time GitHub installation/organization approval was not repeated or changed. Its return/no-access/error behavior is covered with controlled API/UI tests; the real existing-account refresh was exercised. No fresh Groq workload was submitted, so token telemetry will be populated on future work and no production latency/quota improvement is claimed. Model routing, response caching and provider/quota changes remain future measured decisions. Tests establish the checked behavior, not a guarantee against every possible error.

Screenshots: `scratch/frontend-final-review82-desktop.jpg`, `scratch/frontend-final-fleet-desktop.jpg`, and `scratch/frontend-final-review82-mobile.jpg`.
