# Phase 2b repository navigation and contextual layout

**24 November 2026 · Authenticated acceptance passed**

## A. Git baseline and working-tree preservation

Before the work, branch `codex/durable-review-pipeline` pointed to `dc9b6af` with an empty index. The baseline included 25 tracked frontend modifications and six untracked frontend component and test files from Phases 1, 1c and 2a. The existing audit, plan, checklist and earlier milestone reports and screenshots were present. The worktree and index were preserved. [Audit](../FRONTEND_SCREENSHOT_AUDIT_2026-11-23.md) · [Master plan](../../tasks/plan.md) · [Phase 1](../frontend-phase-1/README.md) · [Phase 1c](../frontend-phase-1c/README.md) · [Phase 2a live acceptance](../frontend-phase-2a/README.md#o-final-live-acceptance--24-november-2026)

The established local services and session were available before editing. The reference remained the actual `DhyanMehta/httpx` repository under installation `161715271`, default branch `master`, automatic reviews, with saved review #79. The existing global shell retained its 1280 px maximum from Phase 2a. The approved Phase 2b boundary keeps the fourth repository view as an installation-wide Settings entry until the direct route is approved.

## B. Exact files modified

| Area | Files |
| --- | --- |
| Repository workspace | [RepoDashboardPage.tsx](../../frontend/src/pages/RepoDashboardPage.tsx), [ContextBar.tsx](../../frontend/src/components/layout/ContextBar.tsx), [Tabs.tsx](../../frontend/src/components/common/Tabs.tsx) |
| Installation scope | [InstallationPicker.tsx](../../frontend/src/components/common/InstallationPicker.tsx), [RepoListPage.tsx](../../frontend/src/pages/RepoListPage.tsx) |
| Refresh metadata and scoped Settings link | [AsyncState.tsx](../../frontend/src/components/common/AsyncState.tsx), [PullsTab.tsx](../../frontend/src/components/dashboard/PullsTab.tsx), [SettingsTab.tsx](../../frontend/src/components/dashboard/SettingsTab.tsx) |
| Regression tests | [repositoryNavigation.test.tsx](../../frontend/src/test/repositoryNavigation.test.tsx), [Tabs.test.tsx](../../frontend/src/test/Tabs.test.tsx), [reliabilityFlows.test.tsx](../../frontend/src/test/reliabilityFlows.test.tsx) |
| Evidence | This report, 32 JPEGs linked in section N, and the [implementation checklist](../../UI_REGRESSION_CHECKLIST.md) |

## C. Previous repository navigation architecture

The dashboard rendered a standalone installation card, a breadcrumb with default branch and mode, and a separate identity card that repeated both values. The permanent sidebar also held the four local tabs and global Repositories and Profile shortcuts. At 1024 px and above, the sidebar was 256 px wide. Below 1024 px, it occupied the full content width ahead of the active panel. At 390 and 320 px, only one of four tabs fit fully in its scrolling strip. The baseline tablist was vertical at desktop sizes while exposing the implicit horizontal orientation. The local back links to `/repos` discarded explicit installation scope. Repeated last-updated lines preceded the workspace, Pull Requests and Settings content.

Visible `nav`, `aside` and tablist elements totaled four at 1440, 1024 and 768 px, including the global primary navigation. They totaled three below 768 px with the account menu closed. The installation picker was already backed by the single provider. Repository access was gated by the selected installation's repository list.

## D. New repository navigation architecture

One contextual region contains a scoped back link, the installation picker and mode, the authorized repository's full name as an H1, and its known default branch. Each identity value appears once in that region. There are zero sidebar elements. The active panel occupies the main content width. At desktop widths the global primary nav and repository tablist each have their own purpose. Below 768 px, one labeled native select owns repository-view navigation. The Phase 2a global account disclosure continues to own global account actions.

The dashboard keeps authorization and tab selection, and the existing tab components keep the data subscriptions. The shell omits routine freshness for the repository-authorization read while preserving loading, errors, retry and last-success information on failure. Pull Requests and Installation Settings group their two source-specific fetch times under one keyboard-operable Refresh details disclosure. Each populated timestamp remains machine-readable. Analytics and Agent History retain their single resource status.

## E. Installation context treatment

Connected Repositories and the repository workspace use the same compact picker. The label, selected account, and installation-wide review mode travel together. The list shows the mode once beside the picker and keeps existing search, rows, branch metadata and repository destinations. A missing branch or mode has no invented value. Suspended and invalid selections have explicit recovery messages, and a repository that is unavailable in the chosen scope has no view controls. Multiple installations use the same native select and authoritative provider, with the same precedence and remembered selection logic. Canonical Review Detail uses its recorded parent and has no installation picker.

## F. Desktop layout and measured improvements

All dimensions below are CSS pixels, rounded. Context and navigation are measured from the global header's bottom to the active panel top, including the main gutter. Heading and first PR coordinates start at the viewport top. Measurements used the same repository, installation and existing review.

| Viewport | Content width before → after | Context and nav before → after | First content heading Y before → after | First PR heading Y before → after | Document scroll / available after |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1920 | — → 1232 | — → 189 | — → 254 | — → 403 | 1920 / 1920 |
| 1440 | 952 → 1232 | 199 → 189 | 263 → 254 | 433 → 403 | 1440 / 1440 |
| 1024 | 690 → 976 | 203 → 189 | 263 → 250 | 433 → 399 | 1024 / 1024 |
| 768 | 714 → 720 | 441 → 189 | 498 → 246 | 667 → 395 | 768 / 768 |
| 700 | 646 → 652 | 445 → 193 | 502 → 250 | 671 → 403 | 700 / 700 |
| 390 | 353 → 353 | 470 → 297 | 527 → 354 | 741 → 551 | 385 / 385 |
| 320 | 282 → 282 | 502 → 323 | 559 → 380 | 773 → 577 | 314 / 314 |

The 1440 px layout recovered 280 px from the sidebar and its gap. At 1024 px the gain also includes the disappearance of a 6 px page scrollbar. All four horizontal destinations fit at 768 px. The selected tab measured 146 × 40 px, and the installation picker measured 40 px high. There is one tab stop within the tablist and four selectable views.

## G. Tablet and mobile layout

Below 768 px the Repository view select shows the current title and all four options. At 320 px it measured 185 × 44 px and the installation selector was 44 px high. ArrowDown reached Analytics, Agent History and Installation Settings, and Home returned to Pull Requests. The control retained focus after selection. Back restored Agent History, Forward restored Installation Settings, and reloading retained the selected view and scope. Each of the four views had no document overflow at 320 px. The long-name fixture preserved all text at that width and wrapped across five heading lines.

## H. Route and query-parameter preservation

The workspace uses the existing `/repos/:owner/:repo` route with `installation_id` and `tab`. Pull Requests remains the default, invalid tab values normalize in place, and other query parameters survive tab and installation changes. A view change pushes a navigation entry and reselecting the active view leaves history alone. The context back link returns to `/repos` with the explicit scope. Browser tests confirmed the same installation before and after the return link. Deep links, Back, Forward and reload restore the scoped view. The canonical `/reviews/79` path was opened by keyboard and pointer, and the saved review supplied the scoped repository return link. The legacy PR resolver and finding fragment behavior retain their existing routes. Automated regression checks cover explicit scope over a remembered alternative, invalid, suspended, and inaccessible scope, and a delayed old response during switching.

## I. Settings transition boundary

Installation Settings remains at `tab=settings` and states that its settings affect every repository in the selected installation. The existing link to Profile carries the installation ID for the return journey. The form's permissions, inputs, mutation contracts and guarded write states retain their existing owners. The direct installation Settings route and any redirect aliases are outside Phase 2b.

## J. Accessibility improvements

- Desktop uses a named horizontal tablist, native buttons, roving focus, `aria-selected`, valid `aria-controls` and reverse labeling for each tab panel. Inactive desktop panel shells are hidden and contain no data owners or controls. The active panel can take focus before its internal controls. Left/Right and Home/End retain the tabs' keyboard behavior.
- The native mobile select is visibly labeled and points to the single named content region. Only one navigation control type is mounted at a time. When the focused control crossed the 768 px breakpoint, focus transferred from the tab to the select and back to the selected tab. Automated verification confirmed the active panel content instance and subscription count survived a resize.
- The 700 px account menu still exposes one Profile and one Sign out control, with Escape returning focus. The first shell skip link still targets main. Context supplies one H1 with the full repository name. Loading and access-loss states remain perceivable.
- The computed active tab foreground on its fill was 7.95:1, inactive text on canvas was 13.09:1, native chooser text on its fill was 16.97:1, and its control border against its fill was 4.80:1. Visible solid focus outlines were observed on both navigation layouts.

## K. Focused tests

75 tests passed across 11 files with `npm test -- repositoryNavigation Tabs Navbar identity readFlows reliabilityFlows finalFlow ProtectedRoute writeFlows auth callbackRecovery`. The new suite covers desktop panel relations and history, explicit scope, three access failures, a delayed installation switch, compact chooser and focus transfer, and record-scoped canonical review navigation. Existing assertions for member access, write guards, auth, legacy resolution and review behavior remain covered.

## L. Full frontend suite

`npm test` passed 144 tests across 25 files.

## M. Production build

`npm run build` passed TypeScript and the Vite production build. `git diff --check` passed.

## N. Authenticated before and after evidence

The baseline and redesign use the same authenticated `DhyanMehta/httpx` repository. An em dash indicates a baseline width that was outside the required capture set. The image dimensions can exclude the scrollbar gutter.

| Pull Requests viewport | Before | After |
| --- | --- | --- |
| 1920 px | — | [Workspace](after-pulls-1920.jpg) |
| 1440 px | [Workspace](before-pulls-1440.jpg) | [Workspace](after-pulls-1440.jpg) |
| 1024 px | [Workspace](before-pulls-1024.jpg) | [Workspace](after-pulls-1024.jpg) |
| 768 px | [Workspace](before-pulls-768.jpg) | [Workspace](after-pulls-768.jpg) |
| 700 px | [Workspace](before-pulls-700.jpg) | [Workspace](after-pulls-700.jpg), [account menu](after-account-menu-700.jpg) |
| 390 px | [Workspace](before-pulls-390.jpg) | [Workspace](after-pulls-390.jpg) |
| 320 px | [Workspace](before-pulls-320.jpg) | [Workspace](after-pulls-320.jpg) |

| Other authenticated view | Before | After |
| --- | --- | --- |
| Analytics | [1440](before-analytics-1440.jpg), [320](before-analytics-320.jpg) | [1440](after-analytics-1440.jpg), [320](after-analytics-320.jpg) |
| Agent History | [1440](before-agents-1440.jpg), [320](before-agents-320.jpg) | [1440](after-agents-1440.jpg), [320](after-agents-320.jpg) |
| Installation Settings | [1440](before-settings-1440.jpg), [320](before-settings-320.jpg) | [1440](after-settings-1440.jpg), [320](after-settings-320.jpg) |
| Connected Repositories | [Phase 2a baseline](../frontend-phase-2a/live-1440.jpg) | [Scoped list](after-connected-repositories.jpg) |
| Review #79 | [Phase 2a baseline](../frontend-phase-2a/live-review-79.jpg) | [Saved review](after-review-79.jpg) |

Separate 320 px fixture evidence uses the real application components with simulated installations and repository responses. The temporary harness rejected mutations and was removed before the full build. [Long repository name and multiple accounts](fixture-long-repository-320.jpg) · [Inaccessible repository](fixture-inaccessible-repository-320.jpg) · [Suspended installation](fixture-suspended-installation-320.jpg) · [Invalid installation](fixture-invalid-installation-320.jpg)

## O. Data and workflow preservation

The dashboard authorizes the repository via the installation-scoped repository read before mounting workflow content. The provider, cache keys, resource APIs, polling, retries, PR pagination, latest-head comparison, review routing and guarded mutations retain their existing behavior. Installation switches abort the old subscription and wait for access in the new scope, as verified with a late-response test. A responsive switch replaces the navigation control and leaves the active view mounted. Live inspection used only saved records and read navigation. The worker stayed stopped. The fresh browser tab reported zero console warnings or errors.

## P. Remaining limitations

The authenticated account exposed one installation. Multiple accounts, suspended and invalid selection, and cross-installation delayed reads were verified using isolated evidence. Physical touch and screen-reader speech were outside the verification performed. The existing analytics table may scroll within its own frame at narrow widths. PR cards, charts, agent-history internals and standards forms still use their existing designs.

## Q. Recommendation for Phase 2c

**GO for Phase 2c approval.** Phase 2b passed authenticated visual acceptance, focused and full tests, and the production build. Phase 2c requires separate approval.
