# Phase 1 foundation milestone

**24 November 2026 · Branch `codex/durable-review-pipeline` · Baseline `dc9b6af`**

## A. Baseline and working tree

HEAD matched the master plan. The initial staged and unstaged tracked diffs were empty. The audit, master plan, checklist and other pre-existing untracked files were preserved. The changes below remain unstaged.

## B. Exact files modified

| Purpose | Files |
|---|---|
| Tokens | [frontend/src/index.css](../../frontend/src/index.css) |
| Shared controls | [Button.tsx](../../frontend/src/components/common/Button.tsx), [IconButton.tsx](../../frontend/src/components/common/IconButton.tsx), [SearchInput.tsx](../../frontend/src/components/common/SearchInput.tsx), [InstallationPicker.tsx](../../frontend/src/components/common/InstallationPicker.tsx) |
| Shared state and shell | [AsyncState.tsx](../../frontend/src/components/common/AsyncState.tsx), [ProtectedRoute.tsx](../../frontend/src/components/common/ProtectedRoute.tsx), [AppLayout.tsx](../../frontend/src/components/layout/AppLayout.tsx) |
| First consumer | [frontend/src/pages/RepoListPage.tsx](../../frontend/src/pages/RepoListPage.tsx) |
| Tests | [Button.test.tsx](../../frontend/src/test/Button.test.tsx), [IconButton.test.tsx](../../frontend/src/test/IconButton.test.tsx), [ProtectedRoute.test.tsx](../../frontend/src/test/ProtectedRoute.test.tsx), [readFlows.test.tsx](../../frontend/src/test/readFlows.test.tsx) |
| Added evidence | This report and six JPEGs linked in section I |

## C. Design tokens

- Page heading 24/32 px on phones and 28/36 px from 768 px. Section heading 20/28 px and 22/30 px. Row title 16/24 px and 17/24 px.
- Body 16/24 px, support 15/22 px, control 15/22 px or 15/20 px, metadata 14/20 px or 13/20 px, code 14/21 px. Plus Jakarta Sans remains the prose face. Repository branch labels use JetBrains Mono.
- Added `panel`, `panel-raised`, `panel-inset`, `fg`, `fg-secondary`, `fg-muted`, action fills and hover roles, link/focus, control border/divider and additive status/severity roles. Existing palettes still resolve. See the stylesheet for values.
- `control-target` sets a 44 px minimum below 768 px and 40 px above. `control-focus` adds a solid 2 px outline with a 3 px offset for keyboard focus.

## D. Shared controls

Button keeps the original variants, sizes, loading and native props and adds quiet and destructive variants. IconButton keeps an explicit name, hides its decorative icon from assistive technology and shares the focus and target rules. Search and installation selection remain native fields. The installation label and select can wrap as whole units in narrow layouts.

## E. Connected Repositories

The header, supporting text, search, repository name, metadata and freshness time use the new roles. Refresh uses a secondary button with a decorative refresh icon. GitHub App access is a visually distinct external anchor with its existing URL. Repository titles and “View pull requests” still navigate to the same installation-scoped path. Repository cards use a static panel style and hover is reserved for the links. Search, count data, selection, cache behavior and the read-error paths retain their existing contracts.

## F. Accessibility

The first tab stop is Skip to main content. Enter moves focus to the main landmark, after which Tab reaches the first page control. The protected-route wait shows “Checking your sign-in…” in a status region. The footer identifies CodeGuardian AI and removes the unverified assurance language. Freshness uses a machine-readable time element.

| Measured on the live page | Before | After |
|---|---:|---:|
| Desktop heading / description | 24 / 14 px | 28 / 15 px |
| Desktop repository title / metadata | 16 / 12 px | 17 / 13 px |
| Phone repository title / metadata | 16 / 12 px | 16 / 14 px |
| Desktop refresh | 144 × 16 px, underlined | 203 × 40 px, secondary button |
| Phone refresh | 144 × 16 px, underlined | 203 × 44 px, secondary button |
| GitHub App access | 12 px text, 16 px target | 15 px text, 40 px desktop / 44 px phone target |
| Search | 14 px text, 38 px high | 16 px text, 40 px desktop / 44 px phone |
| Last updated | 12 px, 4.08:1 on canvas | 13 px desktop / 14 px phone, 9.64:1 on canvas |

Contrast ratios use computed sRGB colors. Muted metadata on the new panel is 8.81:1 and the refresh label is 14.47:1 against its fill.

## G. Test results

- Focused baseline: 33 passed in 8 files.
- Focused after implementation: 34 passed in 8 files. Button, IconButton, ProtectedRoute, readFlows, SearchInput, Tabs, SeverityBadge and reliabilityFlows.
- Full frontend suite: 105 passed in 21 files. The expanded read-flow test checks the scoped destination, semantic GitHub link, retained search, GET-only refresh and shell accessibility. Mutation contracts are exercised through isolated test responses.

## H. Build

`npm run build` completed TypeScript and the Vite production build.

## I. Visual comparison

Same authenticated installation and five repository records, with an empty search in all six captures. The listed widths are browser viewport settings. The capture excludes browser chrome and can differ slightly from the nominal dimensions.

| Viewport | Before | After |
|---|---|---|
| 1440 × 900 | [Desktop baseline](before-1440.jpg) | [Desktop result](after-1440.jpg) |
| 390 × 844 | [Phone baseline](before-390.jpg) | [Phone result](after-390.jpg) |
| 320 × 760 | [Narrow phone baseline](before-320.jpg) | [Narrow phone result](after-320.jpg) |

## J. Visual limits

The 320 px view naturally shows fewer rows above the fold because standalone controls have larger targets. The installation label stays whole. The longest live repository name, DhyanMehta/flask-task-api, fits in the narrow view, and the link has an explicit wrapping rule for longer identifiers. No oversized fixture was injected into the live session. Screen-reader speech and physical touch remain untested.

## K. Acceptance

The milestone passed the focused and full frontend suites, production build and live checks at all three widths. The document fit at 1434, 385 and 314 CSS px of available width respectively. Visible keyboard focus, skip navigation, case-insensitive search, retained focus/query after refresh and repository navigation were confirmed. The first repository still opens its scoped PR screen. Live verification used read paths only.

## L. Remaining Phase 1 work

The broader shared-state work in Phase 1c remains. It includes the static severity and metric card treatments, shared section and status components, cross-page timestamp formatting and write feedback adoption. The user’s approval covers this first milestone.

PHASE 1 FOUNDATION MILESTONE COMPLETE — AWAITING VISUAL REVIEW
