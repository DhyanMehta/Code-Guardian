# Phase 3b · Pull request experience

Authenticated acceptance passed on 24 November 2026 for **DhyanMehta/httpx, PR #1, review #79**. The filled **View Review** link opened the saved result. Browser Back restored the same installation and PR. The saved trace contains 16 GET calls and zero review-trigger attempts.

## A. Git baseline and preservation

Branch `codex/durable-review-pipeline` at `dc9b6af4149764ae66e2ca10974c151a6bf819a0` was one commit ahead of its remote. The index was empty. The working tree already included edits across routes, shared controls, dashboard pages, CSS and tests, plus untracked milestone reports, screenshots, checklists and unrelated backend documentation. The baseline captures used that working tree including Phase 3a. All milestone edits remain local and unstaged.

## B. Files changed for this milestone

| Area | Paths relative to the repository |
|---|---|
| Dashboard | `frontend/src/pages/RepoDashboardPage.tsx`, `frontend/src/components/dashboard/PullsTab.tsx`, `frontend/src/components/dashboard/prActions.ts`, `frontend/src/components/dashboard/PullRequestRow.tsx` |
| Write owner and feedback state | `frontend/src/components/reviews/TriggerReview.tsx`, `frontend/src/api/writes.ts` |
| New tests | `frontend/src/test/prActions.test.ts`, `frontend/src/test/prWorkspace.test.tsx` |
| Existing workflow assertions updated for the new control names | `frontend/src/test/readFlows.test.tsx`, `frontend/src/test/writeFlows.test.tsx`, `frontend/src/test/reliabilityFlows.test.tsx`, `frontend/src/test/repositoryNavigation.test.tsx` |
| Acceptance | `UI_REGRESSION_CHECKLIST.md`, `tasks/todo.md`, this README and the evidence files linked in J, O, P and Q |

## C–D. Previous and redesigned presentation

The baseline gave the current SHA a separate line, presented the result as a small text link and gave the filled action to “Run a new review”. At 1440px the saved-result target was 167 × 20px. Severity and degraded-agent information from the list response did not appear in the row.

The PR title opens GitHub. The next group identifies the saved run, its analysis state and its relationship to the current head. Findings, severity counts, recorded limitations and delivery precede the actions in reading order. **View Review** is a filled anchor to the canonical result. **Run Another Review** is a secondary native button. The row itself is static. Commit details disclose the full identifiers. The historical list still links to its existing records.

## E. Classifier and ownership

`RepoDashboardPage` supplies the selected installation’s validated mode. `PullsTab` owns the existing 50-PR pagination and scoped history query. History reads in batches of 100, initially capped at ten pages. The first record for each PR in server order is its latest known review. A pending or running record already found for that PR takes precedence. Extending the search keeps the previously read page available while the longer query resolves. Access loss clears readable results.

`classifyPrActions` accepts the selected record, history reliability, head, policy and scoped write state. It returns a destination, labels, visual priority, warning and revision relationship. `PullRequestRow` renders those decisions. Only `TriggerReview` can submit or navigate after acceptance. Rendering and resizing use the same mounted workflow owner.

## F. Action-state matrix

All 19 table-driven classifier cases passed. Eleven additional workspace integration cases exercise the production components with isolated responses.

| Evidence | Dominant action or message | Mutation and recovery |
|---|---|---|
| Completed, same head | View Review | Secondary Run Another Review |
| Running | View Progress for the recorded ID | Conflicting request suppressed. Older target explicitly identified |
| Pending | View Queued Review for the recorded ID | Conflicting request suppressed |
| Failed | Inspect Failed Review | Recorded summary or failure label, deliberate rerun |
| Skipped | Inspect Skipped Review | Recorded summary or skip label, deliberate rerun |
| Terminal, outdated | View Previous Review | Review Current Revision, both revisions available |
| Missing SHA | Existing status-specific destination | Unknown freshness, explicit missing-revision text |
| Exhaustive empty history, manual | Review Pull Request | Explains queuing the current head |
| Exhaustive empty history, automatic | Eligibility explanation and existing GitHub PR link | Secondary Request Review Now |
| History loading | Checking review history, or labeled last-known review | Explicit request when eligible |
| Bounded lookup with unresolved PR | Load older review history | Warns that another review may exist |
| Failed history read | Retry history | Authorized cached link remains available on transient failure |
| Known restriction | Keep readable result after write denial | Scoped HTTP 403 suppresses another submission. Read denial suppresses inaccessible history |
| Pending write | Requesting review… | Duplicate submissions disabled, saved link retained |
| Uncertain write | Check review history | Guard remains until reconciliation or explicit acknowledgment |

## G–I. Revision, evidence and mutation safety

Both full SHAs were `5b2630b1d2b7442718dea99c443513677afc06dd`. Comparison uses the complete values. An active review targets a revision. A failed or skipped run can match a revision without establishing successful analysis.

Review #79 reports **16 findings**, comprising **1 high, 4 medium and 11 low**. The list supplied no degraded-agent names for this record. Its saved detail explicitly says “Coverage not recorded”. The row reads finding totals, individual severity counts, degraded-agent names and GitHub delivery from their respective fields. It issues no per-row detail requests. The independent delivery status was **posted**.

The existing handler sends a bodyless POST scoped to user, installation, repository and PR. The server verifies installation access, requires repository write authorization and resolves the current head. The client does not derive permission from the installation role or review mode. Scoped busy and uncertain guards, cache invalidation, validated accepted ID and the unmount check remain in the write path. Tests cover a response arriving after an installation switch, a bodyless rerun accepted as review #12, a forbidden write with readable history and an ambiguous response without replay. All mutation tests used mocks.

## J. Responsive measurements

Dimensions are CSS pixels rounded to the nearest pixel. First PR position is the top of the first article at page start. Available width can exclude the scrollbar gutter. The final document scroll width equaled its available width at every viewport.

| Viewport | Available / scroll | Row width | First PR y, before → after | Row height, before → after | View Review / rerun height |
|---:|---:|---:|---:|---:|---:|
| 1920 | 1920 / 1920 | 1232 | 382 → 382 | 259 → 278 | 40 / 40 |
| 1440 | 1434 / 1434 | 1232 | 382 → 382 | 259 → 278 | 40 / 40 |
| 1024 | 1018 / 1018 | 970 | 378 → 378 | 259 → 278 | 40 / 40 |
| 768 | 762 / 762 | 714 | 418 → 418 | 259 → 332 | 40 / 40 |
| 700 | 694 / 694 | 646 | 478 → 482 | 263 → 344 | 44 / 44 |
| 390 | 385 / 385 | 353 | 578 → 578 | 297 → 390 | 44 / 44 |
| 320 | 314 / 314 | 282 | 578 → 578 | 336 → 447 | 44 / 44 |

At 320px the actions stack below the evidence. At both phone widths the user scrolls to reach the result action from page entry. At 1440px the result link measures 139 × 40px and the secondary button 169 × 40px. The baseline’s 12px supporting copy gives way to 15px summary text and 14px author metadata. Severity labels use the shared 13px desktop and 14px mobile roles. [Before measurements](before-measurements.json) · [Final measurements](after-measurements.json)

## K. Accessibility

Keyboard order within the reference row is GitHub PR link → saved review link → rerun button → native commit disclosure. Tabbing from the title focused “View Review #79 for DhyanMehta/httpx PR #1”. The focus outline was visible. The integration suite also verified that a focused saved link survives a history continuation and that access loss removes the link. The 700px account menu and repository chooser remained reachable.

Computed token contrast is 6.29:1 for white on the primary action, 11.97:1 for supporting text on the panel, 8.81:1 for muted metadata on the panel and 8.91:1 for the focus color against the panel. Status and severity both have written labels.

## L–N. Automated verification

| Check | Result |
|---|---|
| Focused Vitest run | **134 passed in 14 files**. Filters covered prActions, prWorkspace, readFlows, writeFlows, reliabilityFlows, repositoryNavigation, identity, finalFlow, reviewProgress, polling, Button, SeverityBadge and SharedFeedback. The Button filter also matched IconButton |
| Full `npm test` | **194 passed in 28 files** |
| Production `npm run build` | TypeScript and Vite succeeded, 1,964 modules transformed |
| `git diff --check` | Passed |

## O. Authenticated screenshots

| Viewport | Baseline | Final |
|---:|---|---|
| 1920 | [Before](before-1920.jpg) | [After](after-1920.jpg) |
| 1440 | [Before](before-1440.jpg) | [After](after-1440.jpg) |
| 1024 | [Before](before-1024.jpg) | [After](after-1024.jpg) |
| 768 | [Before](before-768.jpg) | [After](after-768.jpg) |
| 700 | [Before](before-700.jpg) | [After](after-700.jpg) |
| 390 | [Before](before-390.jpg) | [After](after-390.jpg) |
| 320 | [Before](before-320.jpg) | [After](after-320.jpg) |

[Focused result link](focused-review.jpg) · [Exact commit details](commit-details.jpg) · [Saved review #79](saved-review-79.jpg) · [Browser Back](browser-back.jpg) · [320px action group](actions-320.jpg) · [700px account menu and chooser](account-menu-700.jpg)

## P. Authenticated request trace

The local verification entry loaded the real application with its existing session, recorded each application fetch method and route, and blocked non-GET methods before dispatch. The journey started at Connected Repositories, opened the scoped httpx PR workspace, followed View Review to #79 and used browser Back. The final URL restored `/repos/DhyanMehta/httpx?installation_id=161715271`. The trace includes development-mode repeated reads. Review detail reads first appear after selecting the saved link. **16 GET, 0 write attempts, 0 review-trigger POSTs.** [Method and endpoint trace](live-requests.txt)

## Q. Isolated visual evidence

These browser captures used the production classifier and row with synthetic records, isolated from backend writes. The fixture heading identifies every capture. The mocked integration suite separately exercised actual handlers.

- [Queued](fixture-pending.jpg), [running](fixture-running.jpg), [failed](fixture-failed.jpg), [skipped](fixture-skipped.jpg)
- [Outdated revision](fixture-outdated.jpg), [missing review SHA](fixture-missing-sha.jpg)
- [Manual first review](fixture-manual.jpg), [automatic eligibility](fixture-auto.jpg)
- [Loading](fixture-loading.jpg), [bounded](fixture-bounded.jpg), [failed history with saved result](fixture-history-error.jpg)
- [Write permission denied](fixture-permission.jpg), [pending write](fixture-busy.jpg), [uncertain write](fixture-uncertain.jpg)

[Rendered text from the fourteen fixture states](fixture-states.json)

## R–S. Limitations and recommendation

The authenticated sample provided one completed same-head result. Exceptional states, deliberate reruns and installation-switch races were tested in isolation. Browser keyboard and accessibility-tree checks covered semantics and focus. Physical touch and screen-reader speech were outside this run. PR lists still depend on bounded history and the API’s summary fields. The saved detail remains the source for more granular execution evidence.

**GO for review and separate Phase 3c approval.** Scoped freshness and the broader historical-review presentation remain pending. Phase 3 remains open.
