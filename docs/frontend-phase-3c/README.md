# Phase 3c · Scoped refresh, timestamps and review history

Authenticated acceptance on 24 November 2026 covered Connected Repositories and Pull Requests at seven viewport widths. Search survived refresh, saved review #79 opened from both the current PR and loaded history, and Browser Back restored the scoped PR workspace. The live journey recorded **27 GETs and zero workflow writes**.

## A. Git baseline and preservation

Work started on `codex/durable-review-pipeline` at `dc9b6af4149764ae66e2ca10974c151a6bf819a0`, one commit ahead of the remote. The index was empty. Prior phases were present as tracked modifications and untracked components, tests, reports and screenshots. The audit, master plan and those changes were preserved. The baseline inspection used the established local services and the existing authenticated session.

## B. Files changed

| Area | Repository paths |
|---|---|
| Freshness | `frontend/src/components/common/ScopedRefreshStatus.tsx` and `frontend/src/components/common/FriendlyTimestamp.tsx` |
| Workspaces | `frontend/src/pages/RepoListPage.tsx` and `frontend/src/components/dashboard/PullsTab.tsx` |
| History and density | `frontend/src/components/dashboard/LoadedReviewHistory.tsx` and `frontend/src/components/dashboard/PullRequestRow.tsx` |
| Tests | `frontend/src/test/ScopedRefreshStatus.test.tsx`, `frontend/src/test/prWorkspace.test.tsx` and `frontend/src/test/repositoryList.test.tsx` |
| Acceptance | `tasks/todo.md`, `UI_REGRESSION_CHECKLIST.md` and this report with its linked evidence |

## C. Previous shared mutation changes

Phase 3b added `errorStatus` to the shared write snapshot so `TriggerReview` can keep an HTTP 403 restriction with the original operation key. The synchronous guard covers both in-flight and uncertain writes. A transport failure, 5xx or undecodable accepted response can leave the write uncertain. The existing explicit reconciliation control and comparison against a newly observed review ID govern recovery. Phase 3c uses the current history resource for this input and uses temporarily retained continuation records for display and active-review detection.

## D. Scoped freshness architecture

`ScopedRefreshStatus` renders existing read snapshots and callbacks. It listens for browser online/offline events and uses the existing paused-monitoring flag. Repository list, PR and review-history reads retain their existing resource owners and keys. The repository toolbar retains its search and count. The PR refresh button invokes both existing read callbacks. An expanded source list exposes each source’s last successful fetch. On an error the toolbar offers a source-specific retry. PR rows retain their state-specific recovery actions from Phase 3b.

## E. Freshness decision matrix

| Read state | Presentation |
|---|---|
| All applicable reads complete | One timestamp summarizes the oldest successful fetch when two sources apply. A single source shows its own fetch time |
| One source updating | Names the updating source and retains recorded source times in the disclosure |
| Initial loading | Announces the loading source without a success timestamp |
| PRs succeed and history fails | Shows review history failure and its retry. Authorized PRs and transiently cached review records stay visible |
| History succeeds and PRs fail | Shows pull request failure and its retry. Authorized cached PRs and readable reviews stay visible when the failure is transient |
| Offline or polling paused | Names the pause and preserves recorded source times under the disclosure |
| No success timestamp | Awaiting data, with unavailable or unrecorded source times identified in the disclosure |
| Access denied | The resource gate drops restricted records and continuation evidence |
| Installation switches | The new scope reads under its own key. Its first render cannot show the previous installation’s fetch time |

## F. Timestamp behavior

Client fetch times come from successful resource snapshots. Historical creation times come from `created_at`. A valid timestamp renders a localized date and time with an explicit offset and a machine-readable `time` value. The native disclosure retains the source string, including its original offset and fractional precision. Missing or malformed values show “Time unavailable”. Zoneless values remain unparsed and can still be inspected when supplied. The interface conveys GitHub delivery as a status without inventing a publication time.

## G–H. Loaded history and continuation

The loaded-history disclosure shows the number loaded and the reported total. Rows show review and PR numbers, analysis state, creation time, findings, abbreviated reviewed revision, recorded degradation and independent GitHub delivery. Their outlined links point to canonical `/reviews/:id` destinations. On narrow screens the data wraps ahead of the row’s link. Rows render on expansion without another history request.

The PR page still reads up to 50 PRs, and history lookup still reads 100 reviews per page with the existing initial bound and continuation actions. A bounded lookup retains its older-history action. Exhaustion is reported only after a successful exhaustive lookup. During continuation the authorized last-loaded records remain readable. Scope changes and nontransient failures drop the retained continuation data. Review selection still favors a known active review, and loaded history does not change the primary result just by being expanded.

## I. Layout measurements

All dimensions are CSS pixels. Baseline toolbar measurement spans the toolbar top through the old freshness control. The final measurement includes the consolidated toolbar. Every final viewport had matching available and document scroll widths in both workspaces.

| Viewport | Available and scroll width | Repositories toolbar | PR toolbar | First PR top | PR row height | View Review top |
|---:|---:|---:|---:|---:|---:|---:|
| 1920 | 1914 | 118 → 110 | 108 → 85 | 382 → 354 | 278 → 278 | 500 → 472 |
| 1440 | 1434 | 118 → 110 | 108 → 85 | 382 → 354 | 278 → 278 | 500 → 472 |
| 1024 | 1018 | 118 → 110 | 108 → 85 | 378 → 350 | 278 → 278 | 496 → 468 |
| 768 | 762 | 118 → 110 | 108 → 85 | 418 → 390 | 332 → 332 | 638 → 610 |
| 700 | 694 | 126 → 118 | 116 → 93 | 482 → 454 | 344 → 344 | 706 → 678 |
| 390 | 385 | 154 → 138 | 156 → 93 | 578 → 506 | 390 → 350 | 852 → 748 |
| 320 | 314 | 154 → 138 | 156 → 93 | 578 → 506 | 447 → 407 | 857 → 753 |

View Review moved up by 104px on both phones. At 320px the actions still follow the review evidence and the second button may require scrolling. An expanded history record measured 1,205 × 101px at 1440, 326 × 205px at 390 and 255 × 241px at 320. Expanded history also fit the document width at each of those sizes. [Baseline repositories](before-repos.json) · [Final repositories](after-repos.json) · [Baseline PRs](before-pr.json) · [Final PRs](after-pr.json) · [History measurements](history-measurements.json)

## J. Accessibility

Native buttons retain scoped accessible refresh names. Native disclosures expose source timestamps by keyboard or touch. The visible keyboard focus ring on View Review was checked by tabbing from the GitHub PR link and activating the result with Enter. Refresh preserved focus in the integration test. Timestamp and action targets measured at least 40px on desktop and 44px at compact widths. Routine refresh changes are visible, with live announcements reserved for initial loading and error alerts. The responsive shell still provides the native repository chooser and the existing account menu.

Computed contrast from the existing tokens measured 6.29:1 for primary-action text, 8.81:1 for muted panel metadata and 8.91:1 for focus or link color against the panel. Historical analysis states have written labels alongside color.

## K. Mutation and authorization safety

The live harness rejected non-GET application requests before dispatch. Scoped retry and continuation call the existing read handlers. The draft request, authorization, accepted-ID navigation and cache invalidation remain with the Phase 3b write owner. Integration tests verify one read per source per explicit PR refresh, scope isolation, late accepted-response handling, the bodyless POST on an explicit mocked rerun and a preserved uncertain guard after unsuccessful history refresh.

## L–N. Automated verification

| Check | Result |
|---|---|
| Focused tests | **144 passed across 14 files**. ScopedRefreshStatus, FriendlyTimestamp, SharedFeedback, repositoryList, repositoryNavigation, prActions, prWorkspace, readFlows, writeFlows, reliabilityFlows, polling, identity, finalFlow and reviewProgress |
| Full frontend suite | **202 passed across 29 files** |
| Production build | TypeScript and Vite passed |
| Whitespace check | `git diff --check` passed |

## O. Authenticated screenshots

| Viewport | Repositories | Pull Requests |
|---:|---|---|
| 1920 | [Before](before-repos-1920.jpg) · [After](after-repos-1920.jpg) | [Before](before-pr-1920.jpg) · [After](after-pr-1920.jpg) |
| 1440 | [Before](before-repos-1440.jpg) · [After](after-repos-1440.jpg) | [Before](before-pr-1440.jpg) · [After](after-pr-1440.jpg) |
| 1024 | [Before](before-repos-1024.jpg) · [After](after-repos-1024.jpg) | [Before](before-pr-1024.jpg) · [After](after-pr-1024.jpg) |
| 768 | [Before](before-repos-768.jpg) · [After](after-repos-768.jpg) | [Before](before-pr-768.jpg) · [After](after-pr-768.jpg) |
| 700 | [Before](before-repos-700.jpg) · [After](after-repos-700.jpg) | [Before](before-pr-700.jpg) · [After](after-pr-700.jpg) |
| 390 | [Before](before-repos-390.jpg) · [After](after-repos-390.jpg) | [Before](before-pr-390.jpg) · [After](after-pr-390.jpg) |
| 320 | [Before](before-repos-320.jpg) · [After](after-repos-320.jpg) | [Before](before-pr-320.jpg) · [After](after-pr-320.jpg) |

The 1920px repository baseline and 390px and 320px PR baseline images use the earlier authenticated milestone captures for the same layouts because the new baseline screenshot exports at those sizes were scaled or clipped. The baseline measurements come from the Phase 3c run.

[Search after refresh](search-refresh.jpg) · [Expanded freshness and exact fetch time](freshness-details.jpg) · [Loaded history](historical-records.jpg) · [Exact creation timestamp](historical-exact.jpg) · [Focused View Review](focused-view-review.jpg) · [Phone actions](mobile-view-review.jpg) · [Phone history](mobile-history.jpg) · [Saved review #79](saved-review-79.jpg) · [Browser Back](browser-back.jpg)

## P. Live request trace

The existing session opened installation `161715271` and repository `DhyanMehta/httpx`. Searching for `httpx` showed one of five repositories after refreshing. PR #1 still showed a completed current-revision review #79 with **16 findings** and **posted** GitHub delivery. History showed ten of ten records. Review #79 displayed creation as 6 Oct 2026, 22:04 GMT+5:30, with source value `2026-10-06T22:04:28.082270+05:30`.

The historical link and the primary PR link both opened the saved review. Browser Back restored `/repos/DhyanMehta/httpx?installation_id=161715271`. The trace records 27 GETs, including development-mode repeated reads, with zero non-GET attempts. [Method and endpoint trace](live-requests.txt)

## Q. Isolated fixture evidence

The nine labeled fixtures rendered the production components with synthetic records and isolated network behavior. [Initial loading](fixture-initial-loading.jpg) · [Background refresh](fixture-background-refresh.jpg) · [Partial failure](fixture-partial-failure.jpg) · [Stale cache](fixture-stale-cache.jpg) · [Offline](fixture-offline.jpg) · [Unresolved history](fixture-unresolved.jpg) · [Exhausted history](fixture-exhausted.jpg) · [Permission denial](fixture-permission-denied.jpg) · [Uncertain write](fixture-uncertain-write.jpg) · [Fixture text](fixture-states.json)

## R–T. Limitations, acceptance and recommendation

Live evidence uses one installation and one same-head current PR. Exceptional data and mutation outcomes were exercised in isolation. Browser keyboard, semantic and layout checks covered the new controls. Physical touch and screen-reader speech remain outside this run.

**Phase 3 is implemented and verified, awaiting final review.** Phase 3a established scoped search and repository navigation. Phase 3b established the primary saved-review action and guarded rerun. Phase 3c verified scoped refresh, independent failures, loaded history, responsive density and read-only navigation. **GO for final review and separate Phase 4 approval.** [Phase 3a](../frontend-phase-3a/README.md) · [Phase 3b](../frontend-phase-3b/README.md)
