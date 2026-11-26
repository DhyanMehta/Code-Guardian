# Phase 1c shared UI foundations

**24 November 2026 · `codex/durable-review-pipeline` · HEAD `dc9b6af`**

## A. Previous milestone

Reviewed all six screenshots in the first milestone. The desktop rows and toolbar maintain their alignment, the larger refresh target stays distinct from GitHub navigation, and secondary text is brighter. The 390 px view stacks controls comfortably. At 320 px, the installation label stays whole and the larger targets show fewer rows above the fold. No significant regression in those captures blocked this milestone. [Previous report and images](../frontend-phase-1/README.md)

## B. Worktree

The initial staged diff was empty. The thirteen unstaged Phase 1 files and pre-existing untracked material were present and inspected. This milestone extends AsyncState, the theme and the repository freshness call site from that work. All changes remain unstaged. The original report, screenshots, plan and checklist are intact.

## C. Exact Phase 1c files

| Area | Paths |
|---|---|
| Tokens | [index.css](../../frontend/src/index.css) |
| Updated common components | [AsyncState.tsx](../../frontend/src/components/common/AsyncState.tsx), [SeverityBadge.tsx](../../frontend/src/components/common/SeverityBadge.tsx), [StatCard.tsx](../../frontend/src/components/common/StatCard.tsx), [WriteFeedback.tsx](../../frontend/src/components/common/WriteFeedback.tsx) |
| Added common components | [FriendlyTimestamp.tsx](../../frontend/src/components/common/FriendlyTimestamp.tsx), [SectionCard.tsx](../../frontend/src/components/common/SectionCard.tsx), [StatusBadge.tsx](../../frontend/src/components/common/StatusBadge.tsx) |
| Dashboard and review consumers | [AnalyticsTab.tsx](../../frontend/src/components/dashboard/AnalyticsTab.tsx), [SettingsTab.tsx](../../frontend/src/components/dashboard/SettingsTab.tsx), [ReviewPresentation.tsx](../../frontend/src/components/reviews/ReviewPresentation.tsx) |
| Page consumers | [ProfilePage.tsx](../../frontend/src/pages/ProfilePage.tsx), [RepoListPage.tsx](../../frontend/src/pages/RepoListPage.tsx), [ReviewDetailPage.tsx](../../frontend/src/pages/ReviewDetailPage.tsx) |
| Tests | [FriendlyTimestamp.test.tsx](../../frontend/src/test/FriendlyTimestamp.test.tsx), [SharedFeedback.test.tsx](../../frontend/src/test/SharedFeedback.test.tsx), [SeverityBadge.test.tsx](../../frontend/src/test/SeverityBadge.test.tsx), [StatCard.test.tsx](../../frontend/src/test/StatCard.test.tsx), [reliabilityFlows.test.tsx](../../frontend/src/test/reliabilityFlows.test.tsx) |
| Evidence | This report and the nine JPEGs below |

## D. Shared components and first consumers

SeverityBadge serves findings and severity totals. StatusBadge serves the existing analysis label on Review Detail. StatCard uses SectionCard to render the existing analytics KPIs. FriendlyTimestamp serves the repository list fetch time. Existing AsyncState and WriteFeedback consumers receive the shared feedback treatment. Settings supplies its existing busy copy and Profile supplies its existing confirmed-save receipt.

## E. Severity and analysis

Severity labels are sentence-case text with decorative icons and severity-specific tokens. Icon-only use keeps text available to assistive technology. Static labels carry no live-region role. Completed, Running, Queued, Failed, Skipped, Degraded and Unknown have explicit status text. The live review retained “Coverage not recorded” while displaying “Analysis Completed”. Finding counts and agent outcomes keep their existing meanings.

## F. Static surfaces

The existing analytics grid uses static cards with definition-list label/value pairs, tabular numerals and new 24/32 px and 28/36 px value roles. The live data remained 10 reviews, 9 completed, 0 failed and 1 skipped. The other analytics values and their ordering were preserved. Severity totals shed redundant borders around individual badge/count pairs. Finding summaries have local hover and a visible focus treatment.

## G. Timestamps

The repository list identifies the value as “Last successful fetch”. It formats the date and time in the viewer’s locale with a GMT offset, then exposes the exact fetch instant in a native disclosure. The reusable component can also accept explicitly zoned server event strings, preserves the unrounded input, and emits a valid machine-readable instant when available. Missing, invalid and ambiguous zoneless values display as unavailable. Server event callers still use their existing display during this milestone.

## H. Read and write feedback

Initial reads have a status message. Routine background refresh and timestamp updates stay quiet for screen readers. Failed reads keep their source error, last successful fetch when available and an explicit Retry. Cached data ownership and the offline banner stay with the existing resource and shell code.

Write feedback presents the caller’s busy and confirmed-success messages and preserves validation, permission and conflict errors. Ambiguous results explain the uncertainty and require the existing explicit reconciliation action before an intentional retry. The presenters delegate to existing handlers. They add no request, automatic mutation replay or inferred success.

## I. Focused tests

68 passed across 10 test files. This includes the badge, metric, button, icon, protected-route, timestamp, shared feedback, read flow, write flow and reliability coverage. The skipped-review regression assertion now checks the status inside its Analysis row.

## J. Full suite

`npm test` passed all 133 tests across 23 files. Existing route, installation scope, review initiation, standards and fix-decision workflows were exercised with isolated responses. Live inspection used existing read paths.

## K. Production build

`npm run build` passed TypeScript and Vite. The analytics metric definitions explicitly keep the label type separate from the string-or-number value.

## L. Responsive evidence

| Surface | Before | After | Result |
|---|---|---|---|
| Analytics · 1440 px | [Baseline](before-analytics-1440.jpg) | [Updated](after-analytics-1440.jpg) | Same metrics and sample. Cards are static and labels use prose type. |
| Connected Repositories · 390 px | [Baseline](before-repos-390.jpg) | [Updated](after-repos-390.jpg) | Timestamp label and local offset wrap naturally. Repository controls and results fit. |
| Review #79 · 320 px | [Baseline](before-review-320.jpg) | [Updated](after-review-320.jpg) | Analysis status, missing coverage and severity are visually distinct. |
| Feedback · 320 px | [Fixture baseline](before-feedback-320.jpg) | [Fixture updated](after-feedback-320.jpg) | Isolated data with inert callbacks. Retry and reconciliation wrap and remain reachable with keyboard focus. |
| Repository toolbar · 700 px | | [Focused timestamp](after-repos-700.jpg) | Search, refresh and focused timestamp fit. The existing header breakpoint remains visible. |

Document scroll width equaled available width in all checked views. The old and new live screenshots use the same repository, review and selected installation as applicable. The isolated feedback fixture was removed after capture.

## M. Accessibility verification and limits

Browser checks confirmed keyboard-opened exact time, a visible focus outline and a machine-readable value matching the disclosed fetch time. At 320 px the reconciliation button remained fully visible with focus and grew to roughly 58 px to fit its label. The severity pairs measure 7.96:1 to 11.14:1 on their assigned surfaces and muted metric labels measure 8.81:1 on the card surface. These are color-pair calculations, not a full accessibility conformance result. Screen-reader speech, forced colors, physical touch and live offline rendering remain unverified. Error and uncertain-write visuals came from the isolated fixture.

## N. Remaining work

The shared foundations are ready for review. Existing debts belong to the phases already assigned in the master plan. Those include the header control duplication near 700 px, repository and review navigation, chart and narrow history semantics, and broader server timestamp adoption.

## O. Recommendation

**GO for Phase 2 after explicit approval.** The Phase 1c tests, build and representative responsive checks passed. The known 700 px header behavior remains part of Phase 2.

PHASE 1c SHARED FOUNDATIONS COMPLETE — AWAITING REVIEW
