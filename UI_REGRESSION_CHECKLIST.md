# CodeGuardian AI frontend regression checklist

The Phase 8 full suite passed 276 Vitest tests across 35 files. Each milestone retains its own results. API write tests use isolated responses. The final authenticated replay recorded 111 GET attempts and zero writes. [Phase 8 evidence and limitations](docs/frontend-phase-8/README.md)

**Evidence key**

- **Implemented and verified** means the listed acceptance checks passed. Product review is recorded separately.
- **Implemented, acceptance outstanding** applies when a required check is missing. **Not started** refers to redesign work that has yet to begin.
- **PASS** applies only to the behavior and evidence in its row. Pre-redesign functionality can have passing regression tests while its redesign is still pending.
- **Fixture** means isolated inputs and responses. **Live** means the authenticated running application. **Not tested** means no result was obtained for that check.

---

## 1. Backend and API Contract Protection (Strict Zero-Touch)

| Item | Contract / Endpoint | Status | Verification Evidence / Reference |
|---|---|---|---|
| Zero Backend Files Modified | `backend/**` | **PASS** | `git diff --stat backend` returns 0 tracked changes. Pre-existing untracked backend documentation is excluded. |
| User Profile Session | `GET /auth/me` | **PASS** | `src/test/auth.test.tsx`, `src/test/callbackRecovery.test.tsx` |
| GitHub OAuth Initiation | `GET /auth/github/login` | **PASS** | `src/test/finalFlow.test.tsx` |
| GitHub OAuth Callback | `POST /auth/github/callback` | **PASS** | `src/test/callbackRecovery.test.tsx` |
| GitHub App Install Return | `GET /auth/installation-url` | **PASS** | `src/test/finalFlow.test.tsx` |
| Installations List | `GET /installations` | **PASS** | `src/test/reliabilityFlows.test.tsx` |
| Connected Repositories | `GET /installations/:id/repos` | **PASS** | `src/test/readFlows.test.tsx`, `src/test/reliabilityFlows.test.tsx` |
| Pull Requests List | `GET /installations/:id/repos/:owner/:repo/pulls` | **PASS** | `src/test/readFlows.test.tsx`, `src/test/writeFlows.test.tsx` |
| Reviews List | `GET /reviews?installation_id=:id&repo=:repo` | **PASS** | `src/test/readFlows.test.tsx`, `src/test/polling.test.tsx` |
| Single Review Detail | `GET /reviews/:id` | **PASS** | `src/test/readFlows.test.tsx`, `src/test/reliabilityFlows.test.tsx` |
| Review Markdown Report | `GET /reviews/:id/report` | **PASS** | `src/test/reliabilityFlows.test.tsx` |
| Code Health Metrics Trends | `GET /metrics/trends?installation_id=:id&repo=:repo` | **PASS** | `src/test/readFlows.test.tsx` (shows single point & both coverage limitations) |
| Installation Settings | `GET /installations/:id/settings` | **PASS** | `src/test/writeFlows.test.tsx` |
| Coding Standards Status | `GET /installations/:id/standards` | **PASS** | `src/test/writeFlows.test.tsx` |
| Coding Standards Upload | `POST /installations/:id/standards` | **PASS** | `src/test/writeFlows.test.tsx` ("uploads multipart standards and resets metadata") |
| Coding Standards Reset | `DELETE /installations/:id/standards` | **PASS** | `src/test/writeFlows.test.tsx` |
| Auto-Fix Branch Creation | `POST /reviews/:id/autofix` | **PASS** | `src/test/writeFlows.test.tsx` ("creates one fix branch, displays skipped reasons") |
| Auto-Fix Approval | `POST /reviews/:id/autofix/approve` | **PASS** | `src/test/writeFlows.test.tsx` ("persists the decision") |
| Auto-Fix Rejection | `POST /reviews/:id/autofix/reject` | **PASS** | `src/test/writeFlows.test.tsx` ("rejects without claiming the branch was deleted") |
| Manual Review Trigger | `POST /installations/:id/repos/:owner/:repo/pulls/:number/review` | **PASS** | `src/test/writeFlows.test.tsx` ("triggers without a body and navigates") |
| Global Policy Broadcast | `PATCH /profile/review-mode` | **PASS** | `src/test/profileMode.test.tsx` ("saves one policy for every administered installation") |

---

## 2. Core Agent Identity Verification (4 Platform Specialists)

| Identifier | Presentation Name | Scanners & Tools | Status | Verification Evidence |
|---|---|---|---|---|
| `security` | **Security Agent** | Semgrep, Bandit, Gitleaks | **PASS** | `HomePage.tsx`, `ReviewPresentation.tsx`, `AgentTimeline.tsx`, `AgentsTab.tsx` |
| `quality` | **Quality Agent** | ChromaDB RAG, AST Gatekeeper, Standards Alignment | **PASS** | `HomePage.tsx`, `ReviewPresentation.tsx`, `AgentTimeline.tsx`, `AgentsTab.tsx` |
| `test_gap` | **Test Gaps Agent** | AST Function Scan, Static Test Discovery, Starter Unit Stubs | **PASS** | `HomePage.tsx`, `ReviewPresentation.tsx`, `AgentTimeline.tsx`, `AgentsTab.tsx` |
| `documentation` | **Documentation Agent** | AST Docstring Scan, Signature Verification, Replacements | **PASS** | `HomePage.tsx`, `ReviewPresentation.tsx`, `AgentTimeline.tsx`, `AgentsTab.tsx` |
| Inaccurate names (`Architecture`, `Performance`, `Compliance`, `Dependencies`) | Removed from all UI labels & CSS tokens | None | **PASS** | Verified absent from `frontend/src` codebase |

---

## 3. Routing, Navigation & State Integrity

| Route / State Behavior | Expected Pattern | Status | Verification Evidence |
|---|---|---|---|
| Public Home / Landing | `/` | **PASS** | Chrome DevTools MCP browser inspection across 5 viewports |
| OAuth Callback Handler | `/auth/callback` | **PASS** | `src/test/callbackRecovery.test.tsx` (11 tests pass) |
| Installation Return Handler | `/auth/install` | **PASS** | `src/test/finalFlow.test.tsx`, `src/test/callbackRecovery.test.tsx` |
| User Profile & Global Policy | `/profile` | **PASS** | `src/test/profileMode.test.tsx` |
| Connected Repositories | `/repos`, one scoped workspace link per row, truthful combined count, search with clear recovery | **PASS** | Live navigation and [Phase 3a report](docs/frontend-phase-3a/README.md). Isolated cache and scope coverage in `repositoryList.test.tsx`. |
| Repository Dashboard | `/repos/:owner/:repo` | **PASS** | `src/test/readFlows.test.tsx`, `src/test/reliabilityFlows.test.tsx` |
| Legacy Pull Request Route | `/repos/:owner/:repo/pulls/:number` | **PASS** | `src/test/reliabilityFlows.test.tsx` (resolves legacy route to review ID) |
| Canonical Review Detail | `/reviews/:reviewId` | **PASS** | `src/test/readFlows.test.tsx`, `src/test/reliabilityFlows.test.tsx` |
| Catch-All Fallback | `* -> /` | **PASS** | `src/App.tsx` redirects unhandled paths to `/` |
| Repository workspace navigation | One contextual region, horizontal tabs from 768 px, native Repository view chooser below 768 px | **PASS** | [Phase 2b live layout and keyboard checks](docs/frontend-phase-2b/README.md#j-accessibility-improvements) and `repositoryNavigation.test.tsx` |
| Compact global account menu | One account disclosure with anchored Profile and Sign out | **PASS** | Authenticated 700 px menu and Escape check in [Phase 2b](docs/frontend-phase-2b/after-account-menu-700.jpg) |
| Tab Query Param Preservation | `?tab=pulls\|analytics\|agents` | **PASS** | `src/test/reliabilityFlows.test.tsx` ("normalizes invalid tab while retaining params") |
| Repository installation scope | One picker, explicit scope, revalidate access on switch, scoped return link | **PASS** | Live history and reload plus isolated invalid, suspended, inaccessible and delayed-read coverage in [Phase 2b](docs/frontend-phase-2b/README.md#h-route-and-query-parameter-preservation) |
| Installation Settings | Protected `/settings/installation?installation_id=ID`, also reached through a repository-validated legacy `tab=settings` bookmark | **PASS** | [Phase 2c live and fixture evidence](docs/frontend-phase-2c/README.md), including history replacement, denied access and delayed writes |

---

## 4. Component Test Hooks & Selector Preservation

| Component | Selector / Contract | Status | Verification Reference |
|---|---|---|---|
| `Button` | `bg-action`, `bg-action-secondary`, `bg-neutral-100`, `border-control-border` for the respective primary, secondary, inverted and outlined variants | **PASS** | `src/test/Button.test.tsx` (4/4 tests pass) |
| `SeverityBadge` | Static text, `bg-risk-*-bg`, decorative SVG, accessible label in icon-only mode | **PASS** | `src/test/SeverityBadge.test.tsx` (8 cases) |
| `Tabs` | `role="tablist"`, `role="tab"`, `aria-selected`, `aria-controls`, active `text-link`, Arrow/Home/End navigation | **PASS** | `Tabs.test.tsx`, `repositoryNavigation.test.tsx`, and authenticated keyboard checks |
| `StatCard` | Title, value, description, icon rendering | **PASS** | `src/test/StatCard.test.tsx` (3 cases) |
| `ProgressBar` | `role="progressbar"`, descriptive name | **PASS** | `src/test/ProgressBar.test.tsx` (2/2 tests pass) |
| `SearchInput` | Border, clear icon, search callback | **PASS** | `src/test/SearchInput.test.tsx` (2/2 tests pass) |
| `IconButton` | Focus ring, accessible label | **PASS** | `src/test/IconButton.test.tsx` (2/2 tests pass) |
| `AgentOutcomeChart` | `role="img"`, exact label (`Security: 0 ok, 1 degraded, 0 failed, 0 unrecorded`) | **PASS** | `src/test/finalFlow.test.tsx` |

---

## 5. Viewport and responsive evidence

The five landing-page rows record the earlier public-page inspection. The authenticated rows identify the milestone actually exercised.

| Viewport | Dimensions | Live Browser Inspection | Status |
|---|---|---|---|
| **Desktop XL** | 1440 × 900 px | Landing page rendered, verified zero horizontal overflow, hero centered, clean navbar. | **PASS** |
| **Desktop Standard** | 1280 × 800 px | Balanced layout, proportional cards, zero clipping. | **PASS** |
| **Tablet Landscape** | 1024 × 768 px | Fluid container width, 2-column agent card grid. | **PASS** |
| **Tablet Portrait** | 768 × 1024 px | Earlier landing-page inspection recorded a stacking agent grid. Current account navigation is covered separately below. | **PASS** |
| **Mobile** | 390 × 844 px | Single-column stack, zero overflow (`hasHorizontalOverflow: false`), legible fonts. | **PASS** |
| **Authenticated Repository Workspace** | 1920, 1440, 1024, 768, 700, 390 and 320 px | Phase 2b captured the same live repository before and after at six widths. Its then-current four views were reachable at 320 px. Fixture access states documented separately. | **PASS** ([screenshot gallery](docs/frontend-phase-2b/README.md#n-authenticated-before-and-after-evidence)) |
| **Authenticated Installation Settings** | 1920, 1440, 1024, 768, 700, 390 and 320 px | One installation selector and equal document/client widths. Three repository destinations and a separate settings link. | **PASS** ([Phase 2c evidence](docs/frontend-phase-2c/README.md)) |
| **Authenticated Connected Repositories** | 1920, 1440, 1024, 768, 700, 390 and 320 px | Same five records before and after, equal document/client widths, 40 px desktop and 44 px compact row actions, keyboard and clear-search recovery. | **PASS** ([Phase 3a evidence](docs/frontend-phase-3a/README.md)) |

---

## 6. Accessibility evidence by surface

| Check | Evidence | Result |
|---|---|---|
| Text contrast | Phase 1 measured muted metadata at 8.81:1 on its panel. Phase 2b measured 13.09:1 for inactive repository navigation on canvas. | Passed for the sampled surfaces |
| Control boundary | Phase 2b measured the mobile chooser border against its fill at 4.80:1. The control border token is `#71839B`. Decorative dividers serve a different purpose. | Passed for that control |
| Keyboard focus | `.control-focus:focus-visible` uses a 2 px solid `--color-focus` outline (`#A5B4FC`) with 3 px offset. Keyboard focus and Enter verified on the 320 px settings link. | Live, Phase 2c |
| Control size | Settings selector and refresh measured 40 px tall from 768 px and 44 px below 768 px. | Live, Phase 2c |
| Reduced motion | `index.css` includes a reduced-motion media query. | Source evidence |
| Screen reader speech, physical touch and complete WCAG conformance | Outside the Phase 2c verification performed. | Not tested |

## 7. Implementation and sign-off

| Phase | Approved scope | Full suite and build at milestone | Evidence and status |
|---|---|---|---|
| 1 | Foundation and first list consumer | 105 passed, build passed | [Implemented and verified](docs/frontend-phase-1/README.md) |
| 1c | Remaining shared foundations | 133 passed, build passed | [Implemented and verified](docs/frontend-phase-1c/README.md) |
| 2a | Global header and shell | 137 passed, build passed | [Authenticated acceptance](docs/frontend-phase-2a/README.md) |
| 2b | Repository navigation and context | 144 passed, build passed | [Authenticated acceptance](docs/frontend-phase-2b/README.md) |
| 2c | Installation settings routing | 156 passed, build passed | [Implemented and verified, awaiting review](docs/frontend-phase-2c/README.md) |
| 3a | Connected Repositories experience | 164 passed, build passed | [Implemented and verified, awaiting review](docs/frontend-phase-3a/README.md) |
| 3b | PR action hierarchy | 134 focused and 194 full tests passed, build passed | [Authenticated at seven widths, saved review opened with zero writes](docs/frontend-phase-3b/README.md) |
| 3c | Scoped freshness and history | 144 focused and 202 full tests passed, build passed | [Authenticated at seven widths, 27 GET requests and zero writes](docs/frontend-phase-3c/README.md) |
| 4a | Review Detail layout, summary and navigation | 138 focused and 215 full tests passed, build passed | [Seven authenticated widths, reviews #79 and #90, 26 GET attempts and zero writes](docs/frontend-phase-4a/README.md) |
| 4b | Finding disclosures, filters, fragments and specialist evidence | 111 focused and 228 full tests passed, build passed | [Seven authenticated widths, reviews #79 and #90, 30 GET attempts and zero writes](docs/frontend-phase-4b/README.md) |
| 4c | Execution, delivery and guarded fix decisions | 144 focused and 242 full tests passed, build passed | [Verified at seven widths, 34 GET attempts and zero writes in the two complete journeys. Phase 4 awaits final review.](docs/frontend-phase-4c/README.md) |
| 5 | Repository analytics, execution evidence and historical review visualization | 147 focused and 251 full tests passed, build passed | [Both repositories verified at seven widths. All 24 rows matched, 32 GET attempts and zero writes across the final walkthroughs.](docs/frontend-phase-5/README.md) |
| 6 | Agent History and specialist execution evidence | 151 focused and 260 full tests passed, build passed | [Both repositories verified at seven widths, issue #71 and saved reviews #79 and #90 reached, 80 GET attempts and zero writes.](docs/frontend-phase-6/README.md) |
| 7 | Installation Settings, Profile, authentication and onboarding | 122 focused and 266 full tests passed, build passed | [Seven-width before and after captures, isolated mutation evidence, 11 live GET attempts and zero writes.](docs/frontend-phase-7/README.md) |
| 8 | Cross-flow audit, corrections and verification | 276 tests across 35 files, type check and production build passed | [29-finding traceability, live journeys A–G, responsive geometry and remaining manual checks](docs/frontend-phase-8/README.md) |

## 8. Final audit evidence

| Check | Result |
|---|---|
| Authenticated walkthroughs | All seven completed. 74 HTTP 200 responses and 37 cancellations across 111 GET attempts. Zero attempted workflow writes. [Ledger](docs/frontend-phase-8/evidence/final-requests.json) |
| Data correctness | All 24 historical analytics rows across two repositories reconciled. Skipped #65 and measured zero #72 remained distinct. [Comparison](docs/frontend-phase-8/evidence/analytics-comparison.json) |
| Responsive and keyboard access | All seven widths covered. No document overflow on 112 screen and 21 disclosure measurements. Skip link, responsive focus transfer, account disclosure and review chooser verified. [Gallery](docs/frontend-phase-8/evidence/gallery.md) |
| Platform fixtures | Chromium, Firefox and WebKit each rendered six phone views and restored dialog focus. Native Chrome 200% zoom, emulated forced colors and reduced motion checked. [Engine results](docs/frontend-phase-8/evidence/browser-engines.json) |
| Accessibility scan | Nine isolated Lighthouse snapshots scored 1.00. The lowest sampled opaque text/background contrast was 6.29:1. [Scan](docs/frontend-phase-8/evidence/lighthouse.json) |
| Manual coverage gaps | Physical touch, actual screen-reader speech, native Safari/iOS and the OS file-picker interaction were not tested. Release-readiness sign-off remains pending. |
