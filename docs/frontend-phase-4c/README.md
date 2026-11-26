# Phase 4c · Review execution, GitHub delivery and auto-fix decisions

**Phase 4 implemented and verified, awaiting final review.** Both authenticated reference journeys passed across the approved responsive layout. Review #79 has timestamps and an attempt number, but zero checkpoint events. Review #90 has 19 checkpoint events. Both reviews have a published GitHub comment. These differences are visible independently of finding counts and specialist coverage.

## A–B. Baseline and files

The baseline was the existing Phase 4b working tree on `codex/durable-review-pipeline`, HEAD `dc9b6af4149764ae66e2ca10974c151a6bf819a0`. The index was empty. Earlier changes, audit, plan and screenshots remained in the working tree. There was no separate frontend checkpoint. No files were staged or committed.

| Production or test file | Phase 4c change |
|---|---|
| [ReviewDetailPage.tsx](../../frontend/src/pages/ReviewDetailPage.tsx) | Retains review ownership, timestamps, section anchors and shared PR head. Composes timeline, delivery and one proposal owner. |
| [ReviewProgress.tsx](../../frontend/src/components/reviews/ReviewProgress.tsx) | Queued, retrying and running labels with independent readiness feedback. |
| [AgentTimeline.tsx](../../frontend/src/components/reviews/AgentTimeline.tsx) | Attempts, exception summaries, current provider waits and timestamped event lists. |
| [ReviewDelivery.tsx](../../frontend/src/components/reviews/ReviewDelivery.tsx) | Delivery state, verified comment destination and explicit report retrieval. |
| [AutofixActions.tsx](../../frontend/src/components/reviews/AutofixActions.tsx) | Integrates the saved proposal, revision, skipped targets, decisions and existing scoped mutations. |
| [ReviewOverview.tsx](../../frontend/src/components/reviews/ReviewOverview.tsx) and [diagnosticText.ts](../../frontend/src/components/reviews/diagnosticText.ts) | Withhold diagnostic strings containing recognized credential patterns, including in failed or skipped review summaries. |
| [identity.ts](../../frontend/src/api/identity.ts) | Validates the two repository path components before constructing external links. |
| [reviewOperations.test.tsx](../../frontend/src/test/reviewOperations.test.tsx) | Fourteen regression cases for execution, delivery, report recovery and proposal requests. |
| [Implementation checklist](../../tasks/todo.md), [regression checklist](../../UI_REGRESSION_CHECKLIST.md) and this directory | Milestone status, report and verification artifacts. |

## C–F. Execution before and after

Previously, the terminal timeline hid its current-attempt summary under an outer disclosure. It showed the last checkpoint for each of four agents. An earlier failed attempt and the intermediate events of the current attempt could disappear. GitHub delivery showed a raw state and a comment link. Proposal metadata and its operations occupied separate panels, and the desktop revision-refresh target measured 16 px high.

The execution section now groups the response by recorded attempt. The most recent attempt is first. Within each attempt, the ordered list retains the API’s persisted event-ID order, including concurrent specialists and provider waits. Failure, degradation and starts without a recorded finish are visible with the timeline closed. Each row identifies the stage, specialist where present, recorded status and source time. A missing completion checkpoint can coexist with a completed review. The UI makes no claim about an unobserved stage duration or a worker’s present health from an old heartbeat.

Active progress keeps review state separate from the readiness read. The queued state can report a retry, and running reviews expose available provider wait reasons. Final findings remain gated on terminal state. Native timestamp disclosures retain offsets and fractions. An unavailable or malformed time has a written fallback, with its original string available when supplied. For example, #79’s recorded start is `2026-10-06T22:04:30.577029+05:30`. [#79 historical evidence](execution-evidence-79.jpg) · [#90 checkpoint records](recorded-checkpoints-90.jpg)

## G–H. Delivery and saved Markdown

| Recorded state | User-visible behavior |
|---|---|
| Posted, valid destination | View GitHub Report opens the recorded PR comment. The comment ID is visible. |
| Posted, missing or invalid destination | Shows the recorded delivery outcome and explains that the destination is unavailable. |
| Pending | Publication awaits confirmation. The existing bounded monitoring policy applies. |
| Failed | Displays the delivery failure and available diagnostic, independently of completed analysis. |
| Null | Displays Not recorded. |

The report button is available for completed and failed reviews. Opening it uses the existing authenticated `GET /reviews/{id}/report`. The scoped resource exposes loading, delayed reads and retry. Empty text or an inconsistent review ID gives an unavailable message. Returned Markdown is rendered as selectable, focusable plain text. The endpoint can return saved Markdown or render from persisted historical records. Its response carries no origin flag. The frontend preserves that distinction in the button label and performs no reconstruction or publication.

## I–J. Proposal matrix and safeguards

| Condition | Behavior and source of authority |
|---|---|
| No proposal, eligible drafts | Shows the recorded eligible count and explicit Create fix branch action. Apply-time validation may skip drafts. |
| No eligible drafts, fork or incomplete review | Visible reason and disabled creation action. |
| Local submission pending or server records creating | Duplicate activation is locked in the user/review operation scope. Persisted creation is polled by the existing review resource. |
| Saved proposal or awaiting decision | Displays branch, commit, applied count and skipped targets/reasons where recorded. Approval and rejection are distinct native buttons. |
| Approved or rejected | Shows the decision from the saved review. Approval identity and time appear when supplied. Approval records a decision. Rejection leaves the branch available. |
| Known stale revision | Creation and approval are blocked. The existing proposal remains readable and rejection remains available. |
| Current head unknown | Freshness is explicitly unconfirmed. The original server-side creation validation and approval contract apply. The approval API checks the saved proposal commit when one exists. A PR-head refresh is available to the reader. |
| Known permission denial | The recorded error remains visible and operations are disabled. A user can explicitly allow another attempt after an access change. The server reauthorizes each operation. |
| Conflict | Settlement invalidates the scoped review and repository history, so a decision recorded elsewhere can appear. |
| Ambiguous response | The scoped uncertainty guard prevents repeat submission, including across navigation. Existing reconciliation accepts a change in saved status or an explicit retry acknowledgement. |
| Missing data or read failure | A failed authorized read has recovery feedback. The interface uses available saved identifiers and counts. A restricted or missing review cannot supply a proposal. |

The same component owns the three bodyless POSTs to `/reviews/{id}/autofix`, `/approve` and `/reject` under that auto-fix path. The create receipt carries the branch, applied count and skipped data. Decision receipts carry a string review ID and the decision. Existing response validators, user/review locks, cache invalidation and server-side installation membership and repository write checks remain in use. The saved review supplies final proposal state. Mutation tests exercise these operations only against isolated responses.

Three further authenticated records supplied real proposal evidence. #29 and #83 await decisions, and #82 holds an approval with an approver and timestamp. The two pending captures include an in-flight head lookup. They establish proposal identity and status only. [#29 pending](saved-proposal-29.jpg) · [#83 pending](saved-proposal-83.jpg) · [#82 approved](saved-proposal-82.jpg) · [Read traces and recorded fields](saved-proposals.json)

## K. Polling and resource ownership

ReviewById owns one user/review resource and one polling policy. Pending, running and proposal creation schedule a five-second review refresh. Terminal pending or failed delivery schedules 15-second reads for up to three visible minutes. Terminal posted or absent delivery stops monitoring unless creation is active. Explicit refresh reopens the monitoring budget. The active-only readiness read runs at 15 seconds. The PR header and proposal consume a single shared head lookup.

Hidden or offline transitions cancel the timer and in-flight resource read. Visibility restoration resumes eligible resources. Transient polling errors back off from ten seconds to sixty seconds and honor a longer Retry-After. Version and cancellation guards discard superseded reads. Disclosure, viewport changes and section navigation do not create review or head subscriptions. The report has its own user/review key and starts only on demand.

## L–M. Responsive and accessibility verification

CSS pixels, 25 November 2026, local in-app browser in GMT+05:30. Each row samples both reviews, all three sections and both working-tree versions. The section heights shown below are for #79. The linked measurements also include section widths, page positions, control typography and #90’s figures.

| Viewport | Section width | Execution height, before → after | Delivery height, before → after | Proposal height, before → after | Document overflow |
|---:|---:|---:|---:|---:|---:|
| 1920 | 1232 | 188 → 272 | 284 → 258 | 342 → 236 | 0 |
| 1440 | 1232 | 188 → 272 | 284 → 258 | 342 → 236 | 0 |
| 1024 | 970 | 200 → 284 | 284 → 258 | 342 → 236 | 0 |
| 768 | 714 | 200 → 284 | 284 → 258 | 362 → 258 | 0 |
| 700 | 646 | 204 → 292 | 292 → 262 | 389 → 266 | 0 |
| 390 | 353 | 292 → 410 | 292 → 338 | 473 → 338 | 0 |
| 320 | 282 | 308 → 426 | 312 → 338 | 518 → 360 | 0 |

Execution uses more height to keep the heartbeat, attempt and evidence availability in view. At 320 px, #79’s first execution timestamp stayed at document y=4503. At 1440 px it stayed at y=2597. The first proposal control at 1440 px moved from y=3262 to y=3212 and grew from 16 px to 40 px. At 320 px the first proposal control measured 44 px. Timestamp targets ranged from 40 to 52 px as labels wrapped. The desktop event disclosure measured 40 px, event text 15 px and timestamp metadata 13 px on desktop or 14 px on compact screens.

The keyboard sequence reaches the section navigation, event and timestamp summaries, GitHub link, report button, report text when expanded, and permitted proposal actions. The compact chooser retained its original section destinations. Keyboard focus on View GitHub Report showed a 1.6 px indigo outline. The focus/link token against the panel has a contrast ratio above 8:1, muted text on that panel is 8.81:1, and primary text is 16.22:1. Status and failure text supplement color. Disclosure and resize introduce no new animation or routine live-region announcements. A screen-reader certification assessment was outside this verification. [Focus](keyboard-focus-90.jpg) · [Mobile chooser](mobile-section-chooser.jpg) · [#79 geometry before](before-79.json) / [after](after-79.json) · [#90 before](before-90.json) / [after](after-90.json)

## N–P. Engineering checks

| Check | Result |
|---|---|
| Focused regression | 144 passed across 14 files. Includes reviewOperations, reviewWorkspace, findingsEvidence, reviewProgress, polling, readFlows, writeFlows, reliabilityFlows, finalFlow, identity, repositoryNavigation, FriendlyTimestamp, ScopedRefreshStatus and SharedFeedback. SharedFeedback exercises StatusBadge. |
| Full frontend suite | 242 passed across 32 files. |
| Production build | TypeScript project build and Vite production build passed. |
| Git whitespace | `git diff --check` passed. |

New assertions cover historical attempts, event order, focus retention, missing time, valid and invalid comment destinations, an empty report, read failure/retry, redacted diagnostics, fork/unknown/stale protections, permission denial, late responses, reconciliation and the exact three request contracts. Existing tests continue to cover hidden/offline polling, retry backoff, terminal monitoring, scoped head reads, saved decisions, conflict recovery, prior review filters and stable finding anchors.

## Q. Authenticated screenshots

Each cell links a baseline and redesigned capture of the same saved review and viewport.

| Width | #79 execution | #79 delivery | #79 proposal | #90 execution | #90 delivery | #90 proposal |
|---:|---|---|---|---|---|---|
| 1920 | [Before](before-79-execution-1920.jpg) / [After](after-79-execution-1920.jpg) | [Before](before-79-delivery-1920.jpg) / [After](after-79-delivery-1920.jpg) | [Before](before-79-autofix-1920.jpg) / [After](after-79-autofix-1920.jpg) | [Before](before-90-execution-1920.jpg) / [After](after-90-execution-1920.jpg) | [Before](before-90-delivery-1920.jpg) / [After](after-90-delivery-1920.jpg) | [Before](before-90-autofix-1920.jpg) / [After](after-90-autofix-1920.jpg) |
| 1440 | [Before](before-79-execution-1440.jpg) / [After](after-79-execution-1440.jpg) | [Before](before-79-delivery-1440.jpg) / [After](after-79-delivery-1440.jpg) | [Before](before-79-autofix-1440.jpg) / [After](after-79-autofix-1440.jpg) | [Before](before-90-execution-1440.jpg) / [After](after-90-execution-1440.jpg) | [Before](before-90-delivery-1440.jpg) / [After](after-90-delivery-1440.jpg) | [Before](before-90-autofix-1440.jpg) / [After](after-90-autofix-1440.jpg) |
| 1024 | [Before](before-79-execution-1024.jpg) / [After](after-79-execution-1024.jpg) | [Before](before-79-delivery-1024.jpg) / [After](after-79-delivery-1024.jpg) | [Before](before-79-autofix-1024.jpg) / [After](after-79-autofix-1024.jpg) | [Before](before-90-execution-1024.jpg) / [After](after-90-execution-1024.jpg) | [Before](before-90-delivery-1024.jpg) / [After](after-90-delivery-1024.jpg) | [Before](before-90-autofix-1024.jpg) / [After](after-90-autofix-1024.jpg) |
| 768 | [Before](before-79-execution-768.jpg) / [After](after-79-execution-768.jpg) | [Before](before-79-delivery-768.jpg) / [After](after-79-delivery-768.jpg) | [Before](before-79-autofix-768.jpg) / [After](after-79-autofix-768.jpg) | [Before](before-90-execution-768.jpg) / [After](after-90-execution-768.jpg) | [Before](before-90-delivery-768.jpg) / [After](after-90-delivery-768.jpg) | [Before](before-90-autofix-768.jpg) / [After](after-90-autofix-768.jpg) |
| 700 | [Before](before-79-execution-700.jpg) / [After](after-79-execution-700.jpg) | [Before](before-79-delivery-700.jpg) / [After](after-79-delivery-700.jpg) | [Before](before-79-autofix-700.jpg) / [After](after-79-autofix-700.jpg) | [Before](before-90-execution-700.jpg) / [After](after-90-execution-700.jpg) | [Before](before-90-delivery-700.jpg) / [After](after-90-delivery-700.jpg) | [Before](before-90-autofix-700.jpg) / [After](after-90-autofix-700.jpg) |
| 390 | [Before](before-79-execution-390.jpg) / [After](after-79-execution-390.jpg) | [Before](before-79-delivery-390.jpg) / [After](after-79-delivery-390.jpg) | [Before](before-79-autofix-390.jpg) / [After](after-79-autofix-390.jpg) | [Before](before-90-execution-390.jpg) / [After](after-90-execution-390.jpg) | [Before](before-90-delivery-390.jpg) / [After](after-90-delivery-390.jpg) | [Before](before-90-autofix-390.jpg) / [After](after-90-autofix-390.jpg) |
| 320 | [Before](before-79-execution-320.jpg) / [After](after-79-execution-320.jpg) | [Before](before-79-delivery-320.jpg) / [After](after-79-delivery-320.jpg) | [Before](before-79-autofix-320.jpg) / [After](after-79-autofix-320.jpg) | [Before](before-90-execution-320.jpg) / [After](after-90-execution-320.jpg) | [Before](before-90-delivery-320.jpg) / [After](after-90-delivery-320.jpg) | [Before](before-90-autofix-320.jpg) / [After](after-90-autofix-320.jpg) |

Expanded baseline and final report views are also available. [#79 baseline history](before-79-expanded.jpg) · [#90 baseline history](before-90-expanded.jpg) · [#90 expanded execution](execution-evidence-90.jpg) · [#79 baseline report](before-79-report.jpg) / [after](report-79.jpg) · [#90 baseline report](before-90-report.jpg) / [after](report-90.jpg)

## R–T. Live traces, isolated cases and Phase 4 walkthrough

The authenticated walkthrough started at Connected Repositories, opened the repository’s Pull Requests view, then the saved review. It checked the overview and severity distribution, applied and cleared a severity filter, followed a finding permalink, inspected the four specialist results and navigated through execution, delivery and the proposal. Browser Back returned to the original repository under installation `161715271`.

| Verified field | #79 · DhyanMehta/httpx PR #1 | #90 · DhyanMehta/flask-task-api PR #4 |
|---|---|---|
| Reported findings | 16, including 1 high, 4 medium and 11 low | 3, including 1 medium, 1 low and 1 info |
| Filter and permalink | 1 of 16, finding #715 | 1 of 3, advisory #996 with its historical standards citation |
| Specialist outcomes and coverage | Four OK outcomes. Coverage unrecorded for all four. | Four OK outcomes. Four completed executions with complete coverage. |
| Recorded execution | Attempt 1, zero checkpoint events and a heartbeat | Attempt 1, 19 checkpoint events and a heartbeat |
| Delivery and explicit report read | Posted, comment 6020884748, 2723 characters | Posted, comment 7080588921, 2197 characters |
| Proposal | 11 eligible drafts, no recorded proposal | 2 eligible drafts, no recorded proposal |
| Journey ledger | 17 GET attempts, including one report read | 17 GET attempts, including one report read |

The live verification entry mounted the application with the existing session, logged application fetch methods and endpoints, and blocked non-GET requests. Filtering and navigating sections added zero fetches during the local interaction check. Each Markdown retrieval added one report GET. The 34 journey reads include development-mode attempts and repository revalidation on return. The three supplemental proposal inspections recorded 21 further GET attempts. Live workflow writes across these traces were zero. The first finding remained at document y=1138 on the 320 px reference #90 layout with the chooser closed. [#79 validated response](record-79.json) / [journey ledger](journey-79.json) · [#90 validated response](record-90.json) / [journey ledger](journey-90.json)

The following screenshots use clearly labeled synthetic records rendered by the actual components. The isolated harness answered every application fetch locally. Its busy, denied, conflict and uncertain operations had no connection to a real mutation endpoint.

| Fixture group | Evidence |
|---|---|
| Execution | [queued](fixture-queued.jpg) · [running](fixture-running.jpg) · [failed](fixture-failed.jpg) · [skipped](fixture-skipped.jpg) · [attempts](fixture-attempts.jpg) · [missing events](fixture-missing-events.jpg) |
| Delivery | [pending delivery](fixture-pending-delivery.jpg) · [failed delivery](fixture-failed-delivery.jpg) · [missing comment](fixture-missing-comment.jpg) |
| Proposal and decisions | [eligible](fixture-eligible.jpg) · [no eligible fixes](fixture-no-eligible-fixes.jpg) · [creating](fixture-creating.jpg) · [awaiting decision](fixture-awaiting-decision.jpg) · [approved](fixture-approved.jpg) · [rejected](fixture-rejected.jpg) |
| Restrictions and recovery | [stale revision](fixture-stale-revision.jpg) · [unknown revision](fixture-unknown-revision.jpg) · [fork](fixture-fork.jpg) · [permission](fixture-permission.jpg) · [busy](fixture-busy.jpg) · [conflict](fixture-conflict.jpg) · [uncertain](fixture-uncertain.jpg) |

The 22 fixture states had zero horizontal document overflow. [Fixture widths](fixture-viewports.json)

## U–V. Limitations and decision

Historical records can lack checkpoint finish events, branch commit IDs, or delivery metadata. They do not provide a publication timestamp, percent complete or execution duration per stage. Permission, conflict, uncertain-write and actual operation submission behavior were verified with isolated responses. The live session later expired during an optional repeat visit after the authenticated walkthroughs and proposal captures were complete. The final unknown-revision wording was checked separately against the backend implementation, an isolated browser fixture and automated tests.

**GO for final Phase 4 review.** Phase 5 is eligible for separate approval. Its implementation has not started.
