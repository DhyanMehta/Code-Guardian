# Phase 4a · Review detail, summary and navigation

**Verified on 25 November 2026.** Both saved reviews opened from their repository workspaces. Review #79 displayed 16 findings and missing historical coverage. Review #90 displayed three findings and four complete coverage records. The authenticated journey recorded 26 application GET requests and zero writes. [Read-only trace and response fields](read-only-trace.txt)

## A. Git baseline and preservation

The working branch was `codex/durable-review-pipeline`. HEAD was `dc9b6af4149764ae66e2ca10974c151a6bf819a0`, one commit ahead of its remote tracking branch. The index was empty. The earlier milestones existed as unstaged changes and untracked components, tests, documents and captures. The Phase 3c report identifies the same HEAD. A separate Phase 1–3 Git checkpoint report or SHA could not be found in this checkout. The October post-checkpoint report concerns an earlier backend milestone. The before captures therefore use the actual working tree that contained Phase 3c. [Phase 3c handoff](../frontend-phase-3c/README.md)

Vite and FastAPI initially refused local connections. Restoring those two read services made the existing signed-in session available. Verification used the existing installation and saved records. The worker and public tunnel stayed stopped.

## B. Files changed in this milestone

| Area | Files |
|---|---|
| Composition and presentation | `frontend/src/pages/ReviewDetailPage.tsx`, `frontend/src/components/reviews/ReviewOverview.tsx`, `frontend/src/index.css` |
| Shared head read and checkpoint times | `frontend/src/components/reviews/AutofixActions.tsx`, `frontend/src/components/reviews/AgentTimeline.tsx` |
| Regression coverage | `frontend/src/test/reviewWorkspace.test.tsx`, `frontend/src/test/readFlows.test.tsx`, `frontend/src/test/reliabilityFlows.test.tsx`, `frontend/src/test/writeFlows.test.tsx`, `frontend/src/test/finalFlow.test.tsx` |
| Handoff | `tasks/todo.md`, `UI_REGRESSION_CHECKLIST.md`, this report and the measurement, trace and image files indexed below |

## C–E. Composition, identity and navigation

Previously, refresh and its fetch timestamp preceded the repository return link. The banner put the full SHA and raw execution timestamps alongside analysis status, recorded prose and coverage. Severity counts followed the banner. Finding filters came next in keyboard order. Reaching agents, delivery or fix decisions required traversing the page. [Previous desktop view](before-1440.jpg)

The review heading now identifies the saved record, repository and PR. The heading receives focus on ordinary entry. A direct fragment visit opens the addressed finding after the asynchronous record loads. The parent link uses the installation and repository in the review response. The legacy PR resolver still resolves a real review ID. The detail contract supplies the PR number without a title, so the header makes no title lookup.

The header shows the analysis state and a short reviewed revision with a keyboard-operable disclosure for the full value. The existing scoped head lookup serves both the summary and auto-fix guards through a single subscription. Revision labels distinguish a match, a changed head, an unavailable current head, an absent reviewed SHA and a comparison using last-loaded data.

The **Review sections** landmark links to the overview, findings, agent results, execution, GitHub delivery and applicable auto-fix decisions. The links wrap on phones and retain native fragment and Back behavior. During queued or running analysis, the page shows progress first and offers execution details while final results are pending. [Keyboard focus](focused-section-link.jpg) · [Scoped PR list after Browser Back](browser-back.jpg)

## F–G. Analysis, severity and coverage

| Observed response | Review #79 | Review #90 |
|---|---|---|
| Repository and PR | DhyanMehta/httpx · #1 | DhyanMehta/flask-task-api · #4 |
| Reviewed revision, abbreviated | `5b2630b1d2b7` | `719a766b9edd` |
| Analysis / GitHub delivery | Completed / posted | Completed / posted |
| Reported findings | 16 | 3 |
| Critical / high / medium / low / info / unknown | 0 / 1 / 4 / 11 / 0 / 0 | 0 / 0 / 1 / 1 / 1 / 0 |
| Specialist outcomes | Four recorded OK | Four recorded OK |
| Execution coverage | All four coverage records absent | All four complete, with completed execution |

The definition list pairs each persisted severity bucket with its count, including zero. The total comes from the review response independently of filtering. The response validator rejects a malformed or missing bucket. The overview displays agent-level partial, unknown, inapplicable or missing coverage and degraded or failed outcomes where present. Failed and skipped analysis reasons stay visible. Delivery status has its own field and its own evidence section. [Historical coverage](after-1440.jpg) · [Review #90 before](before-review-90.jpg) · [Review #90 after](recorded-coverage-90.jpg)

## H–I. Time, freshness and detailed evidence

Review creation, start, completion, heartbeat, recorded agent checkpoint and approval times use the event timestamp treatment. The native disclosure preserves the source string, including fractional seconds and offset. Review fetch time belongs to the scoped refresh control. Cached results carry a visible warning after a transient failure. A denied read withholds the evidence. [Exact execution timestamp](execution-exact-time.jpg)

Findings retain their filters, evidence, draft previews and stable IDs. Per-agent cards retain execution data, outcomes, scanner details and raw evidence. The timeline retains its attempt and stage logic. The saved report loads on explicit request. The GitHub comment, branch links, skipped-fix reasons and human decision controls remain available under the existing eligibility rules. Mutation ownership stays in the existing auto-fix component. [Findings](findings.jpg) · [Agent evidence](agent-evidence.jpg) · [Execution](execution.jpg) · [Delivery](github-delivery.jpg) · [Auto-fix](auto-fix.jpg)

## J and O. Responsive measurements and authenticated captures

Measurements are rounded CSS pixels for the same review #79 at initial entry. Widths in the first column are the requested viewport settings. The browser content width excludes its gutter. Header height covers the review identity region. The summary size is the redesigned evidence panel. The two evidence Y values locate the former analysis status and the new findings-total heading respectively. The first-finding column compares the same disclosure in both versions.

| Requested width | Available / document width, after | Header height, before → after | Summary width × height, after | Evidence Y, before → after | First finding Y, before → after | Authenticated captures |
|---:|---:|---:|---:|---:|---:|---|
| 1920 | 1914 / 1914 | 248 → 177 | 1232 × 205 | 336 → 302 | 734 → 780 | [Before](before-1920.jpg) · [After](after-1920.jpg) |
| 1440 | 1434 / 1434 | 248 → 177 | 1232 × 205 | 336 → 302 | 734 → 780 | [Before](before-1440.jpg) · [After](after-1440.jpg) |
| 1024 | 1018 / 1018 | 248 → 177 | 970 × 205 | 332 → 298 | 730 → 776 | [Before](before-1024.jpg) · [After](after-1024.jpg) |
| 768 | 762 / 762 | 276 → 177 | 714 × 342 | 328 → 294 | 754 → 949 | [Before](before-768.jpg) · [After](after-768.jpg) |
| 700 | 694 / 694 | 292 → 181 | 646 × 346 | 328 → 298 | 844 → 1038 | [Before](before-700.jpg) · [After](after-700.jpg) |
| 390 | 385 / 385 | 371 → 231 | 353 × 401 | 388 → 344 | 997 → 1288 | [Before](before-390.jpg) · [After](after-390.jpg) |
| 320 | 314 / 314 | 403 → 231 | 282 × 401 | 388 → 344 | 1061 → 1332 | [Before](before-320.jpg) · [After](after-320.jpg) |

The narrower layouts bring the saved identity and limitations forward. The stacked summary, larger controls and section links place the first individual finding farther down. At 320 px the Findings jump bypasses that extra scrolling. Available and document widths matched at all seven settings. [Baseline geometry](before-measurements.json) · [Final geometry](after-measurements.json) · [Phone findings](phone-findings.jpg)

## K. Accessibility verification

Keyboard inspection found a visible outline on the section links. Ordinary entry focused the H1 with the page at the top. The native summary exposed the exact execution-start value. Direct navigation to `/reviews/79#finding-715` opened the addressed disclosure below the header. A regression test checks that refresh failure preserves focus on the refresh control.

Refresh measured 101 × 16 px before, 132 × 40 px at desktop widths after, and 132 × 44 px below 768. At 320 px the return link, revision disclosure, section links and finding filters each measured at least 44 px tall. Calculated token contrast ratios were 16.22:1 for foreground on panel, 8.81:1 for muted text on panel, 9.75:1 for links on canvas, and 8.69:1 for high-severity text on its badge. Physical touch and screen-reader speech were outside this verification. [Phone control measurements](phone-controls.json) · [Direct finding fragment](direct-finding-fragment.jpg)

## L–N. Automated verification

| Gate | Result |
|---|---|
| Focused suites | **138 passed in 14 files**. Review workspace, read flows, reliability, final flow, progress, polling, identity, repository navigation, PR workspace, write flows, friendly timestamps, scoped refresh, severity badges and shared feedback. |
| Full frontend suite | **215 passed in 30 files** using `npm test`. |
| Production build | **Passed** using `npm run build` (TypeScript and Vite). |
| Whitespace | **Passed** using `git diff --check`. |

The 13 new workspace tests cover local section targets, a single shared head read, explicit report retrieval, read-only requests, active and terminal states, coverage distinctions, missing severity data, revision labels, original timestamps, asynchronous fragment entry, denied access, and cached refresh failure. Existing suites cover polling, route resolution, scope isolation and auto-fix guards with isolated writes.

## P. Live request trace

The signed-in journey followed Connected Repositories → httpx → Pull Requests → View Review → #79. It visited evidence sections, retrieved the saved report, used Browser Back to return to the same installation, then opened flask-task-api → #90. A temporary verification wrapper recorded application fetch attempts and blocked non-GET methods before dispatch. Its ledger includes repeated development reads. It recorded **26 GET attempts, zero attempted writes and one explicit report retrieval**. The saved response excerpts include the complete SHAs and all six severity counts. [Request trace](read-only-trace.txt)

## Q. Isolated exceptional-state evidence

These captures use labeled local fixtures and mocked reads. They exercise conditions outside the two live completed reviews.

| Fixture | Desktop | Phone |
|---|---|---|
| Queued | [1440](fixture-pending-1440.jpg) | [390](fixture-pending-390.jpg) |
| Running | [1440](fixture-running-1440.jpg) | [390](fixture-running-390.jpg) |
| Failed analysis | [1440](fixture-failed-1440.jpg) | [390](fixture-failed-390.jpg) |
| Skipped analysis | [1440](fixture-skipped-1440.jpg) | [390](fixture-skipped-390.jpg) |
| Partial coverage and material agent outcomes | [1440](fixture-partial-1440.jpg) | [390](fixture-partial-390.jpg) |
| Changed PR revision | [1440](fixture-outdated-1440.jpg) | [390](fixture-outdated-390.jpg) |
| Missing revision and historical metadata | [1440](fixture-unrecorded-1440.jpg) | [390](fixture-unrecorded-390.jpg) |
| Permission denial | [1440](fixture-denied-1440.jpg) | [390](fixture-denied-390.jpg) |
| Failed initial read | [1440](fixture-read-failure-1440.jpg) | [390](fixture-read-failure-390.jpg) |
| Transient failure with authorized cached data | [1440](fixture-cached-1440.jpg) | [390](fixture-cached-390.jpg) |

## R–S. Limitations and recommendation

The live sample covers two terminal reviews from one installation. Active reviews, exceptional coverage, failed delivery and permission failures were exercised in isolation. The trace counts fetch attempts and does not establish server completion for every request. The phone findings layout still requires more vertical space than the baseline. The individual finding and agent card treatments remain future work.

**GO for Phase 4b review and separate approval.** Phase 4a passed its automated and authenticated visual gates. Phase 4 remains open.
