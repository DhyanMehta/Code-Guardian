# Phase 5 · Analytics dashboard acceptance

**Passed on 26 November 2026.** Both authenticated repositories passed at seven widths. All 24 historical records matched their metrics responses. The two final repository-to-review walkthroughs recorded 32 application GET attempts and zero writes.

[Desktop overview](evidence/overview-desktop.jpg) · [Severity and weighted findings](evidence/severity-and-index.jpg) · [320px history record](evidence/history-mobile.jpg)

## A. Git baseline and preservation

Work continued on `codex/durable-review-pipeline` at `dc9b6af4149764ae66e2ca10974c151a6bf819a0`, one commit ahead of its tracking branch. The last commit was “Verify GitHub installation access updates on return”. The index was empty. Phases 1–4 existed as tracked edits and untracked source, tests, plans and evidence in the same worktree. There was no newer frontend checkpoint. Both live response snapshots and the fourteen original screenshots were captured before editing product source. Existing work stayed in place.

## B. Phase 5 files

| File | Change |
|---|---|
| `frontend/src/components/dashboard/AnalyticsTab.tsx` | Scoped refresh, primary metrics, outcomes, execution evidence, severity distribution and auto-fix decisions |
| `frontend/src/components/dashboard/WeightedFindings.tsx` | Review-sequence plot, observation eligibility, axes, legend and exact-values link |
| `frontend/src/components/dashboard/AnalyticsHistory.tsx` | Responsive table, creation times, limitations and canonical review links |
| `frontend/src/test/analytics.test.tsx` | Analytics contract, rendering, navigation, refresh, failure and isolation regressions |
| `frontend/src/test/repositoryNavigation.test.tsx` | Two existing navigation assertions now use the new chart heading |
| `tasks/todo.md`, `UI_REGRESSION_CHECKLIST.md` | Phase 5 verification status |
| `docs/frontend-phase-5/README.md` and [evidence](evidence/) | This report, original and final live captures, sanitized request traces, measurements, response comparisons and labeled fixtures |

The temporary local verification entries were removed after collection. Product entry points, dependency manifests, backend and API contracts received no edits.

## C. Previous architecture

The repository route owned authorization and the Analytics tab subscribed to one metrics resource. Nine equal cards mixed analysis outcomes, availability of evidence and auto-fix decisions. The original view put severity in a chip strip, gave even a zero a positive bar height, and relied on hover for individual index values in the plot. The table paired findings and index in one cell and displayed the raw creation timestamp. Refresh was a 12px text button with an approximately 16px target height.

## D. Dashboard architecture

The same tab owns the same resource. Four static StatCards lead into analysis outcomes and execution coverage. The severity distribution and historical plot share a row on wide screens. Auto-fix decisions and individual review records follow. The plot and history consume the validated response as props. All breakpoints share a single history DOM and resource subscription.

## E–F. Metric sources, scope and denominators

The frontend calls `GET /metrics/trends?installation_id=ID&repo=OWNER%2FREPO&limit=50`. The authorized metrics route delegates to `backend/services/metrics_service.py`. The service selects the newest records by creation time and ID, applies the limit, then reverses the sample into oldest-first order. The UI preserves that order, including ties. The limit describes the current dashboard request.

| Display | Response or calculation |
|---|---|
| Sample size, limit | `range.review_count`, `range.requested_limit` |
| Review and terminal counts | `totals.reviews/completed/failed/skipped` |
| Queued and running | Count `points[].status` equal to `pending` or `running` respectively |
| Reported occurrences | `totals.findings` from persisted review findings. An issue reported in multiple reviews can contribute multiple times |
| Severity bars | Each of the six validated `totals.severity_counts` values, independent of the reported total |
| Coverage and limitations | Service coverage totals, point-level coverage flags and recorded agent lists as described below |
| Index and weights | Server-provided `points[].weighted_index` and `totals.weights_used` |
| Auto-fix activity and decisions | `totals.autofix.created/approved/rejected` |
| Historical record | `review_id`, `pr_number`, `created_at`, `status`, `total_findings`, index and evidence fields from that point |

The denominator for outcomes and coverage availability is sampled **review records**. A PR can have multiple reviews. The screen makes no all-time or unique-defect claim.

## G. Review outcomes

Completed, failed, skipped, queued and running each have an exact count. Completed is an analysis status. Separate coverage fields determine what execution evidence exists. The current parser accepts five statuses. An unfamiliar status or missing severity bucket produces a contract error and recovery control.

## H. Coverage truthfulness matrix

| Display | Evidence required |
|---|---|
| Full execution coverage records | All four specialists have recognized recorded outcomes and the service has four coverage records |
| Confirmed complete | Full records, all coverage statuses complete or not applicable, and no degraded or failed specialist |
| Full records, coverage limited | `coverage_recorded && !coverage_complete`. The aggregate cannot identify whether the cause is partial coverage, another limited status or degradation alone |
| Missing full records | Sample count less the count with full records. Some specialist evidence can still exist |
| Degraded or failed specialist outcome | At least one name in `degraded_agents`. Each affected review is counted once here |
| All reviews without confirmed complete coverage | `reviews_with_coverage_gap`, the inclusive count of records lacking confirmed completeness |
| Unrecorded specialists in history | `unrecorded_agents` lists missing recognized **outcomes**. A missing coverage record alone does not identify a failed specialist |

These counts overlap. For example, httpx has 10 reviews missing full records, including 7 with a recorded degraded or failed specialist.

## I. Severity distribution

Six written labels, specialist-independent severity icons, exact counts and horizontal bars expose critical through unknown. The largest bucket defines the printed scale. A real zero occupies zero bar width. An empty or all-zero sample uses explicit zero-count wording. Severity bars do not include raw scanner detections. The reported total remains independent even if the buckets and total differ.

## J. Weighted findings

The service sums persisted finding occurrences by severity for each record. Current weights are critical 10, high 5, medium 2, low 1, info 0 and unknown 0. Every stored review has a server index. The frontend uses that index directly and displays the supplied weights.

Each horizontal slot is one review in creation order. Completed observations use their exact index, including zero on the baseline. Filled circles indicate complete coverage. Open squares qualify observations with limited evidence. A failed review with persisted findings can still contribute a qualified observation. Failed reviews without findings, skipped records and active records retain their sequence positions without a plotted value. The table preserves their server index and states when no observation was plotted. A declining index can reflect differences in reviewed files, findings or coverage.

The numeric axis, written legend, endpoint review IDs and keyboard-accessible exact values support inspection without hover. The plot uses CSS geometry and has no animation or new dependency. The final seven-width pass verified all three tick labels stayed on one line.

## K. Auto-fix activity

Activity counts reviews with any non-null saved auto-fix status, including intermediate states and failure. Approved and rejected count the corresponding stored decisions. The UI reports these three values separately. Branch creation, retries, merges and deployments cannot be determined from these counts.

## L–M. History, timestamps and freshness

The full sample is one table with column and row headers. Below the large desktop breakpoint, the same records become labeled blocks. Each record exposes its review, PR, created time, analysis outcome, finding count, exact index and coverage limitations. A native link opens the canonical saved review. FriendlyTimestamp displays a localized creation time with a UTC offset and a keyboard-operable disclosure of the original timestamp. Missing times show “Time unavailable”. Ambiguous or malformed input remains inspectable without assigning it a timezone.

One ScopedRefreshStatus describes the client fetch for Analytics. Explicit refresh reads the current installation and repository. The existing `scope:trends` cache key, 30-second policy, cancellation, access-loss handling, offline behavior, retries and backoff remain in the shared resource layer.

## N. Authenticated data comparison

The local application recovered the manually authenticated account through its existing session check. **GET /auth/me returned HTTP 200** for installation 161715271's authenticated user. Each repository's decoded original and final metrics documents matched in full. Comparison against the rendered DOM checked 23 named summary values per repository, six weights, each history record and every plotted position. [Comparison](evidence/comparison.json) · [httpx rendered values](evidence/live-httpx-display.json) · [flask-task-api rendered values](evidence/live-flask-task-api-display.json)

| Verified metric | DhyanMehta/httpx | DhyanMehta/flask-task-api |
|---|---:|---:|
| Reviews | 10 | 14 |
| Completed / failed / skipped | 9 / 0 / 1 | 14 / 0 / 0 |
| Queued / running | 0 / 0 | 0 / 0 |
| Reported occurrences | 145 | 127 |
| Critical / high / medium / low / info / unknown | 0 / 9 / 30 / 106 / 0 / 0 | 8 / 40 / 25 / 28 / 26 / 0 |
| Full records / confirmed complete | 0 / 0 | 1 / 1 |
| Full records with limited coverage / missing full records | 0 / 10 | 0 / 13 |
| Reviews with degraded or failed specialist / inclusive coverage gaps | 7 / 10 | 5 / 13 |
| Auto-fix activity / approved / rejected | 1 / 0 / 0 | 2 / 1 / 0 |
| Historical records / plotted observations | 10 / 9 | 14 / 14 |

Skipped httpx review #65 has a stored index of 0 and a gap in the plot. Completed flask-task-api review #72 has 0 reported findings and appears at zero with a limited-evidence marker. Review #79 has 16 findings and index 24. Review #90 has 3 findings, index 3 and confirmed complete coverage. [Original httpx](evidence/before-httpx-response.json) · [Final httpx](evidence/after-httpx-response.json) · [Original flask-task-api](evidence/before-flask-task-api-response.json) · [Final flask-task-api](evidence/after-flask-task-api-response.json)

## O. Responsive measurements

Rounded CSS pixels from the httpx dashboard. The KPI start is the first card's distance from the document top at initial load. Overview height covers the entire KPI grid. All seven widths had zero excess document width and zero horizontal cell overflow in the redesigned history for both repositories.

| Width | KPI start before → after | Overview height before → after | New first card W×H | New plot W×H | New first history row W×H |
|---:|---:|---:|---:|---:|---:|
| 1920 | 370 → 350 | 329 → 138 | 299×138 | 648×192 | 1231×133 |
| 1440 | 370 → 350 | 329 → 138 | 299×138 | 648×192 | 1231×133 |
| 1024 | 366 → 346 | 329 → 178 | 234×178 | 491×192 | 970×133 |
| 768 | 406 → 386 | 329 → 289 | 351×138 | 633×192 | 714×327 |
| 700 | 462 → 442 | 317 → 281 | 317×134 | 565×192 | 646×331 |
| 390 | 562 → 550 | 496 → 542 | 353×126 | 279×160 | 353×385 |
| 320 | 562 → 550 | 556 → 562 | 282×126 | 209×160 | 282×393 |

At 320px, the longer flask-task-api repository name adds 32px above Analytics. The mobile cards take more vertical space to keep field labels, creation times and execution limitations readable. The chart previously used a 144px-high strip without numeric axes. [Original httpx layout](evidence/before-httpx-layout.json) · [Final httpx layout](evidence/after-httpx-layout.json) · [Original flask-task-api layout](evidence/before-flask-task-api-layout.json) · [Final flask-task-api layout](evidence/after-flask-task-api-layout.json) · [All final viewport, axis and target measurements](evidence/final-responsive-checks.json)

## P. Accessibility verification

At 320px the review links measured approximately 87×44px, the refresh button was 44px tall and the first timestamp disclosure was 52px tall. Both saved reviews opened at that width without horizontal scrolling. The plot's exact-values link leads to the history heading. Tab from a timestamp disclosure placed keyboard focus on its View review link. In the measured desktop environment it had a solid 1.6 CSS-pixel computed outline and matched `:focus-visible`. Refresh kept focus on the existing link in the integration test. Routine successful polling uses ordinary text.

The chart axes use 14px type, the explanatory caption and history values 15px. The shared metric label uses 13px on desktop and 14px on phones. Computed colors on the panel background give contrast ratios of 16.22:1 for primary text, 8.81:1 for muted text, 8.91:1 for link/focus and 14.27:1 for the limited-evidence marker. Status labels, shape and text accompany color. [Computed styles](evidence/desktop-accessibility.json) · [Focused link](evidence/httpx-focused-review.jpg) · [Exact source time](evidence/httpx-exact-time.jpg)

## Q–S. Automated verification

| Gate | Result |
|---|---|
| Focused Vitest suites | 147 passed in 15 files |
| Full `npm test` | 251 passed in 33 files |
| `npm run build` | TypeScript and Vite production build passed |
| `git diff --check` | Passed |

Focused coverage included analytics, readFlows, reliabilityFlows, repositoryNavigation, polling, identity, StatCard, SeverityBadge, FriendlyTimestamp, ScopedRefreshStatus, reviewWorkspace, findingsEvidence, reviewOperations, writeFlows and finalFlow. Nine dedicated analytics cases cover data interpretation, chart geometry, single/empty samples, malformed contracts, navigation without writes, delayed old-scope responses, access loss, staleness and offline handling. Existing navigation, review and mutation suites exercised their normal contracts against isolated responses.

## T. Authenticated visual evidence

Each link opens a full-page screenshot of the named repository and width. The original and final captures used the same installation, data and viewport dimensions.

| Width | httpx | flask-task-api |
|---:|---|---|
| 1920 | [Before](evidence/before-httpx-1920.jpg) · [After](evidence/after-httpx-1920.jpg) | [Before](evidence/before-flask-task-api-1920.jpg) · [After](evidence/after-flask-task-api-1920.jpg) |
| 1440 | [Before](evidence/before-httpx-1440.jpg) · [After](evidence/after-httpx-1440.jpg) | [Before](evidence/before-flask-task-api-1440.jpg) · [After](evidence/after-flask-task-api-1440.jpg) |
| 1024 | [Before](evidence/before-httpx-1024.jpg) · [After](evidence/after-httpx-1024.jpg) | [Before](evidence/before-flask-task-api-1024.jpg) · [After](evidence/after-flask-task-api-1024.jpg) |
| 768 | [Before](evidence/before-httpx-768.jpg) · [After](evidence/after-httpx-768.jpg) | [Before](evidence/before-flask-task-api-768.jpg) · [After](evidence/after-flask-task-api-768.jpg) |
| 700 | [Before](evidence/before-httpx-700.jpg) · [After](evidence/after-httpx-700.jpg) | [Before](evidence/before-flask-task-api-700.jpg) · [After](evidence/after-flask-task-api-700.jpg) |
| 390 | [Before](evidence/before-httpx-390.jpg) · [After](evidence/after-httpx-390.jpg) | [Before](evidence/before-flask-task-api-390.jpg) · [After](evidence/after-flask-task-api-390.jpg) |
| 320 | [Before](evidence/before-httpx-320.jpg) · [After](evidence/after-httpx-320.jpg) | [Before](evidence/before-flask-task-api-320.jpg) · [After](evidence/after-flask-task-api-320.jpg) |

[Outcome and coverage overview](evidence/overview-desktop.jpg) · [Severity and weighted chart](evidence/severity-and-index.jpg) · [Auto-fix and desktop history](evidence/activity-and-history.jpg) · [Mobile history](evidence/history-mobile.jpg) · [Refresh disclosure](evidence/httpx-freshness.jpg)

## U. Live read-only traces

Both final journeys started at Connected Repositories, opened the named repository and selected Analytics. Each explicit refresh added one scoped metrics GET. Opening exact values, disclosing a creation timestamp and focusing the saved review link added zero requests. Review details loaded on intentional navigation. Browser Back restored the installation, repository, Analytics tab and history anchor. Pull Requests, Agent History and Installation Settings remained reachable.

| Repository | Saved destination | App GET attempts, including cancellations | Workflow writes | Settled Back result |
|---|---|---:|---:|---|
| httpx | #79 · PR #1 | 16 | 0 | Scoped metrics 200 |
| flask-task-api | #90 · PR #4 | 16 | 0 | Scoped metrics 200 |

The local verification entry instrumented application fetch before normal React startup, rejected non-GET methods and retained only method, endpoint, status and the authorized metrics response. No review-trigger or auto-fix write was attempted. Counts include development remount cancellations and exclude static Vite assets. The totals above apply to the two final walkthroughs. [httpx stages](evidence/journey-httpx.json) · [httpx settled return](evidence/returned-httpx.json) · [flask-task-api stages](evidence/journey-flask-task-api.json) · [flask-task-api settled return](evidence/returned-flask-task-api.json) · [Additional destinations](evidence/additional-destinations.json)

[Review #79](evidence/httpx-saved-review.jpg) · [Back to httpx](evidence/httpx-browser-back.jpg) · [Review #90](evidence/flask-task-api-saved-review.jpg) · [Back to flask-task-api](evidence/flask-task-api-browser-back.jpg)

## V. Isolated evidence

A separate local fixture rendered the actual Analytics tab with in-memory responses. Its screenshots carry an “Isolated fixture” heading. The mixed sample exercised repeated dates, an ambiguous/malformed timestamp, long specialist metadata, active/terminal states, recorded limited and complete coverage, degraded outcomes, overlapping limitations, unavailable observations and baseline zero. Separate captures cover empty, one-point/all-zero, loading, forbidden, malformed-contract, offline and stale-cache states. The delayed previous-scope response was verified with a controlled promise in the dedicated integration test.

[Mixed outcomes and evidence](evidence/fixture-mixed.jpg) · [Empty](evidence/fixture-empty.jpg) · [One point](evidence/fixture-one.jpg) · [Loading](evidence/fixture-loading.jpg) · [Permission denied](evidence/fixture-denied.jpg) · [Invalid contract](evidence/fixture-malformed.jpg) · [Offline](evidence/fixture-offline.jpg) · [Cached read failure](evidence/fixture-cached-error.jpg)

## W–X. Limitations and recommendation

**GO for Phase 6 planning and separate approval.** The two live repositories had no queued, running or failed analysis and no fully recorded but limited review. Isolated fixtures supplied those states. GET traces measure application requests in this browser. Accessibility evidence covers keyboard, semantic structure, computed colors, geometry and responsive layout. A screen-reader or cross-browser certification audit remains outside this evidence.

Verification note: an early local evidence-inspection command used the system Python interpreter. The final response-to-DOM comparison was rerun with the verified project virtual environment. No Python packages were installed. Phase 6 implementation is pending separate authorization.
