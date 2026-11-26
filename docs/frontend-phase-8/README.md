# Phase 8 frontend acceptance and corrections

**Decision for November 26, 2026 — GO for release-readiness review.** All seven authenticated journeys completed. The final replay recorded 111 application GET attempts, 74 HTTP 200 responses, 37 cancellations and zero workflow writes. The final suite passed 276 tests across 35 files. The production build passed. Release approval remains pending. Physical touch and screen-reader speech remain untested.

[Screenshot gallery · 126 captures](evidence/gallery.md) · [Authenticated requests](evidence/final-requests.json) · [Journey checkpoints](evidence/final-journeys.json) · [Original audit](../FRONTEND_SCREENSHOT_AUDIT_2026-11-23.md) · [Master plan](../../tasks/plan.md)

## Baseline and scope

The checkout was on `codex/durable-review-pipeline` at `dc9b6af4149764ae66e2ca10974c151a6bf819a0`, one commit ahead of its tracking branch. The index was empty. The working tree already contained 48 modified tracked files and untracked frontend components, tests, milestone reports, screenshots and unrelated documents. The audit used that working implementation, including Phase 7. The original audit, project rules, plan, checklists and Phase 1–7 reports informed the checks below.

Live reads used the existing signed-in session, installation 161715271, the local Vite frontend and FastAPI. The application returned HTTP 200 for `GET /auth/me`. A browser guard blocked non-GET application requests during the authenticated walkthroughs. Administrative writes, review triggers, auto-fix decisions, permission changes and authentication exchanges were exercised with isolated responses. The worker remained stopped. No backend, dependency, database, API contract or Git index changes were made by this phase.

## Route, screen and responsive coverage

Each gallery row contains a capture at **1920 × 1080, 1440 × 900, 1024 × 768, 768 × 1024, 700 × 900, 390 × 844 and 320 × 760**. The browser measured document client and scroll widths separately, including the space taken by a scrollbar. Across 112 screen/viewport combinations and 21 additional disclosure measurements, none had document overflow or a sampled control outside the document. The 700 px account menu and 320 px review section chooser have additional open-state captures. [Screen geometry](evidence/responsive.json) · [Disclosure geometry](evidence/disclosures.json) · [Gallery](evidence/gallery.md)

| Route or screen | State and evidence source | What was verified |
|---|---|---|
| `/` | Signed-out fixture, separate browser context | Landing content, single sign-in action in its context, specialist descriptions and scope of footer claims. |
| `/auth/callback` | Incomplete callback fixture | Recovery heading and action, keyboard access, meaningful status. Callback exchange and safe protected returns covered by auth tests. |
| `/auth/install`, onboarding | Live cancelled return, isolated signed-in account with no installations | Recovery and onboarding remain reachable. No GitHub installation or authorization was submitted. |
| `/repos` | Authenticated | One effective installation selector, repository count wording, search, reset, refresh, access management, primary scoped link and secondary GitHub destination. Empty and access-loss states have separate fixtures. |
| `/repos/:owner/:repo` | Authenticated httpx PR #1 | Three repository destinations. Active view survives navigation. Existing review precedes the deliberate rerun. Revision and delivery remain readable. |
| `/reviews/:id` overview | Authenticated #79 and #90 | Recorded review, repository, PR and revision, distinct analysis, evidence and delivery states. Browser Back and Forward retain scope. Legacy PR resolution also covered by integration tests. |
| Findings and filters | Authenticated #79, #90 | High filter reduced #79 to 1 of 16. Finding #715 opened by fragment and survived reload. Code, paths, citations and long identifiers have fixture coverage. |
| Agent results and execution | Authenticated #79, #90 | Recorded outcome, execution, missing evidence, accepted findings and scanner detections remain distinguishable. Timeline preserves attempts, event order and accessible detail disclosures. |
| Delivery, Markdown, auto-fix | Authenticated saved report #79, pending proposal #29, approved #82 | Delivery and analysis have separate labels. Saved report loads on demand. Proposal inspection issued no decision and makes no merge claim. |
| `?tab=analytics` | Authenticated httpx and flask-task-api | Outcome hierarchy, exact chart equivalents, historical links, timestamp disclosures and data availability. All 24 sampled rows reconciled. |
| `?tab=agents` | Authenticated httpx, saved #71 | Historical terminal denominator, issues and linked review, expandable scanner evidence and continuation. Active/unavailable branches also covered by isolated tests. |
| `/settings/installation` | Authenticated installation and isolated admin/member states | Single scope, coding standards, historical version meaning, labelled file input and confirmation. Legacy repository settings bookmark resolved to the validated installation. |
| `/profile` | Authenticated with scoped return | Shared policy impact, administered installations, draft/save distinction and scoped Back. Mixed policy, no-op, concurrency and uncertain writes covered by fixtures. |

### Density measurements

The following before/after values are Phase 8 DOM measurements of the same httpx workspace. Y coordinates are CSS pixels from the top of the document at its initial scroll position. [Baseline](evidence/before-density.json) · [Final geometry](evidence/responsive.json) · [Review measurements](evidence/review-density.json)

| Measure | 320 px before → final | 1440 px before → final |
|---|---:|---:|
| First PR top | 506 → 462 | 354 → 354 |
| View Review top | 753 → 709 | 472 → 472 |
| View Review target | 139 × 44 → 139 × 44 | 139 × 40 → 139 × 40 |
| First analytics history record height | 393 → 338 | 133 → 133 |
| First specialist card height | 336 → 296 | 454 → 454 |
| Four-specialist section height | 1562 → 1402 | 494 → 494 |

At 320 × 760 the PR action now ends at y=753. For #79 and #90 the final overview begins at y=328 and is 401 px high. The first finding starts at y=1138. At 1440 px the corresponding values are 282, 205 and 768. The mobile section chooser provides direct access to findings. The first finding still requires scrolling when reading from the top. These are direct Phase 8 measurements. The Phase 6 desktop screenshot estimates were excluded.

Long synthetic repository, branch and PR names fit at 320 px. A long code line occupied 8449 px inside its 262 px local scrolling region while the document stayed 320 px wide. Desktop tabs transferred focus to the native select when resized. The selector offered Pull Requests, Analytics and Agent History. Each applicable repository view had a single effective installation selection and account control. [Browser fixtures](evidence/browser-engines.json) · [Keyboard observations](evidence/keyboard.json)

## Original finding traceability

Every row identifies a current implementation owner under `frontend/src`, an executed suite under `frontend/src/test`, and rendered evidence in the gallery. **Verified** refers to the specific behavior in the row. A fixture or environmental limitation is identified where the live accounts cannot demonstrate a state. The affected suites ran with their existing request and authorization assertions.

| Finding | Implementation and observed result | Regression suite | Browser evidence and status |
|---|---|---|---|
| CG-UX-001 | `dashboard/PullRequestRow`, `prActions`, `reviews/TriggerReview` give a current completed review the primary link and retain a secondary rerun button. | prWorkspace, prActions, writeFlows | Verified on #79. View Review issued zero POSTs. Rerun tested with mocks. |
| CG-UX-002 | `dashboard/AnalyticsTab`, `AnalyticsHistory` distinguish missing coverage, terminal outcome and measured counts. | analytics | Verified on both repositories, including #65, #72 and #90. |
| CG-UX-003 | `layout/AppLayout`, `pages/HomePage` removed the unsupported compliance claim. | Navbar, finalFlow | Verified in the rendered shell and landing fixture. No organizational credential was assessed. |
| CG-UX-004 | `pages/RepoDashboardPage`, `layout/ContextBar` consolidate repository identity and replace the permanent sidebar. | repositoryNavigation | Verified on three live destinations at seven widths. |
| CG-UX-005 | `index.css`, `common/Button`, `layout/AppLayout` supply text, target and focus roles, including the offline status. | Button, SharedFeedback | Verified sampled text pairs, geometry and zoom. Actual speech untested. |
| CG-UX-006 | `dashboard/AnalyticsHistory` uses tabular desktop history and labeled mobile records. | analytics | Verified at 320 and 1440 including long status and coverage text. |
| CG-UX-007 | `dashboard/WeightedFindings` links the bounded score plot to exact values and marks missing observations. | analytics | Verified #65 omitted as an observation and #72 measured at zero. |
| CG-UX-008 | `dashboard/AgentsTab`, `AgentOutcomeChart` describe a loaded historical sample and count terminal outcomes. | agentHistory, readFlows | Verified on five live terminal reviews and continuation to ten. |
| CG-UX-009 | `common/ScopedRefreshStatus`, `FriendlyTimestamp`, `dashboard/LoadedReviewHistory` identify the refreshed data and offer exact times. | ScopedRefreshStatus, FriendlyTimestamp, prWorkspace | Verified on list, PR, history, analytics, standards and policy. Retry states exercised in isolation. |
| CG-UX-010 | `common/Button`, `pages/RepoListPage`, `dashboard/PullRequestRow` differentiate primary destination, refresh and explicit mutation. | Button, repositoryList, writeFlows | Verified on live repository and review links. All writes isolated. |
| CG-UX-011 | `dashboard/AnalyticsTab` groups review outcomes, risk, execution evidence and fix activity. | analytics | Verified across both repository samples. |
| CG-UX-012 | `dashboard/AgentOutcomeChart`, `AgentHistoryRecord` group specialist counts, recorded issue and expandable evidence. | agentHistory | Verified #71, four specialist summaries and collapsed/expanded history. |
| CG-UX-013 | `pages/InstallationSettingsPage`, `RepoDashboardPage`, `ProfilePage` expose installation ownership and shared policy scope. | repositoryNavigation, profileMode | Verified direct route, legacy bookmark, profile and Back. |
| CG-UX-014 | `pages/RepoListPage` gives each repository one primary in-app destination and a distinct external link. | repositoryList | Verified on authenticated list → httpx. |
| CG-UX-015 | `pages/RepoListPage` labels the GitHub combined open issues and pull requests count. | repositoryList | Verified rendered list. Exact open PR totals are unavailable from this field. |
| CG-UX-016 | `pages/RepoListPage`, `common/SearchInput` expose the label, filtered count, clear action and scoped empty state. | repositoryList, SearchInput | Verified live search/refresh. Empty and access-loss states isolated. |
| CG-UX-017 | `dashboard/prActions`, `PullRequestRow`, `reviews/TriggerReview` keep revision, history reliability and mutation state independent. | prActions, prWorkspace, reliabilityFlows | Verified matching #79. Active, uncertain, bounded and denied combinations isolated. |
| CG-UX-018 | `common/FriendlyTimestamp`, `dashboard/AnalyticsHistory` format time, expose its exact value, and label findings and index. | FriendlyTimestamp, analytics | Verified exact UTC disclosure, both repositories and mobile records. |
| CG-UX-019 | `common/InstallationPicker`, `layout/ContextBar` show review mode at installation scope and repository identity once. | repositoryNavigation | Verified desktop and mobile PR, Analytics and Agent History. Multiple installations isolated. |
| CG-UX-020 | `reviews/ReviewAgentResults`, `dashboard/AgentHistoryRecord` separate outcome, execution, accepted counts and raw detections. | findingsEvidence, agentHistory | Verified #79 missing coverage and #90 complete coverage. Sensitive-message checks isolated. |
| CG-UX-021 | `dashboard/SettingsTab` leads with active standards, preserves version/chunk details and shows the confirmed receipt. | administration, writeFlows | Verified live active standard. Upload and receipt isolated. |
| CG-UX-022 | `dashboard/SettingsTab`, `common/ConfirmationDialog` implement admin/member behavior, file validation and deliberate reset. | administration, writeFlows | Verified live form and native dialog focus in three browser engines using fixtures. |
| CG-UX-023 | `pages/ProfilePage` separates installation impact from policy editing in a responsive workspace. | profileMode, administration | Verified live wide and narrow layouts. |
| CG-UX-024 | `pages/ProfilePage` distinguishes persisted, draft, unchanged, conflicting and server-confirmed values. | profileMode, writeFlows | Verified current live policy. Save and conflict outcomes isolated. |
| CG-UX-025 | `reviews/FindingCard`, `FindingsList` preserve finding IDs, filter counts, visible evidence and native disclosures. | findingsEvidence, reviewWorkspace | Verified #715 after reload and on browser history navigation. |
| CG-UX-026 | `layout/Navbar` switches the single effective account control at compact widths. | Navbar | Verified open at 700 px, plus one effective control on authenticated captures. |
| CG-UX-027 | `layout/AppLayout`, `common/Tabs`, `pages/RepoDashboardPage` implement skip navigation, tab selection and mobile focus transfer. | Tabs, repositoryNavigation | Verified keyboard skip, ArrowRight, compact chooser and execution section focus. |
| CG-UX-028 | `common/ProtectedRoute`, `EntryPanel`, `pages/AuthCallbackPage` present loading and recoverable auth/installation states. | ProtectedRoute, auth, callbackRecovery | Verified live protected entry/cancelled return. Signed-out, callback and onboarding states isolated. |
| CG-UX-029 | `common/SectionCard`, `SeverityBadge`, `StatusBadge` use static surfaces and textual severity/status labels. | SeverityBadge, SharedFeedback | Verified live finding, PR, analytics and agent surfaces. Screen-reader speech untested. |

## Authenticated journeys and persisted values

| Journey | Observed result |
|---|---|
| A · Search to saved review | Searched for httpx, refreshed the scoped list, opened PR #1 and followed View Review to #79. Back restored the same scoped PR. |
| B · Review evidence | Filtered to High, retained the full 16 count, accessed #715, reloaded, visited agent results, execution and delivery, opened the saved Markdown and inspected auto-fix. |
| C · Analytics | Selected exact chart values locally, opened skipped #65, and returned to the historical table anchor. Both repository datasets matched their metrics responses. |
| D · Agent History | Opened the recorded Quality issue in #71, returned, expanded specialist/scanner evidence locally and loaded five more terminal reviews. |
| E · Administration | From the loaded repository list opened Installation Settings, then scoped Profile. Browser Back restored installation 161715271. |
| F · Legacy settings | The authorized repository bookmark with `tab=settings` resolved to `/settings/installation?installation_id=161715271`. |
| G · History and reload | Browser Forward restored #79 and a fresh load of `/reviews/79#finding-715` restored the addressed evidence. |

For httpx PR #1 the current and reviewed revisions both read `5b2630b1d2b7442718dea99c443513677afc06dd`. Review #79 had 16 findings, one high, four medium and eleven low, a weighted index of 24 and a posted report. Full execution coverage was unrecorded. In the five-terminal Agent History sample, Quality had two OK and three degraded outcomes. #71 contained 16 findings and a degraded Quality outcome. #65 was skipped with zero reported findings and no plotted score observation. [Current PR](evidence/current-pr.json) · [Metrics comparison](evidence/analytics-comparison.json)

For flask-task-api, #72 completed with a measured index of zero, a degraded Security outcome and unavailable full coverage. #90 completed with three findings, index three, complete coverage and a posted report. Its execution timeline had 19 events. #29 had a pending approval, and #82 recorded approval, eleven findings and thirteen events. Approval describes the saved proposal decision. The UI did not claim a merge. Historical standards and citations continue to refer to the saved review version. Findings tests cover advisory/verified distinctions, incomplete evidence and unavailable historical versions.

The comparison reconciled all ten httpx and fourteen flask-task-api rows against their server response, including ID, outcome, finding count, weighted index, coverage wording and whether the point should be plotted. The requested analytics sample bound was 50. The weights for critical, high, medium, low, info and unknown were 10, 5, 2, 1, 0 and 0. No independent health score was introduced.

## Resource behavior, permissions and mutations

The final trace counts application fetch attempts. It includes development lifecycle cancellations and explicit refreshes. Filtering kept the cumulative count at 17, section navigation after reload at 24, and opening saved Markdown increased it from 24 to 25. Inspecting exact analytics values stayed at 31. Expanding historical scanner evidence stayed at 46. Loading more history increased the count from 46 to 57. These observations distinguish local interactions from requested reads. [Final checkpoints](evidence/final-journeys.json) · [Requests with methods, paths and status](evidence/final-requests.json)

The earlier exploratory recording had 118 attempts, including 74 successes, 39 cancellations, four errors without an HTTP status and one still pending at export. A pointer activation during an intermediate navigation reached GitHub account selection. No authorization was submitted. The final replay selected the settled in-app destination by keyboard and reached the scoped settings page. Fresh loads of seven authenticated routes recorded zero console warnings and errors. The earlier development recording includes warnings during module hot replacement. [Exploratory requests](evidence/journey-requests.json) · [Initial console](evidence/console.json) · [Fresh-load console](evidence/clean-console.json)

The API client retries eligible reads. The shared resource retains a 30-second freshness window, cancels unused requests, discards obsolete responses and clears restricted data on access loss. Review monitoring uses 5-second active intervals. Pending delivery uses a 15-second interval bounded by 180 visible seconds. Polling pauses offline or hidden and respects transient backoff of 10, 20, 40 and 60 seconds and server Retry-After. Agent History starts at five records, caps retrieval at 200 and uses two concurrent detail reads. Tests exercise bounded continuation, partial detail failure, recovery and subscriber changes. See `api/resources.ts`, `api/client.ts`, `api/polling.ts`, `api/writes.ts` and `dashboard/AgentsTab.tsx`.

| Isolated operation | Existing request contract and guard verified | Tests |
|---|---|---|
| Trigger review | Bodyless POST `/installations/{id}/repos/{owner}/{repo}/pulls/{n}/review`. Server resolves head and requires repository write permission. A validated accepted review ID selects the canonical destination. | writeFlows, prActions, prWorkspace, reliabilityFlows |
| Create fix | Bodyless POST `/reviews/{id}/autofix`. Saved review, fork, head, busy and uncertain state guard the operation. | reviewOperations, writeFlows |
| Decide fix | Bodyless POST `/reviews/{id}/autofix/approve` or `/reject`. Existing conflict and reconciliation behavior retained. Rejection does not imply deletion. | reviewOperations, writeFlows, reliabilityFlows |
| Upload/reset standards | POST multipart with field `file`, or bodyless DELETE at `/installations/{id}/standards`. Scoped admin capability, validation, confirmation, cancel, receipt and uncertain outcome. | administration, writeFlows, repositoryNavigation |
| Save shared policy | PATCH `/profile/review-mode` with `{ review_mode, version }`. Administered installations, version conflicts, deliberate save and persisted result verified. | profileMode, writeFlows |
| Entry, isolation and late responses | Explicit installation ID has precedence. Invalid/suspended scope, denied repository, delayed reads, member permissions, session changes and canonical historical identity are covered. Busy/uncertain writes are never automatically replayed. | auth, callbackRecovery, identity, repositoryNavigation, reliabilityFlows, polling, writeFlows |

The frontend retained the backend authorization boundary. Installation admin status alone does not grant repository write permission. Endpoints were checked against the existing backend installation, review, auto-fix, standards, metrics, auth and profile handlers. No live write was used to establish a passing result.

## Accessibility and platform checks

| Check | Evidence and result |
|---|---|
| Keyboard, focus and landmarks | The first skip link moved focus to `main-content`. ArrowRight selected and focused Analytics. Resizing with focus in repository navigation transferred it to the select with Analytics selected. The mobile review chooser focused the execution section. Header account disclosure, named controls, current location and heading relationships were inspected through the browser accessibility tree and integration queries. [Keyboard results](evidence/keyboard.json) |
| Links, forms and disclosures | View Review is a native link and Run Another Review is a named button. Scoped selects have visible labels. Finding summaries have a visible chevron and native disclosure state. Exact timestamps, issue history, scanner details and report controls work from the keyboard. File validation associations, busy state, actionable errors, Cancel and impact text were exercised by administration and feedback tests. |
| Confirmation | In Chromium 151.0.7922.34, Firefox 153.0 and WebKit 26.4, the fixture reset dialog focused Cancel on open. Escape closed it and restored focus to Reset to defaults. Each engine rendered the PR, saved review, analytics, agent history, settings and profile fixtures at phone width without document overflow. These are browser-engine fixture results. [Engine results](evidence/browser-engines.json) |
| Contrast and typography | The lowest of 24 unique sampled opaque rendered text/background pairs was **6.29:1**, white on the primary action fill. Light link text on a raised panel measured 7.95:1. The measurements cover sampled text and backgrounds. Gradients, images, OS controls and all possible transient states were outside this calculation. [Measured pairs and screens](evidence/contrast.json) |
| Reflow and preferences | Native Chrome at 200% zoom changed the CSS viewport from 1422 to 711 px and DPR from 1 to 2. The profile document still fit. Chromium forced colors preserved a solid 3 px focus outline. Emulated reduced motion yielded a 0.00001-second transition. [Native zoom](evidence/native-zoom.json) · [Preference capture](evidence/forced-colors-profile.png) |
| Charts, tables and status | Analytics supplies exact values, labeled fields and historical links. Compact records retain header associations. Static severity labels do not each announce a live status. Scoped refresh, access errors and offline status have distinct feedback. Semantic assertions and tree inspection verify markup. |
| Automated scan | The installed Lighthouse 13.6.0 accessibility scanner scored 1.00 on nine fixture surfaces covering entry, repositories, PR, review, analytics, history, settings and profile. Rules outside the sampled state are marked inapplicable. [Per-rule results](evidence/lighthouse.json) |
| NOT TESTED · physical touch | No attached physical phone or tablet was available. Browser viewports, control geometry and keyboard activation were exercised. |
| NOT TESTED · speech | NVDA was unavailable. Narrator was installed, but the available desktop/browser interface exposed no speech output to verify. Spoken order, announcement timing and the native file-picker experience remain manual checks. |
| NOT TESTED · native Safari / iOS | The installed WebKit runtime ran the fixture matrix. A physical Apple device and native Safari were unavailable. |

## Corrections made during Phase 8

Severity describes the consequence before correction. No critical defect was confirmed. File groups below use the exact filenames in the change inventory.

| Severity | Original problem and cause | Correction | Verification and result |
|---|---|---|---|
| High | Multiple consumers shared a resource entry. A subscriber that switched installations could leave its newer reader attached to the old key. Refreshing the surviving subscriber could load the wrong installation. | `resources.ts` binds each subscribed reader to its key and selects a remaining reader on unsubscribe. | An isolated two-subscriber test first returned the second installation for the first. It now retains the first installation. Existing delayed-access and access-loss cases passed. |
| Medium | Aborting a refresh on last unsubscribe retained a cached snapshot with `loading=true`. A within-window revisit could leave the refreshed control busy. | `resources.ts` clears abandoned loading while keeping the last authorized data. | Reproduced before the change. The revisit test now preserves the cached result and clears busy state. |
| High | A late mutation result after session reset could clear a newer operation sharing the same key or hand its accepted result to an obsolete caller. | `writes.ts` checks that the pending operation still owns the key before publishing, reconciling or returning an accepted result. | Mocked late success and failure preserve the newer lock. Existing deliberate POST, scope, uncertainty and no-replay tests passed. |
| High | Review diagnostics and shared feedback could interpolate credential-bearing strings, including JSON-style key/value errors. Collapsed DOM could still contain the text. Some raw scanner messages contained matched content. | Centralized diagnostic handling across review outcomes, summaries, scanner evidence and common read/write feedback. Gitleaks and unknown scanner messages are suppressed. Known Bandit/Semgrep explanations pass through redaction. The compatibility agent card uses the same message rule. | Synthetic markers are absent from rendered DOM in expanded and collapsed evidence, terminal PR diagnostics, completed summaries and error feedback. Safe rule explanations, counts, recovery controls and locations remain available. |
| Medium | The PR title followed a supplied external URL rather than the authorized repository and PR identity. OAuth navigation accepted destinations on GitHub beyond the expected authorization endpoint. | `PullRequestRow.tsx` constructs the PR link from the validated repository and positive safe PR number. `AuthContext.tsx` checks the expected HTTPS origin, path and absence of embedded credentials. | prWorkspace and Navbar tests cover mismatched destinations, wrong path, and alternate port. Existing valid login and canonical review navigation passed. |
| Medium | Narrow context wrapping put the primary result below the first 320 × 760 viewport. Single-column label/value placement made mobile analytics records and specialist cards unnecessarily tall. | `InstallationPicker.tsx`, `RepoDashboardPage.tsx`, `AnalyticsHistory.tsx` and `AgentOutcomeChart.tsx` rebalance compact control spacing and label/value layout. | Same-device before/after geometry shows a 44 px improvement in action position, 55 px shorter history row and 160 px shorter specialist section. Desktop comparator geometry held. |
| Low | Offline feedback used a smaller visual role. The HTML referenced a missing shield asset, causing a non-image response for the favicon. | `AppLayout.tsx` uses the support role for offline status. Added the local `shield.svg` at the referenced path. | Shared feedback and full suites passed. The production smoke read the SVG and rendered both entry and repository screens. |

The security review covered route and external link construction, text rendering, server-authorized reads/writes, data retained after access loss, diagnostics and evidence files. A scoped source search found no raw HTML insertion or dynamic evaluation in the frontend. Targeted checks on source and textual milestone evidence found no matches for the private-key and credential formats searched. These checks have finite pattern coverage. Request ledgers contain application methods, paths, selected parameters and result statuses. They omit cookies, OAuth codes, request headers and session tokens. Saved screenshots include authorized repository identities and review information.

## Exact Phase 8 change inventory

The following paths are relative to the repository root. Earlier uncommitted milestone files remain part of the checkout. The list identifies the files edited or added for this phase specifically.

| Directory | Files |
|---|---|
| `frontend/public/` | `shield.svg` |
| `frontend/src/api/` | `resources.ts`, `writes.ts` |
| `frontend/src/context/` | `AuthContext.tsx` |
| `frontend/src/components/common/` | `AsyncState.tsx`, `InstallationPicker.tsx`, `ScopedRefreshStatus.tsx`, `WriteFeedback.tsx` |
| `frontend/src/components/dashboard/` | `AgentOutcomeChart.tsx`, `AnalyticsHistory.tsx`, `PullRequestRow.tsx` |
| `frontend/src/components/layout/` | `AppLayout.tsx` |
| `frontend/src/components/reviews/` | `diagnosticText.ts`, `ReviewAgentResults.tsx`, `ReviewOverview.tsx`, `ReviewPresentation.tsx` |
| `frontend/src/pages/` | `RepoDashboardPage.tsx` |
| `frontend/src/test/` | `findingsEvidence.test.tsx`, `Navbar.test.tsx`, `polling.test.tsx`, `prWorkspace.test.tsx`, `reviewWorkspace.test.tsx`, `SharedFeedback.test.tsx`, `writeFlows.test.tsx` |
| Documentation | `tasks/todo.md`, `UI_REGRESSION_CHECKLIST.md`, this `docs/frontend-phase-8/README.md` and the [complete artifact inventory](evidence/manifest.txt) under `docs/frontend-phase-8/evidence/` |

## Final engineering checks and recommendation

| Gate | Final result |
|---|---|
| Affected regression tests | The cache and stale mutation fixes have dedicated regression cases. After the final privacy change the review workspace, findings and read-flow suites passed all 35 focused tests. Existing assertions on authorization, requests, numerical results and accepted IDs were retained. |
| Full frontend suite | `npm test` passed **276/276 tests across 35 files**. The previous milestone recorded 266 tests. |
| Type checking and production build | `npm run build` passed `tsc -b` and Vite 6.4.3. 1977 modules transformed. Main JS 438.26 kB, 130.26 kB gzip. CSS 59.49 kB, 14.86 kB gzip. The project has no configured lint script. |
| Production asset smoke | Disposable Chromium loaded the unmodified built HTML, JS, CSS, local fonts and SVG, rendering the signed-out landing and an isolated signed-in repository list. No unexpected requests or unexpected console warnings/errors. The synthetic signed-out session deliberately answered 401. The live harness was removed from the frontend entry and build inputs. [Production smoke](evidence/production-smoke.json) |
| Diff and scope | `git diff --check` passed. The tracked frontend entry matched its original version. Build output contained no temporary verification entry. The package manifests and API contracts were untouched during Phase 8. |

**Remaining release blockers found in the exercised scope: none.** The mobile first-finding position and the manual device, speech and native browser gaps above remain visible to the sign-off reviewer. No formal WCAG or compliance certification is asserted. Release-readiness sign-off is a separate decision.
