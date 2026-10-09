# Frontend Phase 3 — implementation checkpoint

Implemented on 2026-10-07 against the current backend serializers and models.
Scope: frontend only. No backend edits, Git operations, dependency installs, or browser automation.

## Checkpoints

| Checkpoint | Delivered | Verification at checkpoint |
| --- | --- | --- |
| CP-1 Contracts and transport | Runtime response validation; exact nullable/optional fields; cookie credentials; structured errors; bounded read retries; no write replay | TypeScript, 30 tests, production build passed |
| CP-2 Identity | Canonical review IDs; installation-scoped routes and cache keys; bounded paginated PR/history lookup; safe return paths | TypeScript, 32 tests, production build passed |
| CP-3 Authentication | Real OAuth/session/logout; StrictMode single exchange; bootstrap race protection; installation selection and onboarding | TypeScript, 34 tests, production build passed |
| CP-4 Read pages | Real repositories, PRs, review details/reports, analytics, agent history, settings metadata; truthful coverage/evidence/delivery | TypeScript, 37 tests, production build passed |
| CP-5 Polling | Shared subscriptions, exact schedules, visibility/offline pause, backoff, terminal stop and delivery budget | TypeScript, 42 tests, production build passed |
| CP-6 Writes | Review trigger; one fix branch action; approve/reject; installation mode; UTF-8 Markdown standards upload/reset; ambiguous-write reconciliation | TypeScript, 48 tests, production build passed |
| CP-7 Cleanup | Removed production mock data and duplicate legacy contracts; accessible tabs/search/tooltips; corrected product claims | TypeScript, 50 tests, production build passed |
| CP-8 Flow verification | Installation ambiguity, legacy deep links, access/session loss, stale responses, bounded agent concurrency, stale heads, conflicts, upload/reset, terminal cache revisit | Final results below |

## Main implementation locations

- `src/api/contracts.ts`: backend-shaped types and runtime response parsers. `src/types/index.ts` re-exports these contracts.
- `src/api/client.ts`: credentialed API transport and timeouts.
- `src/api/resources.ts`, `polling.ts`: cached read subscriptions, cancellation, invalidation and automatic progress updates.
- `src/api/identity.ts`: validated route identities and paginated review lookup.
- `src/api/writes.ts`: duplicate-write guard and explicit reconciliation after ambiguous results.
- `src/context/`: real authentication and installation selection.
- `src/components/dashboard/`: independent pulls, analytics, agents and installation-settings tabs.
- `src/components/reviews/`: findings, evidence, coverage, trigger and review-level auto-fix actions.
- `src/test/`: backend-shaped fixtures and component/API integration tests; fixtures never enter production routes.

## Status and contract notes

The backend model/migrations use strings, not database enum constraints.

- Review: `pending`, `running`, `completed`, `failed`, `skipped`.
- Auto-fix: `null`, `creating`, `pending_approval`, `approved`, `rejected`, `failed`.
- Delivery: `null`, `pending`, `posted`, `failed`.
- Agent outcome: `null`, `unknown`, `ok`, `degraded`, `failed`.
- Severity: `critical`, `high`, `medium`, `low`, `info`, `unknown`.
- Unfamiliar contract values produce a visible error and stop dependent rendering rather than defaulting to success.
- Auto-fix POST response `status: created` is not a persisted status. Approve/reject response IDs are strings; review IDs and trigger response IDs are numbers.
- Missing historical agent runs omit scanner detail fields. They do not prove successful analysis.
- Delivery and analysis are independent; zero findings do not establish complete coverage.
- Raw scanner evidence remains separate from accepted findings. Quality evidence preserves verified/advisory classification and standards citations.
- `autofix.commit_sha` and `autofix.error` use the response names rather than database column names.
- Applied-fix item details are not exposed by the current detail endpoint. The UI shows the actual applied count, skipped reasons and commit/branch links.
- Metrics `autofix.created` is labeled “Auto-fix attempts,” because the backend includes non-null failed/in-progress states in that count.

## Polling behavior

- Pending/running reviews and `autofix.creating`: every 5 seconds after the previous response settles.
- Terminal reviews with delivery pending/failed: every 15 seconds, for a 3-minute visible monitoring budget. Then manual refresh is available. The UI does not claim backend delivery retries are exhausted.
- PR dashboard review discovery: every 5 seconds while a loaded review is active, otherwise every 30 seconds.
- Dashboard PR metadata: every 60 seconds.
- Error backoff: 10, 20, 40, then 60 seconds; success resets it. A longer Retry-After is honored.
- Hidden/offline pages pause and abort reads. Returning visible/online fetches immediately unless Retry-After still applies.
- No overlapping resource requests. Logout/navigation discards obsolete results.
- 401 expires the session; 403/404 and contract errors stop that resource and remove obsolete data.
- Reads cache for 30 seconds. Revisiting an expired terminal review revalidates it.
- Review status remains server-owned: the client never invents failure, live agent steps, percentages, or completion.

## Writes

“Create fix branch” is one review-level operation, with no finding IDs/body. It attempts all eligible drafts. Forks and known stale heads are blocked; the server remains authoritative for permissions and current-head validation.

Applied counts, skipped reasons and branch/commit links are visible before a decision. Approval records approval only; rejection does not delete the branch. No merge action exists.

Writes have a 120-second client timeout and are never automatically replayed. Ambiguous failures refresh available state and require explicit acknowledgement before another attempt. Network reads use a 15-second per-attempt timeout; ordinary reads retry at most twice after 1 and 2 seconds. Polling reads use the separate polling backoff.

Settings are installation-wide. Non-admin users see read-only settings. Standards accept `.md`, UTF-8, up to 512 KiB, using multipart field `file`. Upload and reset refetch server metadata. Earlier reviews retain their recorded standards version.

## Running locally

Configure a local frontend `.env` from `.env.example`:

```text
VITE_API_BASE_URL=http://localhost:8080
VITE_GITHUB_APP_SLUG=<actual GitHub App slug>
```

The frontend dev server uses port 5173 with strict port selection. Use the same hostname consistently for frontend, API and OAuth settings. The backend already supports `COOKIE_SECURE`; plain local HTTP needs its existing `COOKIE_SECURE=false` configuration. Production uses HTTPS and secure cookies. Backend CORS must allow the actual frontend origin with credentials.

Configure GitHub's OAuth callback to `/auth/callback` on the frontend origin. If using an installation setup URL, use `/auth/install`. New installation membership is refreshed through OAuth; installation query parameters alone do not authorize access.

Production hosting must serve the SPA entry point for `/auth/callback`, `/auth/install`, `/reviews/:id` and repository deep links.

Standard commands from `frontend/`:

```text
npx tsc --noEmit
npm test -- --run
npm run build
```

This Codex shell exposed Node but not npm/npx. Equivalent installed tools were executed directly:

```text
node node_modules/typescript/bin/tsc --noEmit
node node_modules/vitest/vitest.mjs run
node node_modules/typescript/bin/tsc -b
node node_modules/vite/bin/vite.js build
```

## Verification boundaries

Automated integration tests exercise real frontend components and transport against controlled backend-shaped responses. They cover successful/error transitions, identity isolation, polling, OAuth single exchange, creation/decisions, settings and file validation.

Browser automation was explicitly excluded in the approved plan. Actual GitHub redirects, browser cookie/CORS behavior, new-installation return flows, visual appearance and a live end-to-end PR run from this frontend have **not** been verified. No live GitHub writes were made during this frontend implementation.

Remaining deployment checks: supply the actual app slug; verify origin/cookie/OAuth configuration; verify the SPA fallback; manually exercise login, installation return, a real PR review, GitHub delivery, and fix-branch decisions in the browser.

## Final automated results

- TypeScript: passed.
- Vitest: 66 tests passed across 17 files.
- Production build: passed (`tsc -b` and Vite production bundle).
