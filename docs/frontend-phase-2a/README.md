# Phase 2a global header and application shell

## A. Git baseline and worktree preservation

Before the changes, branch `codex/durable-review-pipeline` pointed to `dc9b6af`. The index was empty. The existing tracked diff covered 24 files, and Phase 1c also had five untracked frontend files. The Phase 1 audit, plan, reports, screenshots and other untracked work were present. The relevant shell diff contained the existing skip link, main target and factual footer, plus the approved control and type tokens.

The original Navbar used AuthProvider for session state, sign-in, busy state, logout and header action errors. It forwarded the protected route's saved path, query and hash into login. Signed-in desktop users saw their avatar or fallback icon, login, Profile and Sign out. The primary Repositories link appeared at 768 px, the desktop account controls appeared at 640 px, and a separate compact menu persisted below 768 px. Opening it at 700 px exposed two Profile links and two Sign out buttons. The compact links closed the menu on activation. The toggle lacked expanded state, a controlled-region ID and Escape handling. Global active styles had no `aria-current`, and global destinations linked to bare paths. The picker lived in page content and resolved scope through InstallationProvider. AppLayout supplied the first keyboard skip link, main landmark and footer.

[Audit](../FRONTEND_SCREENSHOT_AUDIT_2026-11-23.md) · [Master plan](../../tasks/plan.md) · [Phase 1](../frontend-phase-1/README.md) · [Phase 1c](../frontend-phase-1c/README.md)

## B. Exact files modified

- [Navbar.tsx](../../frontend/src/components/layout/Navbar.tsx) implements the global header.
- [Navbar.test.tsx](../../frontend/src/test/Navbar.test.tsx) adds four focused integration tests.
- This report and its JPEG evidence in `docs/frontend-phase-2a/` document the milestone. The temporary browser fixture was removed before the production build.

The worktree retains the earlier milestone changes and unrelated files. The index is empty and HEAD is still `dc9b6af`.

## C. Header and navigation architecture

The sticky banner contains the CodeGuardian AI brand, a primary Repositories destination, and one account disclosure. The account panel exposes the signed-in login, Profile settings, and Sign out. Below 768 px it also contains Repositories. React Router links handle destinations. Native buttons handle the disclosure and existing sign-in and sign-out operations.

The brand and Repositories link retain any explicit `installation_id` from the current URL. Profile carries the same parameter through the return trip while review automation keeps its existing all-administered-installations scope. The parameter goes through the existing InstallationProvider resolution, including invalid and suspended installations. Canonical review links and the repository picker keep their existing routes and behavior.

[AppLayout](../../frontend/src/components/layout/AppLayout.tsx) already provides the skip link, one main landmark, footer and responsive content width. The header uses that width and the existing shell needed no edit. Page titles stay with their pages. This phase needed no PageHeader. Authentication, onboarding, cache scoping, repository authorization, profile automation, review execution and history, findings, analytics, standards, and auto-fix decisions retain their existing code paths.

## D. Desktop layout

At 768 px and up, the brand and Repositories sit on the left and the account toggle sits on the right. The toggle shows the avatar or fallback icon and clips long login text within its own width. The account panel aligns with the right content gutter and shows the full login. The row uses semantic foreground, surface and control typography tokens. Measured header heights were about 57 px at 768, 61 px at 1024, and 65 px at 1440 and 1920. Interactive header controls measured 40 px tall at these sizes.

## E. Tablet and mobile layout

Below 768 px the avatar and visible Menu label open a panel that fits between the content gutters. The header remains about 57 px tall. Each signed-in control measured 44 px tall. The 320 px long-login fixture wraps the complete 42-character login on two lines inside the disclosure. The isolated signed-out view keeps the whole brand on one line and fits the sign-in label on two lines within a roughly 66 px header. The repository list fixture had no horizontal overflow at any tested width. Its 320 px viewport had a 314 px content area due to the vertical scrollbar.

## F. 700px duplicate-control regression

The original header showed two Profile links and two Sign out buttons when the compact menu opened at 700 px. The redesigned header renders each account control once. At 700 px, the closed panel exposed zero Profile and zero Sign out controls. The open panel exposed one Repositories link, one Profile link and one Sign out button. The desktop menu at 1440 px likewise exposed one of each account control. The rendered results and keyboard sequence were verified in a browser with fixture data.

## G. Accessibility improvements

- The menu button has an account-specific accessible name, truthful `aria-expanded`, and `aria-controls` referencing the panel. The panel is a named navigation landmark using native links, a list, and a native operation button. Collapsing it removes its descendants from sequential focus.
- At 700 px, Enter opened the menu. Tab reached Repositories, Profile settings and Sign out, then continued to the first interactive page control and closed the disclosure. Escape from Profile settings closed it and returned focus to the toggle. The browser showed the focus outline. Activating the skip link moved focus to the only main landmark.
- Repositories uses `aria-current="page"` on the list and `aria-current="location"` on a repository or review route. Profile settings uses `aria-current="page"` on its route. A filled background reinforces active link state. The panel does not lock scrolling or trap focus. The menu also dismisses on an outside pointer interaction or a route change.
- Measured theme pairs include brand foreground on canvas at 17.74:1, the active link on its fill at 7.95:1, muted account text on panel at 8.81:1, and Sign out text on its hover fill at 8.42:1. The existing global reduced-motion override covers header color transitions. The disclosure has no animated entrance or routine live announcement. Auth action errors keep their alert semantics.

## H. Focused tests

`npm test -- Navbar auth ProtectedRoute callbackRecovery identity readFlows reliabilityFlows finalFlow` passed all 56 tests across eight files. Header checks cover the sign-in return path, a single disclosure, long login, active link semantics, panel visibility and ARIA attributes, Escape, focus return and exit, the main landmark, sign-out failure and its single mocked POST, and a two-installation journey through scoped links and Back/Forward. Browser checks cover the actual breakpoint and CSS visibility, which jsdom cannot establish.

## I. Full-suite tests

`npm test` passed all 137 tests across 24 files. Authentication, installation, route, profile, review and write-contract regression tests use mocked fetch responses. The browser fixtures served local test data and rejected writes.

## J. Production build

`npm run build` passed TypeScript and Vite production compilation. `git diff --check` passed.

## K. Before and after screenshots

The before repository-list, repository-dashboard, review-detail and profile captures used the authenticated app. After the frontend restarted, the real app could render its shell but returned “Network error. Check your connection” during the live sign-in check. The after images use the real frontend components and routes in a browser with the repository's existing mock API fixtures. The signed-out and long-login pairs use isolated header fixtures throughout. The viewport values are configured CSS widths. Some JPEGs exclude the browser's scrollbar gutter. Differences in account names, review IDs, timestamps, and list length reflect the fixture data.

| View | Before | After |
| --- | --- | --- |
| 1920 px | [Closed](before-1920.jpg) | [Closed](after-1920.jpg) |
| 1440 px | [Closed](before-1440.jpg) | [Closed](after-1440.jpg), [open](after-1440-open.jpg) |
| 1024 px | [Closed](before-1024.jpg) | [Closed](after-1024.jpg) |
| 768 px | [Closed](before-768.jpg) | [Closed](after-768.jpg) |
| 700 px | [Closed](before-700.jpg), [open](before-700-open.jpg) | [Closed](after-700.jpg), [open](after-700-open.jpg), [keyboard focus](after-700-focus.jpg) |
| 390 px | [Closed](before-390.jpg) | [Closed](after-390.jpg) |
| 320 px | [Closed](before-320.jpg), [open](before-320-open.jpg) | [Closed](after-320.jpg), [open](after-320-open.jpg) |
| 320 px, long test login | [Open](before-long-login-320.jpg) | [Open](after-long-login-320.jpg) |
| 320 px, signed out | [Signed out](before-signed-out-320.jpg) | [Signed out](after-signed-out-320.jpg) |
| Repository dashboard | [Pull requests](before-repository.jpg) | [Pull requests](after-repository.jpg) |
| Review detail | [Review #79](before-review.jpg) | [Fixture review #9](after-review.jpg) |
| Profile settings | [Profile](before-profile.jpg) | [Profile with current destination visible](after-profile.jpg) |

## L. Observed visual issues and limits

The old 700 px capture showed the desktop account actions alongside their compact equivalents. The old 320 px signed-out fixture showed wrapped or crowded brand and sign-in controls. The redesign removes the duplicate account controls and contains both the title and sign-in action. In the open compact presentation, the menu temporarily covers the top of the page content and leaves the page in place when dismissed. The header and content gutters align in the desktop fixture. The repository dashboard and review detail still render their existing contextual navigation, and the profile still has its existing narrow policy column.

Authenticated visual verification after the changes is outstanding. The live frontend sign-in check failed, so the live account avatar, live route data, and layout with the exact original account could not be compared after the change. The longest account tested was the isolated 42-character fixture. Sign out was exercised only against a mocked session. No live write or review was initiated.

## M. Remaining Phase 2 work

The installation scope and navigation hierarchy, repository tabs and contextual navigation, and any installation settings route belong to the approved later milestones. They still require their own proof and approval.

## N. Recommendation for Phase 2b

**BLOCKED pending authenticated visual verification and user approval.** Phase 2a implementation, the complete automated suite, the build, and browser checks with fixture data are ready for review. The outstanding acceptance check is to repeat the after capture on the authenticated app once its session endpoint is reachable.

## O. Final live acceptance · 24 November 2026

This result supersedes the initial recommendation in section N. Section K retains the original baseline and fixture evidence.

### Root cause and recovery

FastAPI was stopped on the local API port. With the frontend running during the earlier check, that made its `/auth/me` fetch fail before receiving an HTTP response. At the start of this follow-up, local requests to both Vite on `localhost:5173` and FastAPI on `localhost:8080` returned connection refused and HTTP status `000`. The native Windows PostgreSQL service was already running and `pg_isready` confirmed that `localhost:5432` accepted connections. The initial sandboxed probe could not reach the native service, so this result uses the host-level check.

Started FastAPI from the existing project virtual environment on `127.0.0.1:8080` and Vite on `localhost:5173`. The frontend returned HTTP 200. Readiness returned HTTP 503 with database, Chroma and configuration `ok` and worker `unavailable`. The worker was intentionally left stopped for read-only acceptance. The recovery used the existing PostgreSQL and Chroma stores and required no migrations, setup scripts, tunnels, or security configuration changes.

### Authentication and network evidence

- Vite served the site at the canonical `http://localhost:5173` origin. There was no development API override. The frontend default remains `http://localhost:8080`, and the recovered API observed `GET /auth/me` with status 200 on a full browser reload. The redacted server trace records the path, method, and status. The browser tooling did not expose its Network panel or response headers. The browser console reported zero warnings and errors during the route checks and after reload.
- A credential-free control request returned HTTP 401 with `Access-Control-Allow-Origin: http://localhost:5173` and `Access-Control-Allow-Credentials: true`. The browser client sends requests with `credentials: 'include'`. The existing local session cookie configuration is host-only, HTTP-only and `SameSite=Lax`. The cookie itself was not inspected. The browser's existing session authenticated as `DhyanMehta` and its avatar loaded. The 200 response without reauthentication established that the session remained valid.
- The Phase 2a Navbar, AuthProvider, API client and backend source needed no edits during recovery. The initial transport error disappeared when the service was restored. All browser interactions were navigation, viewport changes and disclosure or focus checks. Sign out and workflow mutation controls were left untouched.

### Authenticated screenshots and responsive evidence

The captures below use the existing session and repository data. The viewport column records the CSS viewport setting. The browser's vertical scrollbar takes up part of the width reported by the document.

| Viewport | Original header | Authenticated Phase 2a | Scroll and available width | Header and control height |
| --- | --- | --- | ---: | ---: |
| 1920 px | [Before](before-1920.jpg) | [Closed](live-1920.jpg) | 1914 / 1914 | 65 / 40 px |
| 1440 px | [Before](before-1440.jpg) | [Closed](live-1440.jpg), [open](live-1440-open.jpg) | 1434 / 1434 | 65 / 40 px |
| 1024 px | [Before](before-1024.jpg) | [Closed](live-1024.jpg) | 1018 / 1018 | 61 / 40 px |
| 768 px | [Before](before-768.jpg) | [Closed](live-768.jpg) | 762 / 762 | 57 / 40 px |
| 700 px | [Closed](before-700.jpg), [open](before-700-open.jpg) | [Closed](live-700-closed.jpg), [open](live-700-open.jpg), [keyboard focus](live-700-focus.jpg) | 694 / 694 | 57 / 44 px |
| 390 px | [Before](before-390.jpg) | [Closed](live-390.jpg) | 385 / 385 | 57 / 44 px |
| 320 px | [Closed](before-320.jpg), [open](before-320-open.jpg) | [Closed](live-320.jpg), [open](live-320-open.jpg) | 314 / 314 | 57 / 44 px |

The brand and page heading aligned at all seven widths. The loaded account avatar, 16 px brand, and 15 px control labels remained visible with both layouts. At 700 px the open menu had exactly one Repositories link, one Profile settings link and one Sign out button. The closed menu exposed none of its controls. Tab reached Repositories, Profile settings, Sign out and then the first page control, closing the panel and showing a focus outline throughout. Escape from Profile settings returned focus to the toggle. The 320 px open panel also showed exactly one of each destination and operation, with no page overflow. The desktop open panel showed one Profile and one Sign out control. The menu closed when Profile navigation activated.

### Live routes and installation scope

| Surface | Authenticated observation and capture |
| --- | --- |
| Connected Repositories | The selected existing installation and its actual repository list loaded. [Screenshot](live-1440.jpg) |
| Repository Pull Requests | `DhyanMehta/httpx` showed its open PR and the existing completed review #79. [Screenshot](live-pull-requests.jpg) |
| Code Health Analytics | Existing metrics and the weighted findings chart loaded. [Screenshot](live-analytics.jpg) |
| Agent Fleet | Loaded review history and named agent outcomes were visible. [Screenshot](live-agent-fleet.jpg) |
| Review Detail | Saved review #79 opened at its canonical URL and exposed the scoped link back to its repository. [Screenshot](live-review-79.jpg) |
| Installation Settings | The selected installation's saved settings and standards metadata loaded. [Screenshot](live-installation-settings.jpg) |
| Profile Settings | The existing identity and review automation policy loaded and the Profile link was marked current. [Screenshot](live-profile-settings.jpg) |

The scoped repository URL supplied the installation ID. The header carried it through Profile and back to Connected Repositories. Browser Back restored the same installation and Settings tab. Forward restored the scoped Profile route. The repository picker still showed the original installation after returning to the list. The Repositories link identified the current page on the list and the current section on Review Detail. The six additional surfaces each measured 314 px of document scroll width on 314 px of available width at the 320 px viewport. The live account had one selectable installation. The previous automated two-installation coverage remains applicable.

### Regression and files

This was environment recovery and live verification. Only this report and the 17 new `live-*.jpg` files linked in the tables above changed. The previous screenshots and all pre-existing source changes were preserved. Branch `codex/durable-review-pipeline` stayed at `dc9b6af` with an empty index. `git diff --check` passed. The focused authentication, navigation and read-flow suite was rerun and passed 56 tests in eight files. With no source changes, the earlier 137-test full suite and successful TypeScript/Vite production build still cover this implementation.

Physical touch and screen-reader speech were untested. Long-login and signed-out layouts retain the prior isolated evidence. Sign out remained covered by the earlier isolated test so the active session stayed intact.

**GO for Phase 2b approval.** The outstanding authenticated checks passed. Phase 2b can begin after separate user approval.
