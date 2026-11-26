# Phase 6 · Agent History acceptance

**Passed on 26 November 2026.** Both repositories passed authenticated verification at seven widths. All eight specialist summaries and all ten initial history rows matched the saved responses. The final walkthroughs recorded 80 application GET attempts and zero writes.

[Desktop Agent History](evidence/after-httpx-1440.jpg) · [Recorded Quality issue](evidence/httpx-quality-issue.jpg) · [Missing coverage on #79](evidence/httpx-expanded.jpg) · [Complete coverage on #90](evidence/flask-task-api-expanded.jpg)

## A. Git baseline and checkpoint

The active branch was `codex/durable-review-pipeline` at `dc9b6af4149764ae66e2ca10974c151a6bf819a0`, one commit ahead of its tracking branch, with an empty index. Earlier milestones and evidence were present as tracked edits and untracked work. No newer checkpoint existed. Original live screenshots and response summaries for both repositories were captured before editing product code.

Both local services were stopped at entry. Vite was restored on IPv4 loopback and FastAPI was started from the existing virtual environment. The browser used its established localhost origin and authenticated as DhyanMehta. The baseline instrumented `GET /auth/me` returned 200. The verification used the existing read services with the review worker and tunnel stopped.

## B. Phase 6 files

| Path | Contribution |
|---|---|
| `frontend/src/components/dashboard/AgentsTab.tsx` | Historical scope, bounded detail coordinator, progress, retention, refresh, retry and continuation |
| `frontend/src/components/dashboard/AgentOutcomeChart.tsx` | Four text-first specialist summaries and latest-issue links |
| `frontend/src/components/dashboard/AgentHistoryRecord.tsx` | Compact historical cards, field disclosures and scanner provenance |
| `frontend/src/components/dashboard/specialistEvidence.ts` | Shared specialist outcome and issue interpretation |
| `frontend/src/test/agentHistory.test.tsx` | Nine regressions for evidence, failures, isolation, focus and request boundaries |
| `frontend/src/test/finalFlow.test.tsx`, `frontend/src/test/readFlows.test.tsx`, `frontend/src/test/repositoryNavigation.test.tsx` | Existing behavioral assertions in the new presentation |
| `tasks/todo.md`, `UI_REGRESSION_CHECKLIST.md` | Verified milestone status |
| `docs/frontend-phase-6/README.md`, `docs/frontend-phase-6/evidence/` | Report, screenshots, response summaries, measurements and traces |

Two temporary verification entries were removed after capture. The final diff is restricted to the frontend Agent History view, its tests and milestone evidence. The worktree remained uncommitted.

## C. Previous architecture

The repository page authorized access before mounting `AgentsTab`. Agent Fleet placed four full-width outcome distributions above another four issue panels. Every review rendered a grid of specialist result cards on entry. The existing scope and authorized detail data were already sufficient for a historical workspace. The original labels were 11–14px in the outcome area and the 16px-tall refresh control had no padded target.

## D. Redesigned workspace

The repository selector and `tab=agents` route lead to Agent History. One historical sample summary precedes four specialist summaries with issue links, then collapsed execution history. The source-specific refresh disclosure and padded refresh button share the header. Each record gives its review identity, PR, creation time, analysis status, accepted finding total, coverage availability and specialist outcomes before any disclosure opens.

## E–F. Sample and specialist summaries

The API list's total and returned IDs define the sample and records outside it. Completed, skipped and failed review statuses are terminal when the detail is loaded. Queued and running are active. A detail read failure is unavailable and can retain permitted list metadata. Active and unavailable records stay outside the denominator. Pending work has a review-list phase followed by the count of saved details checked. Continuation keeps the previous sample visible while the next bounded read completes.

Security, Quality, Test Gaps and Documentation each use the loaded terminal denominator. Labels and exact counts cover OK, degraded, failed and unrecorded. Missing or unknown outcomes contribute to the unrecorded bucket. Expanded records distinguish an explicit unknown outcome from an absent record. Coverage limitations are counted separately and can coincide with any outcome.

## G. Outcome, execution and coverage

| Field | Source and meaning |
|---|---|
| Analysis status | `ReviewDetail.status`, the saved review-level status |
| Specialist outcome | Recognized `agent_runs[].outcome` when `recorded` is true |
| Execution | `agent_runs[].coverage.execution` when a coverage record exists |
| Coverage | `agent_runs[].coverage.status`, including complete, partial, not applicable or unknown |
| Coverage availability | Number of specialists whose coverage data is present on that review |
| Accepted findings | `finding_count` for the review and `agent_counts` for each specialist |
| Draft enrichment | Independently recorded enrichment status and target counts where present |
| Scanner observations | Recorded scanner status, per-scanner raw counts and saved raw evidence provenance |

Some historical reviews have OK outcomes with no recorded execution or coverage. Some terminal rows contain partial coverage, independent of their outcome. All counts refer to saved records.

## H. Recorded issue investigation

The first matching review in the server's newest-first order is selected from available detail records. A partial coverage result, degraded outcome or failed outcome qualifies. The summary gives the recorded outcome and limitation, a preview of the sanitized reason when provided, the historical review creation time and a canonical Review Detail link. An absent reason is labeled “Reason not recorded”. Review #71 is the latest Quality issue within httpx's five-record sample. Its link opens `/reviews/71#agents`, the existing Agent results section. The full reason is available in the expanded record and the saved Review Detail. [Live issue evidence](evidence/httpx-issue-review.jpg)

## I. Historical review disclosures

Each stable review ID has its own native record disclosure. The inline view shows four specialist outcomes and the material coverage gaps. Expanded fields distinguish outcome, execution, coverage, accepted findings and drafts. The original creation time is available in a separate timestamp disclosure. View review opens the canonical route. Detail failures show the scoped list's review and PR identity, a visible error and the same review destination. The loaded batch retains its order and includes every returned record.

## J. Scanner evidence and accepted findings

The nested scanner disclosure lists recorded engine status, raw detection counts and available rule IDs and severities. It keeps the saved standards version alongside specialist evidence. Existing saved Review Detail remains the destination for full evidence. New surfaces apply `diagnosticText` to diagnostic and scanner strings and display no raw match messages. Review #79 has 16 accepted findings (one Security finding) and one recorded Bandit detection. Semgrep and Gitleaks each recorded zero. The raw detection count does not increase the review total. [Scanner evidence on #79](evidence/httpx-scanners.jpg)

## K. Bounds, concurrency and ownership

Scope and query keys are owned by the repository and existing `useResource` subscription. `GET /reviews?installation_id=ID&repo=OWNER%2FREPO&limit=N&offset=0` supplies the list, with newest-first order by creation time and review ID. The existing strategy uses a prefix of five, raises its limit by five per continuation and stops at 200. It does not advance an offset. The prior plan's five-record initial sample, maximum bound of 200 and two concurrent detail reads match the implementation.

The existing cache reuses matching-status details for 30 seconds for terminal results and five seconds for active results. The historical sample polls every 30 or five seconds using the same conditions. Each detail is fetched at most once per batch unless the existing transport retries. The batch publishes its result together. Neither specialist summaries nor record disclosures subscribe to another resource. During continuation, fresh details remain reusable under the same scope.

## L. Freshness, retry and isolation

ScopedRefreshStatus distinguishes a successful client fetch from saved event times. On refresh the header can show the previous fetch timestamp in the disclosure. Explicit refresh revalidates the list and clears its local detail cache. A partial detail failure leaves visible per-record feedback and a coordinated retry that can reuse still-fresh successful details. A transient list failure preserves the last available sample. Scope changes cancel their previous reads and discard late results, even if the next scope sees the same review ID. Forbidden list reads clear the visible sample and local detail cache. Existing offline, hidden-tab, retry and backoff controls continue to apply. The shared source offers historical execution event times through Review Detail.

## M. Responsive measurements

Rounded CSS pixels for the httpx redesign. Positions are measured from the document top. Specialist sizes are for the Security summary, whose grid row stretches to accommodate the Quality issue on wider views. The table records both history width and collapsed height.

| Viewport | Title top | Sample top / height | First specialist W×H | First history W×H | Refresh target height | Document / client width |
|---:|---:|---:|---:|---:|---:|---:|
| 1920 | 254 | 372 / 126 | 299×454 | 1232×216 | 40 | 1914 / 1914 |
| 1440 | 254 | 372 / 126 | 299×454 | 1232×216 | 40 | 1434 / 1434 |
| 1024 | 250 | 368 / 126 | 479×422 | 970×216 | 40 | 1018 / 1018 |
| 768 | 290 | 456 / 148 | 351×442 | 714×216 | 40 | 762 / 762 |
| 700 | 346 | 516 / 148 | 317×454 | 646×224 | 44 | 694 / 694 |
| 390 | 402 | 594 / 208 | 353×336 | 353×314 | 44 | 385 / 385 |
| 320 | 402 | 616 / 230 | 282×336 | 282×354 | 44 | 314 / 314 |

The full-width baseline at 1440px put its scope panel at roughly 370px and its first outcome strip at roughly 1190×94px, measured from the original screenshot. The baseline measurement script selected an inactive tab panel at desktop widths, so its desktop element geometry was unavailable. The original mobile geometry recorded a 246×130px Security outcome strip and a 288×937px always-expanded first review at 320px. The redesigned summary folds in its issue and coverage information, and the collapsed record fits those review facts into 354px. The longer flask-task-api repository name adds 32px above the history title at 320px. Both repositories had zero excess width at every breakpoint. [Original desktop overview](evidence/before-httpx-desktop-overview.jpg) · [Original httpx measurements](evidence/before-httpx-layout.json) · [Original flask-task-api measurements](evidence/before-flask-task-api-layout.json) · [Final httpx measurements](evidence/after-httpx-layout.json) · [Final flask-task-api measurements](evidence/after-flask-task-api-layout.json)

## N. Accessibility verification

The repository heading, Agent History view, outcome and history sections, and individual specialist and record headings form a consistent hierarchy. Definition lists communicate exact counts and written states. Links identify their review and PR. At 320px, refresh, review links and specialist/scanner disclosures have at least 44px targets. The typography uses 14px metadata, 15px control and support text, and 16px row titles. Text and link tokens on the panel background give approximately 16.22:1 for primary text, 8.81:1 for muted text and 8.91:1 for links and focus.

Keyboard navigation traversed the issue, record timestamp, View review and disclosure targets. Tab from the creation-time summary focused View review with a solid 1.6 CSS-pixel outline. Enter expanded a record locally and activated continuation. Focus remained on the continuation control when its accessible name changed on completion. The retry test confirms focus returns to the history heading when the recovered button disappears. The view uses static counts, written outcomes and ordinary progress text during background refresh. [Focused link](evidence/httpx-focus.jpg) · [Timestamp](evidence/httpx-timestamp.jpg) · [Continuation focus for httpx](evidence/continuation-focus-httpx.json) · [Continuation focus for flask-task-api](evidence/continuation-focus-flask-task-api.json)

## O. Authenticated response-to-UI comparison

The decoded summaries of the original and final initial batches matched for both repositories. Verified fields included specialist outcome and coverage counts, server order, review and PR identities, canonical destinations and the expanded fields and exact timestamps for #79 and #90.

| Initial sample | DhyanMehta/httpx | DhyanMehta/flask-task-api |
|---|---|---|
| Loaded / total | 5 / 10 | 5 / 14 |
| IDs, newest first | 79, 78, 71, 70, 69 | 90, 87, 86, 85, 83 |
| Terminal / active / unavailable | 5 / 0 / 0 | 5 / 0 / 0 |
| Security · OK / degraded / failed / unrecorded | 5 / 0 / 0 / 0 | 5 / 0 / 0 / 0 |
| Quality · OK / degraded / failed / unrecorded | 2 / 3 / 0 / 0 | 5 / 0 / 0 / 0 |
| Test Gaps · OK / degraded / failed / unrecorded | 5 / 0 / 0 / 0 | 5 / 0 / 0 / 0 |
| Documentation · OK / degraded / failed / unrecorded | 5 / 0 / 0 / 0 | 5 / 0 / 0 / 0 |
| Coverage records missing per specialist | 5 | 4 |
| Latest issue in sample | Quality #71, degraded | None recorded |

Review #79 had four OK outcomes with no coverage records. Review #90 had four OK outcomes with recorded completed execution and complete coverage for all four specialists. Both saved reviews loaded at their canonical destinations. [Comparison](evidence/comparison.json) · [httpx baseline](evidence/before-httpx-records.json) · [flask-task-api baseline](evidence/before-flask-task-api-records.json) · [httpx final UI](evidence/displayed-httpx.json) · [flask-task-api final UI](evidence/displayed-flask-task-api.json) · [#79 fields](evidence/review-evidence-79.json) · [#90 fields](evidence/review-evidence-90.json)

## P–R. Tests and build

| Gate | Result |
|---|---|
| Focused frontend suites | 151 passed in 15 files |
| Full frontend suite | 260 passed in 34 files |
| TypeScript and Vite production build | Passed |
| `git diff --check` | Passed |

Focused coverage included agentHistory, AgentHistoryDots, readFlows, reliabilityFlows, repositoryNavigation, polling, identity, finalFlow, analytics, findingsEvidence, reviewWorkspace, reviewOperations, FriendlyTimestamp, ScopedRefreshStatus and writeFlows. The existing concurrency and running-to-terminal cache tests remain intact. New tests cover exact outcomes, latest issue ordering, timestamp and scanner provenance, partial failure, continuation focus, access loss and delayed scope changes.

## S. Authenticated original and final screenshots

The original screenshots are full-page captures. Final files in this table show the initial viewport. The supporting captures below show the content farther down the page.

| Viewport | httpx | flask-task-api |
|---:|---|---|
| 1920 | [Original](evidence/before-httpx-1920.jpg) · [Redesign](evidence/after-httpx-1920.jpg) | [Original](evidence/before-flask-task-api-1920.jpg) · [Redesign](evidence/after-flask-task-api-1920.jpg) |
| 1440 | [Original](evidence/before-httpx-1440.jpg) · [Redesign](evidence/after-httpx-1440.jpg) | [Original](evidence/before-flask-task-api-1440.jpg) · [Redesign](evidence/after-flask-task-api-1440.jpg) |
| 1024 | [Original](evidence/before-httpx-1024.jpg) · [Redesign](evidence/after-httpx-1024.jpg) | [Original](evidence/before-flask-task-api-1024.jpg) · [Redesign](evidence/after-flask-task-api-1024.jpg) |
| 768 | [Original](evidence/before-httpx-768.jpg) · [Redesign](evidence/after-httpx-768.jpg) | [Original](evidence/before-flask-task-api-768.jpg) · [Redesign](evidence/after-flask-task-api-768.jpg) |
| 700 | [Original](evidence/before-httpx-700.jpg) · [Redesign](evidence/after-httpx-700.jpg) | [Original](evidence/before-flask-task-api-700.jpg) · [Redesign](evidence/after-flask-task-api-700.jpg) |
| 390 | [Original](evidence/before-httpx-390.jpg) · [Redesign](evidence/after-httpx-390.jpg) | [Original](evidence/before-flask-task-api-390.jpg) · [Redesign](evidence/after-flask-task-api-390.jpg) |
| 320 | [Original](evidence/before-httpx-320.jpg) · [Redesign](evidence/after-httpx-320.jpg) | [Original](evidence/before-flask-task-api-320.jpg) · [Redesign](evidence/after-flask-task-api-320.jpg) |

[Mobile review #79](evidence/httpx-expanded.jpg) · [Mobile review #90](evidence/flask-task-api-expanded.jpg) · [Scanner evidence](evidence/httpx-scanners.jpg) · [Issue link](evidence/httpx-quality-issue.jpg) · [Issue destination](evidence/httpx-issue-review.jpg) · [Back to httpx](evidence/httpx-back.jpg) · [Back to flask-task-api](evidence/flask-task-api-back.jpg) · [Load older httpx reviews](evidence/httpx-continuation.jpg) · [Load older flask-task-api reviews](evidence/flask-task-api-continuation.jpg)

## T. Live read-only request traces

The verification entry blocked any non-GET fetch before normal app startup. The two walkthroughs used Connected Repositories, the repo chooser, Agent History, local disclosures and canonical review links. They returned via Browser Back to the same installation, repository and view. Explicit refresh and continuation were performed after returning. Httpx continued to 10 of 10, and flask-task-api continued to 10 of 14.

| Stage | httpx | flask-task-api |
|---|---:|---:|
| Initial successful scoped history request | 1 | 1 |
| Initial successful detail reads | 5 | 5 |
| Max observed in-flight detail requests | 2 | 2 |
| Detail disclosure reads | 0 | 0 |
| Additional GET attempts on intentional review navigation | 4 to #71 and 4 to #79 | 4 to #90 |
| Explicit refresh | 1 list + 5 details | 1 list + 5 details |
| Continue to limit 10 | 1 list + 5 newly needed details | 1 list + 5 newly needed details |
| Total application GET attempts in walkthrough | 43 | 37 |
| Workflow writes | 0 | 0 |

Intentional navigation includes existing head lookups and development mount cancellations. Total attempts include shell and PR reads, cancellations and post-navigation revalidation. Static assets are outside the ledger. [httpx original trace](evidence/before-httpx-requests.json) · [flask-task-api original trace](evidence/before-flask-task-api-requests.json) · [httpx walkthrough](evidence/journey-httpx.json) · [flask-task-api walkthrough](evidence/journey-flask-task-api.json) · [httpx continuation response](evidence/continued-httpx-records.json) · [flask-task-api continuation response](evidence/continued-flask-task-api-records.json)

## U. Isolated fixtures

The labeled fixtures used the production Agent History components with isolated read responses. Mixed evidence covered missing and unknown outcomes, failed specialists, previous partial coverage, overlapping limitations, complete coverage and long diagnostic text. The browser also exercised empty, active-only, loading, offline, permission denial and partial read failure states. Controlled integration tests exercised transient stale data and an old-scope detail resolving after cancellation.

[Mixed outcomes](evidence/fixture-mixed.jpg) · [Complete execution evidence](evidence/fixture-complete-details.jpg) · [Empty](evidence/fixture-empty.jpg) · [Active only](evidence/fixture-active.jpg) · [Loading](evidence/fixture-loading.jpg) · [Offline](evidence/fixture-offline.jpg) · [Forbidden](evidence/fixture-denied.jpg) · [Detail unavailable](evidence/fixture-partial-read.jpg)

## V–W. Limitations and recommendation

**GO for Phase 7 review and separate approval.** The live initial samples contained completed review records and successfully loaded details. Exceptional states were verified with isolated fixtures. The original desktop element measurements had the selector limitation documented above. Accessibility verification covers browser semantics, keyboard, responsive geometry and the cited contrast pairs. Platform screen-reader and cross-browser audits are outside these measurements. Phase 7 implementation is pending separate authorization.
