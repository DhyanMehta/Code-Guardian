# CodeGuardian AI · Frontend redesign master plan

**Decision draft · 23 November 2026 · baseline `dc9b6af` · implementation awaits approval**

## A. Executive design strategy

Make the next decision legible. In the audit’s HTTPX example, a reviewer should see that PR #1 has a completed review for its current commit, that 16 findings were reported, and that **View Review** opens #79. Starting a second analysis must be an intentional choice. In analytics, the same reviewer should be able to explain how nine reviews completed while none of the ten reviews in the sample had full coverage records. These two tasks set the direction for the shell, components and testing.

Retain the dark slate canvas, indigo actions, local Plus Jakarta Sans and JetBrains Mono. Spend visual emphasis on review identity, scope, exceptions and decisions. Use rows for collections, panels for related evidence, and disclosures for technical depth. Keep essential limitations beside the data they qualify. The first release needs no backend or package changes.

**Evidence boundary.** The audit ranks CG-UX-001 through 015 by impact and documents 016 through 029 as additional findings. S1–S8 use the audit inventory order. Desktop screenshots and the live inspection cover a completed review, repository search, history and specific responsive conditions. Auth callbacks, suspended installations, most write outcomes, screen-reader speech, zoom and forced colors need validation during implementation. All dimensions, screen arrangements and acceptance tests below are proposals. The original observations, measurements and source line references remain in the [complete audit](../docs/FRONTEND_SCREENSHOT_AUDIT_2026-11-23.md).

**How to use this plan.** B maps each finding to its implementation owner and test. E and F define what appears on screen. G defines the component boundaries. H and I decide which actions and claims the data supports. K and L specify the change sets, and M defines the release checks. References to component or test names resolve to the exact paths in L.

## B. Finding-to-solution matrix

The first fifteen rows retain the audit’s priority order. Phase numbers identify the phase accountable for the complete correction. Shared prerequisites can land earlier.

| Finding | Screen / source owner | Proposed correction | Design-system dependency | Phase | Acceptance test | Risk or uncertainty |
|---|---|---|---|---:|---|---|
| CG-UX-001 | S2 · PullsTab, TriggerReview | Promote View Review on a completed matching revision. Make Run Another Review a secondary operation. | PrimaryActionLink, ActionButton | 3 | Opening #79 causes zero POSTs. Explicit rerun sends one POST and opens the returned ID. | Current auto mode cannot identify who initiated #79. |
| CG-UX-002 | S3/S4 · AnalyticsTab, ReviewPresentation | Separate analysis outcome, full coverage-record availability, known limitations and reported findings. | CoverageStatus, MetricCard | 5 | With 9 complete reviews and 0/10 full coverage records, both facts render; a known degraded agent remains visible. | Partial historical metadata can coexist with a degraded outcome. |
| CG-UX-003 | S7/S8 · AppLayout | Remove the SOC 2 Type II and OWASP ASVS assertion from the shared footer. Keep product identity only. | Footer text role | 1 | All shell variants omit the assertion and any substitute certification claim. | No applicable report or scoped assessment was verified. |
| CG-UX-004 | S2/S5/S7 · Navbar, ContextBar, RepoDashboardPage, InstallationPicker | One installation selector and one repository context line. Replace repeated side panels with scoped navigation. | AppShell, RepositoryHeader | 2 | Reach all three repository views and installation settings at 320 px without horizontal navigation discovery. | Returning to an unscoped list can lose explicit installation identity. |
| CG-UX-005 | S1–S8 · index.css, AsyncState, ReviewPresentation, pages | Replace 11–12 px working text with the semantic type and contrast roles in D. | Type and foreground tokens | 1–7 | Computed ordinary metadata ≥13 px, operative prose ≥15 px, normal text contrast ≥4.5:1 on its actual surface. | Opacity and inherited styles change the effective pair. |
| CG-UX-006 | S4 · AnalyticsTab, AppLayout | Render labeled review records in a narrow content area. Remove blanket arbitrary word breaking from prose. | ResponsiveHistory | 5 | At 320 px read “Completed”, date, score, coverage and review link in normal reading order. | A wide viewport can still contain a narrow panel. |
| CG-UX-007 | S3/S4 · AnalyticsTab | Plot server index on a zero-based scale by review sequence. Mark skipped, active and insufficient evidence distinctly. | AccessibleChart, exact-value records | 5 | A skipped zero has a labeled marker and no positive-height bar. A single point has no trend claim. | Even two complete reviews may cover different work. |
| CG-UX-008 | S5/S6 · AgentsTab, AgentOutcomeChart | Name the view Agent history. Label its loaded sample, terminal denominator, active reviews and unavailable details. | AgentOutcomeCard, StatusBadge | 6 | Five terminal reviews produce “5 of 5 OK” where supported. Missing execution coverage remains visible on detail. | Bounded history is a sample, and OK is an outcome. |
| CG-UX-009 | S2/S7 · AsyncState, PullsTab, SettingsTab | Use one scoped freshness control and expose independent read times/errors. | ScopedRefreshStatus | 3, 7 | If history fails after PRs refresh, the PRs stay visible with a history warning and its own retry. | An aggregate newest timestamp would overstate freshness. |
| CG-UX-010 | S1–S8 · Button, IconButton, page toolbars | Use anchors for destinations, padded buttons for reads/writes and named icon controls when compact. | Action variants | 1–7 | Refresh is a named button with a 44 px touch target on phones. GitHub access remains an anchor. | Existing tests contain visible labels. |
| CG-UX-011 | S3 · AnalyticsTab, StatCard | Put review outcomes and reported risk first, coverage next and auto-fix decisions below. | MetricCard, severity counts | 5 | Failed and skipped have separate labels. Auto-fix counts use reviews as their unit. | “Created” counts reviews with non-null auto-fix status, including failed. |
| CG-UX-012 | S5/S6 · AgentOutcomeChart, AgentsTab | Four compact agent summaries, latest exception link per agent, then one expandable entry per review. | AgentOutcomeCard, ExpandableDiagnostics | 6 | Find Quality’s latest issue #71 from the summary without opening a successful run. | Loading more history changes the denominator. |
| CG-UX-013 | S7/S8 · App, RepoDashboardPage, SettingsTab, ProfilePage | Expose installation settings directly and label profile automation as shared administration. | PageHeader, PolicyChangeSummary | 2, 7 | Legacy settings link resolves in the correct installation. Bulk apply names affected accounts and count. | Installation admin and repository write permission are different capabilities. |
| CG-UX-014 | S1 · RepoListPage | One explicit View pull requests link per repository, with owner/name in its accessible name. | RepositoryRow | 3 | One tab stop for the internal destination per row. Enter and open-in-new-tab retain installation ID. | A whole clickable card can swallow future nested actions. |
| CG-UX-015 | S1 · RepoListPage | Keep the aggregate secondary and label it “Open issues and pull requests”. | Row metadata | 3 | A value of 4 never renders as “4 open PRs”. | An exact PR total has no list contract. |
| CG-UX-016 | S1 · RepoListPage, SearchInput | Count filtered results, clear query, reset query when the effective installation changes. | SearchInput, EmptyState | 3 | A zero-match search can be cleared by keyboard. Switching installations shows the new full list. | Preserve an active query on ordinary refresh. |
| CG-UX-017 | S2 · PullsTab, TriggerReview | Combine revision match, risk, degraded agents and delivery in a row. Distinguish unresolved history. | PullRequestRow, ReviewSummary | 3 | Delayed history never says “No review yet”. A null SHA reads “Revision unknown”. | Summary data cannot prove all four engines completed. |
| CG-UX-018 | S4/S7, review detail · AnalyticsTab, ReviewDetailPage, SettingsTab | Localize human-readable times and disclose exact source strings. Label counts and index separately. | FriendlyTimestamp | 4, 5, 7 | Original offset and fractional seconds remain reachable by keyboard and touch. Null dates remain unknown. | Report publication time is absent from the contract. |
| CG-UX-019 | S1/S2 · RepoListPage, ContextBar, RepoDashboardPage | Show installation policy once in the scope area. Repeat only for a PR explanation that changes the decision. | InstallationSelector, RepositoryHeader | 2, 3 | One contextual mode value regardless of list length. SHA and default branch remain distinct. | Policy can change while older reviews remain visible. |
| CG-UX-020 | S6 · ReviewPresentation | Give recorded outcome, execution, coverage and accepted findings distinct labels; put raw hits by scanner. | CoverageStatus, AgentOutcomeCard | 4 | One raw hit and one accepted finding never become two reported findings. Singular labels read correctly. | Older runs can carry an outcome without coverage. |
| CG-UX-021 | S7 · SettingsTab | Lead with active source and filename. Show version and chunks on disclosure and a confirmed save/reset receipt. | StandardsUploadPanel, FriendlyTimestamp | 7 | Custom source with null version says “Version unavailable”. Clear staged file only after confirmed success. | A failed refetch following success needs a separate message. |
| CG-UX-022 | S7 · SettingsTab, WriteFeedback | Validate on file selection and at submit. Associate errors and use focused, installation-named reset confirmation. | Form feedback, ConfirmationDialog | 7 | Wrong extension, malformed UTF-8 and oversize cannot submit. Escape cancels reset and restores focus. | Reading files asynchronously can race with the next selection. |
| CG-UX-023 | S8 · ProfilePage | Pair policy editor with affected-installations list on wide screens and stack in decision order on phones. | PageHeader, SectionCard | 7 | At 1440 px the summary occupies a second column; at 390 px impact precedes Apply. | Large account lists need a bounded summary plus full list. |
| CG-UX-024 | S8 · ProfilePage, WriteFeedback | Separate current, draft and saved policy. Clear old receipts on edit and explain unchanged/mixed states. | PolicyChangeSummary | 7 | Change draft after a successful save and old confirmation clears; 409 never claims success. | Concurrent admins can change membership or version. |
| CG-UX-025 | Live #79 · ReviewPresentation, FindingsList | Keep native finding disclosure and add a visible open/close indicator. | FindingDisclosure | 4 | Keyboard activation reveals the file, rule evidence and available draft. Finding ID anchors remain stable. | Filters can temporarily hide the referenced finding. |
| CG-UX-026 | Live 700 px · Navbar | Switch global header controls together and expose menu state and current route. | AppShell, compact nav | 2 | Expanded menu at 700 px exposes exactly one Profile link and one sign-out control. | Hidden desktop controls must leave the tab order. |
| CG-UX-027 | S2–S7 · Tabs, RepoDashboardPage, AppLayout | Skip to main. Use a single horizontal true tablist when it fits and a labeled compact view chooser below it. | Tabs, RepositoryHeader | 2 | Arrow/Home/End work for tabs. Every choice works at 320 px and browser Back restores the view. | Responsive variants need unique IDs and correct focus after switching layout. |
| CG-UX-028 | Auth gate, S1 resource state · ProtectedRoute, AsyncState | Name the auth-loading state and keep one announcement per meaningful state change. | LoadingSkeleton, ErrorState | 1 | A screen reader can identify the waiting task. Placeholder shapes are hidden from the accessibility tree. | Brief waits and polling should avoid repeated narration. |
| CG-UX-029 | S1–S8 · ReviewPresentation, StatCard, SeverityBadge, Button | Remove click-like hover styling on static cards. Separate static badges from live feedback. | SectionCard, StatusBadge, SeverityBadge | 1–7 | Static metrics have no hover elevation, focus stop or live status; actual state transitions are announced once. | A shared panel class currently affects unrelated surfaces. |

## C. Information architecture

| Owner | Destinations and context | URL and history contract |
|---|---|---|
| Global/account | Brand, Repositories, account menu with Profile and Sign out. Within Profile, visibly separate signed-in identity from Shared administration. | Preserve `/`, `/profile`, `/auth/callback`, `/auth/install`. Do not mount installation-specific reads on signed-out pages. |
| GitHub installation | Compact labeled switcher, account, mode, repository inventory, GitHub access and Coding standards. Members can inspect permitted settings. | Keep `/repos?installation_id=ID`. Proposed additive client route `/settings/installation?installation_id=ID` uses the existing provider and settings endpoints. Validate membership/suspension before reads. |
| Repository | One context line “Repositories › owner/repo”, default branch, and a local view chooser for Pull requests, Analytics, Agent history. | Keep `/repos/:owner/:repo`, `?tab=pulls`, `?tab=analytics` and `?tab=agents` and `installation_id`. Old `tab=settings` must first pass the same repo access check, then replace the legacy URL with the installation route, retaining ID and unrelated query parameters. No empty repo prerequisite on the new destination. |
| PR and individual review | From the PR row, open current progress or saved result. On review, show owner/repo, PR number, review ID and section links for findings, agents, execution, delivery and fixes when applicable. | Canonical `/reviews/:reviewId` uses the authenticated review response for identity. Legacy `/repos/:owner/:repo/pulls/:number` keeps bounded resolution and replace-navigation. Preserve `#finding-ID`. A missing installation ID uses a neutral Repositories return link. |

**Navigation rules.** Keep user-initiated view/scope changes as history pushes. Use replace only for normalization, verified legacy resolution and old settings aliases. Preserve unrelated search params on the same route. Selecting a different installation on a repository URL repeats the repository access check, including the existing inaccessible-repository state. On a canonical review, show its recorded scope as read-only context; an explicit switch navigates to the selected installation’s list. On Profile, identify the aggregate administrative scope without an installation filter. A direct deep link always has a deterministic parent link. Browser Back returns to the actual origin, including Analytics or Agent history. Desktop shell uses no permanent duplicate sidebar. Only a long review may use an in-page section list, with the same destinations in a compact jump control on mobile. [Route definitions](../frontend/src/App.tsx) · [Selection precedence](../frontend/src/context/InstallationContext.tsx) · [Identity and legacy history lookup](../frontend/src/api/identity.ts)

## D. Visual design system and tokens

### Type

Use the existing locally loaded Plus Jakarta Sans. Use JetBrains Mono for hashes, paths, version IDs, exact timestamps and code. Use tabular numerals in data columns. Map the following utility names into the current Tailwind v4 theme in `index.css`. Sizes are CSS px at a 16 px root. Express the equivalent in rem, including line height. The compact values apply below 768 px. Use sentence case for labels.

| Tailwind role | Desktop size / line height / weight | Compact size / line height / weight | Use |
|---|---|---|---|
| `text-page` | 28 / 36 / 700 | 24 / 32 / 700 | One task heading per route |
| `text-section` | 22 / 30 / 650 | 20 / 28 / 650 | Findings, coverage, policy impact |
| `text-row-title` | 17 / 24 / 600 | 16 / 24 / 600 | PR, finding and repository titles |
| `text-body` | 16 / 24 / 400 | 16 / 24 / 400 | Reading text and inputs |
| `text-support` | 15 / 22 / 400 | 15 / 22 / 400 | Scope, explanations and error help |
| `text-control` | 15 / 20 / 600 | 15 / 22 / 600 | Button labels, form labels and navigation |
| `text-meta` | 13 / 20 / 500 | 14 / 20 / 500 | Dates, branch, author, secondary labels, footer |
| `text-data` | 15 / 22 / 500 | 15 / 22 / 500 | Table or definition-list values |
| `text-chart-label` | 13 / 18 / 500 | 14 / 20 / 500 | Axis ticks, legend and badges |
| `text-metric` | 28 / 36 / 650 | 24 / 32 / 650 | Measured totals with units |
| `text-code` | 14 / 21 / 450 | 14 / 21 / 450 | Code, SHA, filename and precise diagnostics |

### Color and geometry

| Token or scale | Values | Rule |
|---|---|---|
| Canvas / surface / raised / inset | `#090D16 / #101827 / #182238 / #0C1320` | Background, grouped section, overlay/selected layer, code and wells. Max two panel levels before using dividers. |
| Foreground / secondary / muted | `#F1F5F9 / #CBD5E1 / #AAB8CA` | Muted is for secondary information including timestamps. Muted on raised is 7.86:1 by sRGB luminance. |
| Action fill / hover / on-fill | `#4F46E5 / #4338CA / #FFFFFF` | Primary operation or primary navigation link. White on default fill is 6.29:1. |
| Link / focus / selected bg | `#A5B4FC / #A5B4FC / #20294A` | Links underline in prose. Current nav adds weight, shape and current semantics. |
| Divider / control border | `#2A3549 / #71839B` | 1 px. Divider is decorative. Use strong border where the control boundary conveys its identity; 4.59:1 on surface. |
| Severity foreground / background | Critical `#FCA5A5/#381820`, High `#FDBA74/#382418`, Medium `#FDE68A/#332C17`, Low `#93C5FD/#152B45`, Info `#CBD5E1/#202B3E`, Unknown `#D4D4D8/#25252C` | Always supply a visible label. Keep Info and Unknown distinct from Low and zero. Reuse the existing severity icon mapping. |
| Status foreground | OK/posted `#86EFAC`, active `#A5B4FC`, degraded `#FCD34D`, failed `#FDA4AF`, skipped/unrecorded `#CBD5E1` | Pair with a noun and an icon, label or pattern. Static status is ordinary text. Use neutral styling for unknown. |
| Spacing / radius | 4, 8, 12, 16, 20, 24, 32, 40, 48 px. Radii 6 for badge, 8 for controls, 12 for panels, 16 for dialog. | 8 within label/value, 12 between related controls, 16–24 within sections, 24–32 between sections. |
| Shadow / motion | Static panels flat. Dropdown/dialog `0 12px 32px #0006`. Interactive color changes ≤120 ms; zero motion with reduced-motion preference. | No decorative gradients, elevation on static cards, automatic ticker, count-up, pulsing green health indicator or animated chart growth. |
| Grid / measure | Max shell 1440 px including gutters. Desktop 12 columns, 24 px gaps. Tablet 8 columns, 16 px gaps. Phone 4 columns, 12 px gaps. Prose ≤70ch, dense descriptions ≤60ch. | Let rows grow with text. Containers and controls shrink safely; wrap long identifiers within their own field only. See F for gutters and breakpoints. |

### Interaction recipes

- **Navigation and operations.** One dominant action per decision group. Primary filled anchor for View Review. Filled native button for an eligible first manual review or Apply. Outlined/quiet secondary button for rerun and refresh. External links say GitHub or carry a visible external cue with an accessible name. Destructive confirmation uses red text/border or dark red fill with validated foreground. Cancel remains easy to locate. Preserve Ctrl/Cmd-click, middle-click and copy-link on destinations.
- **Hit area and focus.** Standalone controls 40 px high on desktop and at least 44 × 44 px on compact layouts, including icon buttons, disclosure summaries and menu items. Allow multiline labels to grow. Visible keyboard focus uses a 2 px solid focus outline with 3 px offset. Ensure sticky headers and scroll containers leave the ring visible. Target 4.5:1 normal text, 3:1 large text and essential control/focus boundaries. Verify composited hover, focus and selected states at release. [WCAG contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) · [WCAG target size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)
- **Surfaces.** Static section groups have a heading, one border and no hover affordance. A list uses one enclosing surface and row separators. Only an actionable row or its link receives interactive hover/focus. Avoid nested button or anchor targets. Use a labeled definition list on phones for the same values shown in a multi-column desktop table.
- **Forms.** Persistent labels above controls, 8 px label gap, 16 px between fields. Present helper/error text via described-by ID, invalid state on the field, and one named action. Keep native search/select/file behavior. Distinguish staged edits, busy, conflict and confirmed result. Errors include recovery and retain usable values.
- **Charts and feedback.** Static figure, visible unit/legend, real zero, text alternative and a linked exact-value history. Initial skeletons reserve approximate geometry, are decorative and have one named loading status. Background refresh keeps content in place. Empty, forbidden, failed, stale and uncertain states use distinct plain-language messages and scoped recovery. See H and I.

## E. Page-by-page blueprints

The following are seventeen specifications for routes and the distinct work areas inside them. Section anchors within Review, Analytics and Fleet keep the existing route identity. Each specification inherits D for typography, focus, controls and state feedback and F for shell dimensions. “Test” names the existing suite to extend. Fixtures are for verification only.

### 01 · Connected Repositories — S1 · 004, 009, 010, 014–016, 019

**Goal and structure.** Open the selected installation’s PR workspace. Shell switcher → page title and secondary GitHub access link → labeled search, filtered count and refresh → list. Each row shows owner/name, visibility, default branch and the correctly labeled combined count. Use one **View pull requests** anchor with repository-specific accessible name. Put installation mode once in the scope area. Disclose fetch detail in the toolbar. No separate picker card.

**Composition.** Row-title and meta roles, 16 px row padding, 8 px title/metadata gap. Stack the link below metadata at 390/320. Announce settled filter result count politely without narrating every row. Clear search is a button. **Files/test.** RepoListPage, SearchInput, InstallationPicker, AsyncState. Extend readFlows and reliabilityFlows. Pass when a five-row list has five PR destinations, filtering is case-insensitive, scope changes clear filters, and access loss has a recovery distinct from no matches.

### 02 · Repository Pull Requests — S2 · 001, 004, 009, 010, 017, 019

**Goal and structure.** Decide whether to read, monitor or request a review. Repository header → local views → PR rows → pagination and loaded history disclosure. PR number/title links to GitHub; action column follows H. Show revision freshness, latest review ID/status, accepted findings with highest reported severity, recorded exceptions and delivery status. Keep full SHA, comparison and older review links in details. Explain manual/automatic mode only where the explanation changes the next action.

**Composition.** Row-title, data and meta roles. Use one 16–20 px padded row, two content columns on desktop, one on phones. Keep View Review ahead of rerun in reading/focus order. Preserve history lookup and pagination independently. **Files/test.** PullsTab, TriggerReview, ReviewPresentation, RepoDashboardPage. Extend readFlows, writeFlows and identity. Pass all H rows, including an exhausted search versus a bounded search; opening #79 issues no trigger request.

### 03 · Review Detail — live #79 · 001, 002, 009, 017, 018, 020, 025

**Goal and structure.** Understand the reviewed revision and act on evidence. Canonical review heading and parent → analysis, coverage limits and reported findings → local section links → findings, agent results, timeline, delivery and fix decisions. Show delivery failure and stale revision near the header with links to their sections. For active analysis show progress ahead of pending results. Saved report, full revision, exact event times and apply-time skip reasons are reachable. Show skip reasons before approving a fix. Preserve the GitHub bot comment link when posted with a comment ID.

**Composition.** Page/body/data roles, 24 px sections, 16 px summary padding. Use 8/4 columns for evidence and supporting details where wide enough, then one column. Link to findings or progress as the primary read action; branch operations are separate explicit buttons. Provide labeled section headings and skip targets. **Files/test.** ReviewDetailPage, ReviewProgress, ReviewPresentation, AutofixActions. Extend readFlows, writeFlows and reviewProgress. Pass when failed delivery coexists with completed analysis, stale-head approval stays blocked, and rejection retains the branch link.

### 04 · Findings and Severity — live #79 and S3 severity treatment · 005, 018, 020, 025, 029

**Goal and structure.** Triage persisted findings and inspect evidence. Review’s Findings section → accepted total and severity distribution → agent/severity/search filters → matching count and disclosures. Lead each summary with severity text/icon, title, agent and file:line. Disclose detail, rule provenance, cited standard/version, advisory status and eligible draft. Preserve finding IDs, initial expansion behavior for short result sets and exact paths.

**Composition.** Row-title, meta, code roles. 12–16 px inset, 8 px label gaps. Stack path under title on mobile; allow only long paths/code to wrap or scroll. Primary interaction is a native summary with a visible chevron; file text becomes a link only when it has a real destination. Label filters; keep focus on the filter during updates. **Files/test.** FindingsList, ReviewPresentation, SeverityBadge. Extend finalFlow and SeverityBadge tests. Pass when filtering changes visible count only, keyboard opens the chosen finding, and raw hits cannot inflate the accepted total.

### 05 · Review Agent Outcomes — S6 and live #79 · 002, 008, 020

**Goal and structure.** Identify which specialist reported what. Review → Agents → four ordered rows, Security, Quality, Test Gap, Documentation. Show recorded outcome, execution state, coverage state, accepted findings and an available failure reason. Reveal analyzed/eligible files, exclusions, enrichment, engine statuses, raw findings and evidence location. A missing run gets an explicit unrecorded label.

**Composition.** Section title, data labels, 16 px rows. On phones use a labeled vertical list; keep failures above disclosure. Primary drill-down is a native summary. Avoid a separate focus stop on static badges. **Files/test.** ReviewPresentation, ReviewDetailPage. Extend readFlows and finalFlow. Pass when an OK outcome with absent coverage shows both facts; partial, not applicable, missing and failed remain distinguishable.

### 06 · Review Timeline and Diagnostics — S6 context, source-verified timeline · 008, 009, 018, 020

**Goal and structure.** Explain a queued, delayed or interrupted review. Review → Execution → attempt, current recorded stage, last heartbeat and material waits/errors → ordered checkpoint disclosure. Keep stage, agent, timestamp and attempt identity. Show provider wait/retry text only when the recorded checkpoint supports it. On terminal historical reviews, explain absent events.

**Composition.** 16 px vertical list with time and stage columns, stacked on phones. Use body for stage descriptions, code/meta only for precision. Expand execution events or refresh reads. Announce meaningful transitions once; preserve focus through polls. **Files/test.** AgentTimeline, ReviewProgress, ReviewDetailPage. Extend reviewProgress, polling and finalFlow. Pass when an interrupted started event remains interrupted and a reused checkpoint retains its recorded meaning, with no fabricated completion percentage.

### 07 · Code Health Analytics Overview — S3 · 002, 005, 009–011, 018, 029

**Goal and structure.** Read repository activity, risk and the strength of the evidence. Repository → Analytics → bounded sample and dates → review outcomes → reported severity → coverage availability → trend and exact history → compact auto-fix decisions. Show “9 completed · 0 failed · 1 skipped” for the audited 10. De-emphasize zero severity buckets while keeping them accessible. Label auto-fix counts by review. Weights and technical definitions belong in disclosure.

**Composition.** Section, metric, chart-label roles. 24 px between groups; one outcome band with inline counts, not nine identical panels. Stack bands on phones. Refresh is secondary; “Browse reviews” is a local link. Keep metric readout linear in the DOM. **Files/test.** AnalyticsTab, StatCard, ReviewPresentation. Extend readFlows and StatCard. Pass the ten-review baseline and a zero-review empty range with no invented percentage.

### 08 · Analytics Trends — S4 · 002, 006, 007, 011, 018

**Goal and structure.** Inspect observed weighted findings per review. Analytics → trend figure → evidence warning → zero-based plot → labeled legend → “Read exact values” link to history. Show range and units. Explain weights in a native disclosure. Use the chart rules in I. No smoothing, extrapolation or quality grade.

**Composition.** Figure inset 16–20 px, plot 160–200 px high, 13–14 px ticks. On narrow displays show fewer ticks, retain the full sequence and place the history link before the plot. A long series can use a labeled local scrolling region with usable minimum point spacing. Keyboard/touch readers have the exact-value alternative. **Files/test.** AnalyticsTab, proposed AccessibleChart. Extend readFlows. Pass one, zero, skipped, missing-coverage, mixed and 50-point samples.

### 09 · Analytics Historical Reviews — S4 · 002, 005–007, 018

**Goal and structure.** Open one review and explain its score. Analytics → History. Desktop table columns include review/PR, created date, analysis status, accepted findings, weighted index, coverage and known exceptions. Sort in server sequence consistently with the plot. Exact timestamp and long agent lists may expand; the presence of limitations is always visible. Review ID anchors open canonical detail.

**Composition.** Data and meta roles; 12 × 16 px cell padding and numeric alignment. Below 720 px **available content width**, use one record per review, heading + labeled definition list + same review link. Only one representation participates in navigation and accessibility. **Files/test.** AnalyticsTab, FriendlyTimestamp, ResponsiveHistory. Extend readFlows plus real-browser reflow checks. Pass when a 320 px user can read all fields, follow a review and return with Back.

### 10 · Agent Fleet Overview — S5 · 002, 005, 008, 012, 020

**Goal and structure.** Find exceptions in the loaded review history. Repository → Agent history → loaded terminal/active/unavailable counts → four agent summaries. Each includes the OK/degraded/failed/unrecorded counts with denominator and a latest recorded issue link when supported. Show one shared explanation of the sample. Allow scope/refresh detail on demand.

**Composition.** Four aligned rows with 16 px insets; agent, counts and issue link in columns on desktop. Phone puts agent and issue first, counts next, with no full-width repeated progress bars. Primary link opens an exception review. Refresh is secondary. Announce labels and counts in text. **Files/test.** AgentsTab, AgentOutcomeChart. Extend finalFlow and reliabilityFlows. Pass when Quality 2 OK/3 degraded in the five-terminal baseline points to #71 and active/unavailable counts stay separate.

### 11 · Agent Execution History — S6 · 008, 012, 018, 020

**Goal and structure.** Trace a historical exception to its review and scanner. Fleet → recent reviews. One row per loaded review, with review ID link, available status, concise exception reason or detail-fetch error. Expand the review to compare agent records, then optionally expand engine output. Keep raw detection count and accepted finding count separately labeled. Load older records with a secondary button.

**Composition.** 16 px row insets and 12 px subrows; one level of borders, then indentation. On phones use the same disclosure order and avoid nested horizontal tables. Keep the review anchor and disclosure control siblings. **Files/test.** AgentsTab, ReviewPresentation. Extend reliabilityFlows and readFlows. Pass when unavailable detail leaves the review identifiable, loading five more updates the denominator, and expansion sends no mutation or duplicate detail request.

### 12 · Installation Settings — S7 · 004, 009, 013, 019, 022

**Goal and structure.** Understand which installation owns configuration. Installation context → Installation settings → account, role and scope → Coding standards section → secondary link to shared automation administration. One scoped freshness control covers settings and standards with individually recoverable read failures. Show read-only policy information only with its source and scope.

**Composition.** Page, support and meta roles, 24 px section gaps and a 16 px account strip. Stack title/scope above actions on phones. Installation picker is explicitly labeled. Members see the reason writes are restricted. **Files/test.** App, RepoDashboardPage, SettingsTab, InstallationPicker. Extend reliabilityFlows, identity and readFlows. Pass on the legacy route, the direct route, an authorized installation with no selected repository, and a suspended/invalid ID.

### 13 · Custom Coding Standards Management — S7 · 005, 013, 018, 021, 022

**Goal and structure.** Inspect the active standard and stage a permitted replacement. Settings → active source (default or custom), filename and upload date → staged Markdown file and validation → Upload standards; Reset to defaults is separate. Version, chunk count and historical-version explanation live under Technical details. Show scope and changed source at confirmation. Show returned result and any delayed refetch independently.

**Composition.** Two static sections 24 px apart, 16–24 px insets, native input and 8 px help gap. On phones stack buttons with Upload first; Cancel receives safe initial focus in the reset dialog. Tie validation to the field; return focus after cancel or success. **Files/test.** SettingsTab, WriteFeedback, proposed ConfirmationDialog. Extend writeFlows and reliabilityFlows. Pass 512 KiB boundary, UTF-8 validation, file replacement race, non-admin, reset cancel/confirm and uncertain-write cases.

### 14 · Profile Settings and Review Automation — S8 · 005, 010, 013, 023, 024

**Goal and structure.** Identify the signed-in account and intentionally change shared review automation. Account heading → Shared administration → current policy (including mixed), draft select, affected installation names/count with their persisted modes, Apply and receipt. State beside Apply that this affects other users, eligible future events, and leaves queued reviews running. Future installations keep their own mode until a subsequent apply. Disclose a long list after the first five names and retain the complete list.

**Composition.** At 1024+ use editor 7 columns / impact 5; impact must be in reading order before Apply. At smaller widths stack editor → impact → Apply. 24 px groups, 16 px form spacing. Primary is Apply to N installations; read-only/unchanged has a reason. Use polite receipts and an alert for conflicts. **Files/test.** ProfilePage, WriteFeedback, PolicyChangeSummary. Extend profileMode and writeFlows. Pass mixed, unchanged, zero-admin, conflict, pending and server-confirmed save; editing clears a stale receipt.

### 15 · GitHub Authentication — source-inspected · 003, 005, 010, 026, 028

**Goal and structure.** Sign in and return to the requested safe route. Signed-out home → one principal Sign in with GitHub action → named callback waiting state → restored route or recovery. Preserve existing landing content relevant to sign-in, but subject claims to the same evidence standard as the footer. On callback errors give one explanation and recovery. Keep technical error detail only where actionable; never display auth codes.

**Composition.** Page/body roles, centered reading area ≤640 px, 24 px gaps. One-column phone view, 44 px auth button. Login starts the existing auth flow, so retain the operation as a button. Provide a status while busy and a real focus target on errors. **Files/test.** HomePage, Navbar, AuthCallbackPage, ProtectedRoute. Extend auth, callbackRecovery, ProtectedRoute. Pass single-use callback once under StrictMode, retained safe return path including hash, and failed logout leaving session intact.

### 16 · Onboarding and Installation Return — source-inspected · 004, 010, 013, 016, 028

**Goal and structure.** Obtain verified access or recover after returning from GitHub. Installation return → checking or expired session → account/repository selection on GitHub → confirmation, approval pending, cancellation or retry → scoped list. External installer is an anchor when available, refresh/continue/sign-in are buttons using existing handlers. Show the actionable reason first, optional setup explanation below.

**Composition.** One 600 px maximum card, 24 px inset desktop/16 phone; title, body, status and one action group with 12 px gaps. Use a live status for verification and an alert for errors. **Files/test.** InstallationReturnPage, OnboardingPage, OnboardingEmptyState. Extend callbackRecovery, finalFlow and OnboardingEmptyState. Pass first-time handoff once, cancellation without redirect loop, verified second-installation return, and recoverable failed refresh.

### 17 · Empty, loading, error, degraded and unauthorized states — S1/S2/S7 and source-only transitions · 002, 009, 016, 017, 022, 028, 029

**Goal and structure.** Explain what is known, what is missing, and the next safe action. Render the state in the affected region. Initial load uses a named status and reserved space; stale reads retain cached records with source-specific error; completed empty reads explain the domain-specific absence. Permission lost/suspended supersedes cached restricted content. Degraded analysis shows the recorded limitation beside the result. Uncertain writes retain the affected operation and reconciliation path.

**Composition.** One plain-language heading, support text and a scoped action inside a 16 px inset. Same order on phones. Retry/refresh/clear are buttons, navigation recovery is a link. Reserve assertive alerts for actionable failure. Keep focus stable through background polls. **Files/test.** AsyncState, ProtectedRoute, WriteFeedback, InstallationPicker and consuming pages. Extend polling, reliabilityFlows and writeFlows. Pass when no-match, empty dataset, read-in-progress, access denied and inconclusive writes each have distinct copy and recovery.

## F. Desktop, tablet and mobile composition

Viewport sizes are design acceptance targets. The audit measured 1440, 768, 700, 390 and 320 px. The 1920 and 1024 treatments below are proposed extrapolations. Use CSS media/container queries; use a shared media-query subscription only where switching a semantic control requires it. A single active control must own focus.

| Width | Shell and navigation | Content / actions |
|---:|---|---|
| 1920 | Center a 1440 px maximum shell. 32 px inner gutters, 64 px sticky header. Brand and Repositories at left, installation switcher in context, signed-in account menu at right. | 12 columns. One thin repository breadcrumb and tabs below. Long-form review may use a 240 px section index; limit prose width. Forms use the 7/5 composition. |
| 1440 | Same shell filling available width, 32 px gutters. Account menu owns Profile/sign-out. No duplicate global shortcut panel. | 12 columns, 24 px gaps. Page title and main action share a header. Metrics group by subject. Multi-column history where its own width permits. |
| 1024 | 24 px gutters, 60 px header. Keep repository navigation horizontal and all three destinations visible. Remove review section sidebar in favor of jump links. | 12 columns, 16–24 px gaps. PR actions align right if space permits; wrap as one group. Profile may use two columns with constrained prose. |
| 768 | 20 px gutters, 56 px header. Compact brand, account menu, installation selector on its own scope line when needed. Three horizontal repository tabs fit. | 8 columns, 16 px gaps. Single main stream, toolbar may wrap. Use desktop history only at ≥720 px inner width; the container decides. |
| 700 | 16 px gutters, 56 px header. **One** disclosure button owns global destinations, Profile and Sign out. No second desktop account control. Scope line with installation and labeled “Repository view” native select. | Form and impact stack. History uses records. No offscreen destination; dropdown contains Pull requests, Analytics, Agent history. Installation settings belongs to installation navigation. |
| 390 | 16 px gutters, 56 px header. Compact brand and Menu. Visible scoped account, one chooser and short breadcrumb. | 4 columns, 12 px gaps. Stack actions beneath titles. Search and file inputs full width. Summary rows grow; any secondary actions wrap onto their own line. |
| 320 | 12 px gutters, 56 px header, 296 px nominal content before scrollbar. Same disclosure/chooser, full-width when necessary. Menu contains a direct route to each global and installation destination where applicable. | One reading column. 44 px targets; actions can stack. Labels stay whole. A hash or filename can wrap locally. Weighted plot may scroll locally; exact values are immediately accessible. |

**Shell placement.** Signed-out and callback pages omit account/installation controls. The authenticated header separates global destinations from the installation context band. On repo pages put the current account in its single selector and show the mode only there. Put related destinations in the installation band or menu. On a review use the parent from the record. Footer contains product identity, uses the meta role, and follows page content. Page headers have title, one-line scope or evidence qualifier, then a right-aligned toolbar; on phones the toolbar follows the qualifier.

### Seven text wireframes

These layout specifications describe content order and dimensions for later mockups. Brackets denote real controls, angle arrows indicate a destination, and indentation indicates containment. Counts illustrate the audit sample, not static UI defaults.

| Surface | Desktop blueprint | Phone blueprint |
|---|---|---|
| Connected repositories | 64 px header → installation band → **Connected repositories** / [GitHub access ↗] → [Search ≤440 px] · results · [Refresh] → 72–88 px rows **owner/repo** / branch · visibility · combined count / [View pull requests →]. | 56 px header → scope → title → search and results → compact rows with one left-aligned destination. 16 px inset, 8 px metadata gap. |
| Pull requests | Repo breadcrumb + branch → three tabs → **Open pull requests** / freshness → row **#1 Add retry helper…** / Completed · current head · 16 findings · posted / [View Review] [Run Another Review] → [Loaded history]. | Scope and view chooser → PR title → result and limits → [View Review] → secondary rerun → [Revision & history]. Single identity block. |
| Review detail | **Review #79 · PR #1** / repository parent → analysis · risk · coverage · delivery → 8-column findings / 4-column supporting facts → Agents → Execution → Delivery → Fix decisions. 24 px section gap. | Heading → summary and evidence warning → [Jump to section] → findings with 44 px disclosure summaries → agent results → diagnostics → delivery → fixes. |
| Analytics | **Repository analytics** / range → outcome band / risk counts → full coverage records **0 of 10** → labeled weighted-index figure → five-plus-column exact history → auto-fix decisions. | Title/range → outcomes → severity → coverage warning → [Read exact values] and figure → one labeled record per review. 12 px row gap. |
| Agent history | **Agent history** / loaded scope → four rows **agent / OK / degraded / failed / unrecorded / latest issue →** → review history with inline exception and [Details]. | Scope → four summaries with latest issue directly below each name → review entries → optional engine evidence. 16 px row inset. |
| Coding standards | **Installation settings · account** → **Coding standards** → current source / filename / upload date / [Technical details] → file input + validation → [Upload standards] / [Reset to defaults]. | Scope and role → active source → input/help → staged filename → upload → separate reset. Reset confirmation names account and scope. |
| Profile | **Profile** → identity → **Shared review automation** → 7-column current/draft form / 5-column affected accounts → shared-impact statement + [Apply to N installations] → receipt. | Identity → shared policy heading → current/draft → names and count → policy effect → Apply → receipt. Preserve this DOM order on desktop too. |

## G. Shared React component architecture

Reuse the existing named components where shown. The left column names the design role; the migration column supplies its implementation home. Several roles can remain local named exports. Do not introduce a parallel state manager or a component whose only job is to rename an existing button. Data props are view inputs, not new API fields.

| Role / variants | Responsibility and inputs | Accessibility behavior | Migration / consumers |
|---|---|---|---|
| AppShell · public, scoped, account, review | Landmarks, brand, skip target, scope slot, account disclosure, footer; route and authenticated context | One main and active nav, named menu, focus return on Escape | Evolve AppLayout + Navbar. All routes |
| ContextSidebar / section index · wide, compact | Local section destinations only, taking available heading IDs and labels; desktop aside or compact jump control | Labeled nav of real fragment links; sticky offset | Local review index in ReviewDetailPage. Remove duplicate repository/global sidebar from RepoDashboardPage |
| InstallationSelector · multiple, single, invalid, suspended | Selected account, permissible choices, policy and change callback | Native labeled select; explicit invalid/suspended message | Evolve InstallationPicker. List, repo, settings, legacy resolution |
| RepositoryHeader · repo, review parent | Owner/name, default branch if known, installation ID, active view, destinations | Breadcrumb nav and last item identified; compact chooser labeled | Evolve ContextBar + Tabs. Repo dashboard and review parent |
| PageHeader | Heading level/title, optional scope/help and action slot | One route H1; nested sections H2/H3 | New small layout component shared by list, repo sections, settings, profile |
| PrimaryActionLink · primary, secondary, inline, external | Existing Router Link or anchor, destination, label and optional accessible context | Native href, link focus, accessible external cue | Shared action styles alongside Button, consumed by repo/PR/history/onboarding |
| ActionButton / IconButton · primary, secondary, quiet, destructive, busy | Operation, type, pending, disabled reason, icon/name | Native button, busy text, padded target; visible reason beside disabled action | Extend Button and IconButton. All toolbars and writes |
| StatusBadge / SeverityBadge | Separate labeled analysis, execution, coverage, delivery and severity states; explicit unknown | Icon/shape plus text; ordinary static text | New small StatusBadge and existing SeverityBadge. Review, PR, analytics, Fleet |
| SectionCard / MetricCard · static, inset, group | Heading/children or measured label/value/unit/context | Semantic section or definition list. No live role, tabindex or pointer treatment | Evolve StatCard, replace shared panelClass gradually. Analytics, forms and review |
| RepositoryRow | Repository + scoped URL, combined count, default branch and visibility | Single descriptively named internal anchor | Local RepoListPage component. List only |
| PullRequestRow | PullRequest, resolved ReviewItem, lookup state, mode and write state | Title links to GitHub, latest review action links internally; distinct focusable write | Local PullsTab component, compose existing TriggerReview |
| ReviewSummary | Analysis, recorded SHA/head relationship, accepted counts, delivery and available limitation | Readable text and units; no implicit success | Summaries in ReviewPresentation. PR row and review header |
| AgentOutcomeCard · summary, detail | Four count buckets over loaded terminal reviews or a named AgentRun, failure reason, latest issue link | Visible status noun, denominator and failure, expandable evidence | Evolve AgentOutcomeChart and AgentRunCard. Review and Fleet |
| FindingDisclosure | Finding, open state, stable ID, optional file/line and evidence/draft | Native details/summary, stateful visible marker, targetable finding ID | Evolve FindingCard in ReviewPresentation. FindingsList |
| CoverageStatus · point, run, sample | Typed variants for trend booleans, optional AgentCoverage, or server totals | Full text describes known/unknown/partial/not applicable; no live badge | Evolve Coverage in ReviewPresentation. Review, Fleet, analytics |
| ScopedRefreshStatus | Array of source labels, applicable/loading/error flags, last successful timestamps and refresh handlers | One status per meaningful change, focusable details, scoped retry, offline text | Extend AsyncState composition. Repo, PR, analytics, Fleet, settings, profile, review |
| FriendlyTimestamp · event, fetch, exact | Kind label, ISO string or fetch epoch, absent value and locale/timezone | Human-readable time element plus exact text in accessible disclosure | New common component. History, review, diagnostics, settings and freshness |
| ResponsiveHistory | Ordered TrendPoint list and review link builder; wide table or narrow record view | Caption/header associations or list with dl; hidden alternative excluded from accessibility tree | Local extraction from AnalyticsTab; adopt elsewhere only for matching records |
| AccessibleChart | Ordered points, weights, units, scope and exact-history anchor | Figure, caption, pattern legend, visible zero axis and accessible exact-value link | Local analytics component; retains table independently of chart rendering |
| ExpandableDiagnostics | Summary, failure teaser, children and optional initial expanded state | Native disclosure. Failure teaser remains readable when closed | Shared ReviewPresentation helper for engine output, Fleet history and review events |
| StandardsUploadPanel | Standards data, role, staged file, validation, busy, uncertain and write callbacks | Native file input, described errors, server-confirmed receipt, focus restored | Local SettingsTab extraction. Installation settings and legacy entry |
| PolicyChangeSummary | ProfileMode, current draft, administered names, version, saved result | Impact before commit, mixed/unchanged text, one receipt announcement | Local ProfilePage extraction. Shared automation form |
| ConfirmationDialog · destructive reset | Trigger ref, subject, scope, cancel/confirm, pending state; preserve inline group if equivalent interaction is chosen in O | Default proposed dialog has accessible name/description, safe initial focus, contained Tab, Escape, restore focus; if trigger becomes disabled focus active standards heading | New common confirmation for installation reset. No blanket confirmation of ordinary navigation |
| LoadingSkeleton | Geometry variant, accessible label and first-load flag | One status label, placeholders aria-hidden; reduced-motion static | Evolve AsyncState and ProtectedRoute. Data routes and auth gates |
| EmptyState | Domain-specific title, reason, optional action and intent | Heading and correctly typed link/button; distinct no-match clear | Reuse OnboardingEmptyState for installation setup and common empty pattern elsewhere |
| ErrorState / WriteFeedback | Read error, stale data, per-source retry, permission state or ambiguous write + reconcile | One alert per failure, preserve keyboard focus and user input; mutation retry always explicit | Evolve AsyncState + WriteFeedback. All read/write pages |

## H. UX action-state decision tables

### PR action policy

Resolve **access → write guard → history reliability → latest review status → revision relationship → installation policy**. Known readable results remain navigable while a write is blocked. Use the existing pending/running check and scoped write lock. If loaded history already proves an active run for that PR, link it and suppress a conflicting new request. A bounded history response cannot establish the absence of all active runs. The backend remains authoritative. Keep the explicit manual request reachable wherever currently permitted, including auto mode and incomplete history, with uncertainty visible. Labels below are UI copy.

| Condition | Dominant action and destination | Secondary or guarded operation | State text and test expectation |
|---|---|---|---|
| Completed, same head | **View Review** → canonical review ID | **Run Another Review**, secondary button | “Current revision reviewed”, highest known risk, accepted total, delivery. Opening result triggers no write. |
| Running | **View progress** → active ID | No repeat trigger | “Running” for the recorded review. If SHA differs, say which revision is running. |
| Queued (`pending`) | **View queued review** → active ID | No repeat trigger | Queue/retry wording reflects actual recorded attempt. Never estimate a start time. |
| Failed | **Inspect failed review** → review ID | Run Another Review when eligible | Surface known failure, otherwise link to detail. Zero findings confer no assurance. |
| Skipped | **Inspect skipped review** → review ID | Run Another Review when eligible | Give recorded skip reason where available. Distinguish skipped from successful completion. |
| Terminal review on outdated commit | **View previous review** → stored ID, labeled Outdated | **Review current revision**, explicit POST for current head | Show both short SHAs with exact values available. Any known active newer run takes precedence. |
| Recorded review with missing SHA | **View Review** → stored ID (or inspect/progress for its status) | Eligible secondary rerun | “Reviewed revision not recorded”. Never mark current or stale on the basis of a null SHA. |
| Exhaustive successful lookup, no review, manual | **Review pull request**, primary button | GitHub PR anchor | Explain that the operation queues the current PR head; exactly one bodyless POST. |
| Exhaustive successful lookup, no review, automatic | **Open PR on GitHub** or read the eligibility explanation | **Request review now**, secondary button | “Automatic reviews run on eligible PR events.” Avoid promising that this PR has entered a queue. |
| Initial history loading | Named “Checking review history” status; PR title remains navigable | If a manual request is available, put it in secondary actions labeled “Request review now” | No claim of first review. A cached review remains a labeled last-known link during refresh. |
| Lookup bounded, unresolved | **Load older review history**, read button | Intentional manual request with brief duplicate-work explanation | “Older history has not been fully checked.” Preserve bounded paging and loaded-history links. |
| History unavailable / read error | **Retry history**, read button; cached review link when available | Preserve currently permitted manual request when its authorization is known or server-checked | “Review history unavailable.” A denied scope suppresses inaccessible content and supersedes this row. |
| Known permission restriction | **View Review** if readable, otherwise return to accessible repositories | Suppress or disable the denied operation with reason | 403 for a write does not imply a ban on reading a previously accessible review. A missing capability field is unknown permission. |
| Write request pending | Named “Requesting review…”; retain available read links | Disable submitting again in that PR scope | Ignore double activation. Navigate once after validated acceptance using returned numeric ID. |
| Write outcome uncertain | **Check review history** and inspect last-known result | Keep write guard until reconciled by existing logic or explicit user check; a later retry is a new deliberate action | No auto replay on timeout/network/5xx/invalid response. Late response after unmount never navigates a different workspace. |

**Other actions.** A generic View Repository button would duplicate the repository’s internal PR destination. Where an external repository destination is provided, label its anchor “Open on GitHub” using the recorded URL. In-page review-history expansion, refresh, pagination and explicit retry are buttons. Saved findings, comments, branches and settings destinations are links.

### Administrative and fix decisions

| State | Available interaction | Proof before success |
|---|---|---|
| Default standards / custom / member | Admin may choose a file. Reset is available only for confirmed custom source. Member sees readable source and restriction. | Active source derives from has_custom_standards. A null custom version means “Version unavailable”. |
| File selected / invalid / submitting | Validate suffix, bytes and UTF-8 on selection and submit. Cancel superseded validation results. Keep file after validation or recoverable write error. | Successful multipart response gives metadata. Announce persisted source; if refetch fails, retain scoped warning. |
| Confirm reset / uncertain | Cancel is safe; confirm names installation and affects its repositories. Busy/uncertain blocks repeat. | Show returned reset result, preserve old review versions; resolve ambiguous result via fresh state before intentional retry. |
| Current, mixed, edited policy | No-op Apply disabled with reason. Mixed has no implied selection. A draft lists all affected active administered installations and new mode. | PATCH mode and version. On 409 refetch and require a new decision. On success use response count/mode. |
| Fix eligible / stale / fork / no drafts | Create fix branch only under existing completion, fork, draft and known-staleness gates. Unknown head is explicitly unconfirmed; preserve server validation. | One explicit request; display branch/commit, applied count, skipped targets and reasons from response/detail. |
| Fix creating / pending approval / terminal | Creating polls; pending approval allows explicit approve or reject. Known stale blocks approval; retain rejection where permitted. Respect per-review write lock, server authorization and ambiguity. | Approval records the user decision; no merge occurs. Rejection leaves the branch inspectable. Show only returned decision/identity/time. |

## I. Analytics and coverage truthfulness specification

| Question | Authoritative input | Presentation rule and edge case |
|---|---|---|
| Did analysis finish? | Review or TrendPoint.status | Show queued, running, completed, failed or skipped. A completed review can contain a degraded specialist and missing coverage. Active rows say results pending, even if stored interim counts are zero. |
| What did a specialist report? | AgentRun.recorded, outcome, failure_reason; summary degraded_agents | Show a recorded OK/degraded/failed result only when recorded and recognized. An unknown outcome with a stored row may be labeled “Outcome unknown”. In the Fleet aggregate, explain that the unrecorded bucket includes absent/unrecognized outcomes. Summary lists only support the provided grouped degradation label. |
| How much did it execute? | AgentRun.coverage.execution/status, eligible/analyzed/excluded files, batches, enrichment | Keep execution, coverage and optional enrichment separate. “Execution completed · coverage partial” is valid. Missing object → “Execution coverage not recorded”. Not applicable is its own category. Persisted checkpoints describe events, not full-file coverage. |
| Does this review have full coverage records? | TrendPoint.coverage_recorded and coverage_complete; corresponding server totals | Recorded requires all four recognized agent outcomes and four coverage metadata entries. Complete also requires eligible complete/not-applicable statuses and no degraded outcome. False recorded means “Full coverage records unavailable”. On detail, use whatever records exist. |
| Are known issues present despite missing records? | degraded_agents and unrecorded_agents independently | List the named outcomes beside the evidence-availability label. “Quality degraded/failed” and “Full coverage records unavailable” can both be true. Unrecorded agent outcome and missing coverage metadata are different fields. |
| How many findings? | Review.finding_count, severity_counts, TrendPoint.total_findings, totals.severity_counts | Call them reported/accepted findings across review runs. Repeated revisions can re-report an issue. The audit sample includes 9 high, 30 medium, 106 low. A zero is a measured reported count only in its proper context. |
| What did scanners see? | AgentRun.scanner_statuses, raw_findings, scanner_info | Label “raw detections”, scanner and associated evidence. Do not add raw detections to accepted findings. A scanner can complete with zero raw detections while agent coverage is unknown. |
| Was a report delivered? | delivery_status, delivery_error, comment_id, repo_full_name, pr_number | Display posted, pending, failed or not recorded separately. Link the GitHub comment only for posted + valid ID. Report markdown loads only when requested for supported states. |
| What does auto-fix activity mean? | totals.autofix.created/approved/rejected | Label “Reviews with auto-fix activity”, “Approved” and “Rejected”. A non-null status contributes to created once per review. The residual has no inferred disposition. |
| What is this sample? | range.review_count, requested_limit, since, until and ordered points | “Latest N reviews” and available dates. Do not imply an all-time census. Empty sample uses “No review history in this range”. A cohort of zero has no rate. |

**Acceptance example.** For S3 show **10 reviews · 9 completed · 0 failed · 1 skipped**, followed by **Full coverage records available for 0 of 10 reviews**. Show known degraded agents on their review rows. Keep the server’s ten reviews without confirmed complete coverage available in explanatory detail, labeled by that definition. Do not describe ten measured failures. For S6, Security can read **Recorded outcome OK · 1 accepted finding · execution coverage not recorded**. Engine results remain inspectable.

**Chart encoding.** Horizontal position is ordinal review sequence, oldest to newest; label first/last and selected intermediate review IDs with dates where known. Vertical axis is **Weighted findings index (points)**, using server weighted_index, ticks at zero and readable intervals through or above the maximum. No minimum positive bar. A completed review that meets coverage_complete may use a solid indigo bar. A terminal observation with incomplete records or degradation uses a hatched/outlined bar for its **observed score** with a visible key. Failed and skipped entries also carry status markers. For skipped or active reviews use a distinct baseline symbol labeled “Skipped” or “In progress”, with the persisted value and status in the history record where appropriate. A true measured zero uses a distinct zero glyph at zero. No data has its own empty state. An all-zero sample retains a labeled zero baseline. Every value stays available without hover.

**Comparability.** Distinguish “Completed with full coverage evidence” from “Limited evidence” in the legend. The former permits reading the recorded observations on the same score scale. Scope of work, PR, revision size and rules may differ. The contract supplies no guarantee of comparable analyzed code across reviews. No automated change arrow, improvement %, grade, health score, trend line or claim of equal sampling intervals. Show actual weights from totals.weights_used on disclosure. [Trend payload](../frontend/src/api/contracts.ts) · [Aggregation and coverage definitions](../backend/services/metrics_service.py)

**Timestamp rules.** FriendlyTimestamp formats valid source strings with Intl.DateTimeFormat, the viewer’s locale and named local timezone or numeric offset. Show day, abbreviated month, year and local time for historical events, e.g. “6 Oct 2026, 22:07 GMT+5:30” in that locale/zone. Keep the unrounded source string, including offset and fractional seconds, in a keyboard/touch disclosure. A clock without a date is acceptable for today’s fetch when the full date is available. Mark malformed/zoneless ambiguous input as “Time unavailable” with original string in technical detail. Do not silently append UTC. Use a valid ISO datetime attribute only for valid instants.

| Label | Source | Fallback |
|---|---|---|
| Last successful fetch | Resource updatedAt for that resource and scope | For multiple reads show “Sources updated” with the oldest successful time only when all applicable reads succeeded; detail lists each time. Loading/failed/never-read source yields “Updating”, “Partial update” or “Awaiting data”. |
| Review created | created_at | “Creation time not recorded” |
| Execution started / finished | started_at / completed_at; checkpoint created_at for individual events | “Awaiting start” for genuinely queued analysis; otherwise “Time not recorded” |
| Report publication | No published_at field. delivery_status describes status only. | Show “Posted to GitHub” with comment link when valid. “Publication time unavailable” if displaying a time field. |
| Coding standards uploaded | Standards.uploaded_at | Omit for built-in defaults. “Upload time not recorded” for historical custom source. |

## J. Technical architecture and API constraints

**Keep the read/write boundary in the existing hooks.** Page containers select identity, call endpoints and pass validated snapshots into presentation components. Use pure classifiers for PR action choice and coverage labels; unit-test combinations in H and I. Read-only components receive hrefs and callbacks, never construct another client or trigger work on mount. Keep one resource subscription owner per data scope whenever possible.

| Flow | Existing contract / behavior to preserve |
|---|---|
| Identity and authorization | AuthProvider owns cookie-backed session, safe return path, callback recovery and 401 handling. InstallationProvider prioritizes explicit query ID, then the existing single/remembered selection. A malformed or inaccessible explicit ID cannot fall back to a different account. Keep selected-role and suspension checks; server enforces repository reads/writes and administrator actions. |
| Repository and PR reads | Preserve scoped user/installation/repo keys, encoded owner/name, PR page size 50 and bounded 100-item review-history pages with explicit continuation. lookupHistory distinguishes exhausted from unresolved. Reconcile a new head, late response, scope switch and Back without exposing data for another scope. Avoid per-row detail requests. |
| Review request | Existing installation/repository/PR trigger accepts a bodyless POST. Server resolves current head and enforces write access. Use validated numeric review_id from accepted response. Explicit rerun is allowed on the same SHA. Keep busy/uncertain state and unmount guard. |
| Canonical review and delivery | Fetch by authenticated review ID. Keep nullable installation, revision, findings evidence, coverage and historical times. Retain active/creating polling at 5 s and pending/failed delivery polling at 15 s up to three visible minutes. Manual refresh can resume monitoring. Preserve terminal cache invalidation and late-response cancellation. |
| Fleet and analytics | Keep analytics limit 50, refresh interval 30 s, ordered points and server weights. Fleet loads five initially, adds five per request up to current cap 200, fetches details with at most two concurrent readers, and respects active/terminal cache lifetimes. Scoping and deduplication survive responsive layout changes. |
| Standards | GET settings + standards by installation. POST multipart file and DELETE on explicit reset, both admin-checked. Enforce .md, UTF-8 and ≤524288 bytes. Historical reviews retain their standards version. Do not compute chunks, assign a version, or display local file selection as persisted state. |
| Shared policy | GET/PATCH existing profile review-mode route. Only active installations administered by this user participate. Submit server version + auto/manual. Server response and refreshed installation scope own the saved state. No per-repository override is implied. |
| Auto-fix | Preserve review-specific create/approve/reject endpoints and ID types, validated response shapes, same-head/fork/eligible-draft guards, server-side authorization and confirmed decisions. No merge or branch deletion is implied. |
| Failure and reconciliation | Keep GET retry/backoff, session expiry, cache invalidation and offline/visibility controls. Mutations use the existing useWrite scope and never auto-replay. A network error, invalid success payload or server failure can be ambiguous. Refresh persisted state, present the existing explicit-retry path, and distinguish confirmed conflict from uncertain completion. |

Reference boundaries: [authentication](../frontend/src/context/AuthContext.tsx), [selection](../frontend/src/context/InstallationContext.tsx), [API operations](../frontend/src/api/endpoints.ts), [validated types](../frontend/src/api/contracts.ts), [scoped reads](../frontend/src/api/resources.ts), [write guards](../frontend/src/api/writes.ts), [polling](../frontend/src/api/polling.ts), [manual trigger authorization](../backend/api/installations.py), [standards](../backend/api/standards.py), [profile policy](../backend/api/profile.py), [auto-fix decisions](../backend/api/autofix.py).

**Future dependencies, excluded from these phases.** True open-PR totals per repository require a supported total or aggregation. Live per-agent availability requires timestamped health telemetry with freshness rules. Unique unresolved issues and comparable code-health improvement require deduplication and a comparable-work model. Exact report publication time requires a persisted timestamp. Pre-disabling every unauthorized review action requires a repository-specific capability field. Until such contracts exist, use the bounded facts above and present server denials accurately.

## K. Incremental implementation roadmap

Each numbered slice is independently reviewable. Changes refer to exact file paths in L. Start each phase from its listed prerequisites. For later authorized implementation, use the existing frontend scripts from the frontend directory: `npm test -- <test-file>` for a focused Vitest run, `npm test` for the full suite and `npm run build` for TypeScript/Vite. Use isolated fixtures for writes; routine visual checks exercise read paths. These are future acceptance steps.

| Phase / dependencies | Ordered work, component changes and principal files (exact paths in L) | Functional and visual verification / exit | Principal risk and rollback |
|---|---|---|---|
| **1 · Foundations**. Baseline only. | 1a add semantic palette/type roles in index.css and shared action variants in Button, IconButton, Actions. 1b remove assurance copy in AppLayout, add skip target and named ProtectedRoute loading. 1c evolve SeverityBadge, StatCard, AsyncState and WriteFeedback. Add SectionCard, StatusBadge and FriendlyTimestamp as their first consumers land. Start with one real toolbar to prove treatment in RepoListPage. | Button, IconButton, SeverityBadge, StatCard, ProtectedRoute tests. Verify primary/secondary links, hover/focus/disabled, claim absence, contrast on actual surfaces and reduced motion. Screenshot toolbar at 1440/390 and auth gate at 320. Exit when roles coexist with legacy utilities and existing callers build. | Global selectors could alter untouched routes. Make tokens additive and migrate call sites explicitly. Roll back the affected primitive or caller independently; keep unsupported claims removed. |
| **2 · Shell and scopes**. P1. | 2a consolidate Navbar and AppLayout around PageHeader and the existing phase 1 skip target. 2b evolve ContextBar, Tabs, InstallationPicker and RepoDashboardPage; move picker responsibility out of RepoListPage where shell owns it. 2c in App add protected InstallationSettingsPage, composing existing SettingsTab. Preserve guarded legacy alias and existing invalid-tab normalization. | identity, Tabs, ProtectedRoute, reliabilityFlows, auth, finalFlow. Test explicit invalid ID, direct review, legacy settings, access loss, Back/Forward and query preservation. Capture all seven widths with menu open/closed at 700 and 320. Exit with one effective navigation set per width. | Alias loops or duplicate scoped reads. Restore old dashboard composition per entry point; retain a thin resolver for any published additive settings URL. Keep one provider instance. |
| **3 · Repository and PR workflow**. P1–2. | 3a RepoListPage + SearchInput implement compact rows, count, clear and scope-reset. 3b PullsTab + prActions compose summary and CTA from existing lookup; keep TriggerReview write owner. 3c adopt ScopedRefreshStatus on list/PR, preserve pagination and history. | readFlows, identity, writeFlows, reliabilityFlows, SearchInput and new prActions cases. Verify same-head View Review zero POST, deliberate trigger exactly one, old/unknown SHA, history timeouts and mobile priority. Exit when every H row passes and PR navigation retains identity. | A loading transition can temporarily expose a first-review action. Revert only the affected presenter/classifier to its preceding tested view; retain write guards and truth labels. |
| **4 · Individual reviews**. P1/2 and P3 action vocabulary. | 4a ReviewDetailPage + ReviewProgress provide summary, section links and scoped freshness. 4b ReviewPresentation + FindingsList implement severity, disclosures and separate outcome/coverage. 4c AgentTimeline + AutofixActions adopt diagnostics/time roles and preserve fix/delivery decision flow. | readFlows, finalFlow, reviewProgress, writeFlows, polling. Capture completed, active, skipped, failed, partial and historical null states at 1440/390. Tab to finding and fix decision; check returned IDs and no auto approval. Exit with all evidence accessible and head checks preserved. | Collapsing critical evidence or linking to the wrong scope. Restore the section independently with its original data owner. Preserve finding IDs and review URL. |
| **5 · Analytics**. P1/2 and coverage vocabulary from P4. | 5a AnalyticsTab rearranges totals/sample/availability and uses StatCard and ReviewPresentation. 5b add AccessibleChart with truthful zero/skip handling. 5c extract ResponsiveHistory, add FriendlyTimestamp and link figure to exact records. | readFlows, StatCard and new analyticsPresentation cases. Compare sample totals to returned payload, test all-zero/one/50 points, missing fields and combined degradation. Capture 320/700/768/1440 and a narrow content container. Exit when every visible metric has an input and history works without chart/hover. | Weights or unknown values can be misread. Roll back plot independently to the exact-value history with evidence labels. Keep data semantics and route. |
| **6 · Agent history**. P1/2/4. | 6a AgentOutcomeChart becomes four text-first summary rows with latest-issue links computed from existing loaded details. 6b AgentsTab collapses per-review evidence, retaining errors, concurrency and cache. Reuse AgentRunCard in ReviewPresentation. | finalFlow, reliabilityFlows, readFlows. Test mixed active/terminal/unavailable, 0 terminal, latest partial/failed issue and load-more. Capture 390/768/1440, including a failed detail fetch. Exit when #71 can be reached directly and no live-health claim appears. | Accidentally changing the denominator or multiplying requests. Roll back summary or list presentation independently; leave agentHistory/cache implementation intact. |
| **7 · Administration and entry**. P1/2, shared time/feedback from P3–4. | 7a SettingsTab + ConfirmationDialog implement active source, native validated upload and reset. 7b ProfilePage implements staged policy, impact list and receipt lifecycle. 7c HomePage, AuthCallbackPage, OnboardingPage, InstallationReturnPage and OnboardingEmptyState adopt new entry states. | writeFlows, profileMode, reliabilityFlows, auth, callbackRecovery, finalFlow, OnboardingEmptyState. Verify member/admin, failed upload, reset focus, mixed/unchanged/409, OAuth cancel and return. Capture default/custom and profile impact at 320/768/1440. Exit when scoped authorization, retry and confirmed results hold. | Replayed writes or callback loops. Roll back form/entry slices separately. Keep the original mutation handlers, callback exchange guards, settings route and server versions. |
| **8 · Cross-flow QA**. P1–7. | 8a run source-of-truth suites listed in L. 8b capture the specified width/state combinations; verify keyboard, zoom, NVDA and forced colors. 8c fix local regressions in their owning files and add only focused test coverage for uncovered defects. | Full suite + build; execute M, compare results against source fixture fields and the audit tasks. Record browser, locale, viewport, accessibility tool, failures and retest results. Exit when major workflows, trust semantics and accessibility gates pass. | Static mocks may hide focus, wrapping or side effects. Reject a failing slice or restore its preceding tested presentation. Roll back in reverse dependency order when multiple slices depend on it. No data or schema rollback required. |

Checkpoint after P2: deep-link, scope and header-width matrix. After P4: repository → current review → evidence → Back and guarded fix decisions. After P6: history/analytics reconciliation against the same review. After P8: four end-user tasks and the complete state matrix. Keep behavior changes and visual-only changes identifiable in review.

## L. File-by-file modification inventory

Paths below are relative to `frontend/src/`. “New” means proposed during a later authorized phase. All other entries are existing files. Co-locate single-consumer rows/panels within their owning module first; extract only if readability or reuse warrants it.

| File | Phase | Planned change |
|---|---|---|
| [index.css](../frontend/src/index.css) | 1–8 | Add semantic Tailwind type/color/spacing utilities, safe word-wrap, focus, sticky offsets and reduced motion. |
| [App.tsx](../frontend/src/App.tsx) | 2 | Register additive protected installation route. Keep canonical/legacy/public routes and fallback. |
| [components/layout/AppLayout.tsx](../frontend/src/components/layout/AppLayout.tsx) | 1–2 | Evolve AppShell. Skip-to-main target, scoped layout, global status and factual footer. |
| [components/layout/Navbar.tsx](../frontend/src/components/layout/Navbar.tsx) | 2, 7 | Unify breakpoints and disclosure semantics; route-aware header, scoped return and auth actions. |
| [components/layout/ContextBar.tsx](../frontend/src/components/layout/ContextBar.tsx) | 2 | Own repository breadcrumb and single identity line; remove repeated mode/branch treatment. |
| `components/layout/PageHeader.tsx` | 1–2 · new | Shared heading, scope/evidence qualifier and action slot. |
| [components/common/InstallationPicker.tsx](../frontend/src/components/common/InstallationPicker.tsx) | 2 | Scope switcher and access errors. Retain selection authority in provider. |
| [components/common/Tabs.tsx](../frontend/src/components/common/Tabs.tsx) | 2 | Desktop horizontal tab semantics. Preserve existing variants and keyboard tests for other callers. Compact chooser lives with repository navigation. |
| [components/common/Button.tsx](../frontend/src/components/common/Button.tsx) | 1 | Preserve button API and native behavior; add quiet/destructive treatments and common action styles. |
| [components/common/IconButton.tsx](../frontend/src/components/common/IconButton.tsx) | 1 | Match control height, name requirement and focus ring. |
| `components/common/Actions.tsx` | 1 · new | Presentation for Router Link/external anchors with primary/secondary treatment, using shared styles. |
| `components/common/SectionCard.tsx` | 1 · new | Provide heading and static group/inset variants; replaces repeated panel recipes at adoption sites. |
| [components/common/StatCard.tsx](../frontend/src/components/common/StatCard.tsx) | 1, 5 | Use measured-value typography and static surface. Preserve current props for other callers; analytics omits unsupported trend props. |
| `components/common/StatusBadge.tsx` | 1 · new | Text-first status presentation with icon and tone; keep domain labels supplied by caller. |
| [components/common/SeverityBadge.tsx](../frontend/src/components/common/SeverityBadge.tsx) | 1, 4 | Preserve severity names/icons, improve readability and remove static live-region behavior. |
| [components/common/SearchInput.tsx](../frontend/src/components/common/SearchInput.tsx) | 3 | Add accessible clear affordance where needed without affecting controlled input semantics. |
| [components/common/AsyncState.tsx](../frontend/src/components/common/AsyncState.tsx) | 1, 3 | Named initial loading, scope-local stale/error recovery. Allow consumers to suppress default timestamps when using grouped freshness. |
| `components/common/ScopedRefreshStatus.tsx` | 3 · new | Combine read feedback for a scope while preserving individual status/timing and retry. |
| `components/common/FriendlyTimestamp.tsx` | 1 · new | Centralize localized display and exact-value semantics, including missing/ambiguous inputs. |
| [components/common/WriteFeedback.tsx](../frontend/src/components/common/WriteFeedback.tsx) | 1, 7 | Present busy/uncertain/reconcile messaging with adequate targets; keep mutation lock external. |
| [components/common/ProtectedRoute.tsx](../frontend/src/components/common/ProtectedRoute.tsx) | 1 | Name loading state. Preserve signed-out return, zero-install and error branches. |
| `components/common/ConfirmationDialog.tsx` | 7 · new | Accessible, focused reset confirmation with focus restoration and cancel. |
| [components/common/OnboardingEmptyState.tsx](../frontend/src/components/common/OnboardingEmptyState.tsx) | 7 | Keep configured installer destination, access checks and continuation in a readable state panel. |
| [pages/RepoListPage.tsx](../frontend/src/pages/RepoListPage.tsx) | 1–3 | First toolbar consumer; list of single-destination RepositoryRow components, filter reset and no-match recovery. |
| [pages/RepoDashboardPage.tsx](../frontend/src/pages/RepoDashboardPage.tsx) | 2–3 | Resolve scope/access before children; host view chooser, legacy settings alias, remove duplicate nav/identity. |
| [components/dashboard/PullsTab.tsx](../frontend/src/components/dashboard/PullsTab.tsx) | 3 | Keep PR/history resource orchestration and add row presenter, action policy, scoped refresh and history disclosure. |
| `components/dashboard/prActions.ts` | 3 · new | Pure selection of priority, label, enabled conditions and reason from H. Operation remains in TriggerReview. |
| [components/reviews/TriggerReview.tsx](../frontend/src/components/reviews/TriggerReview.tsx) | 3 | Accept presentation/label priority. Keep scope key, bodyless POST, reconciliation and guarded navigation. |
| [pages/ReviewDetailPage.tsx](../frontend/src/pages/ReviewDetailPage.tsx) | 4 | Keep ID resolver, history resolution and polling; compose evidence sections, return links, delivery and fix decisions. |
| [components/reviews/ReviewPresentation.tsx](../frontend/src/components/reviews/ReviewPresentation.tsx) | 3–6 | Evolve Counts, Coverage, AgentRunCard and FindingCard. House shared review summary, diagnostic disclosures and typed coverage label rules. |
| [components/reviews/FindingsList.tsx](../frontend/src/components/reviews/FindingsList.tsx) | 4 | Accessible filter/count and stable disclosure identity during filtering. |
| [components/reviews/ReviewProgress.tsx](../frontend/src/components/reviews/ReviewProgress.tsx) | 4 | Expose truthful analysis status; no inferred percent. |
| [components/reviews/AgentTimeline.tsx](../frontend/src/components/reviews/AgentTimeline.tsx) | 4 | Current-attempt checkpoints, reuse/interrupt/wait states, human-readable times and technical details. |
| [components/reviews/AutofixActions.tsx](../frontend/src/components/reviews/AutofixActions.tsx) | 4 | Retain write conditions and scoped head read; show eligibility, evidence, conflicts and explicit decisions. |
| [components/dashboard/AnalyticsTab.tsx](../frontend/src/components/dashboard/AnalyticsTab.tsx) | 5 | Compose scoped outcomes, evidence availability, risk and secondary auto-fix activity. |
| `components/dashboard/AccessibleChart.tsx` | 5 · new | Ordinal weighted-index figure, zero/skip/insufficient states, equivalent-value link. |
| `components/dashboard/ResponsiveHistory.tsx` | 5 · new | Single ordered dataset, wide semantic table and narrow labeled records. |
| [components/dashboard/AgentsTab.tsx](../frontend/src/components/dashboard/AgentsTab.tsx) | 6 | Retain agentHistory and bounded fetching. Compose issue-first summaries and expandable review rows. |
| [components/dashboard/AgentOutcomeChart.tsx](../frontend/src/components/dashboard/AgentOutcomeChart.tsx) | 6 | Preserve terminal denominator and public entry point while replacing large bars with four readable summaries. |
| `pages/InstallationSettingsPage.tsx` | 2 · new | Direct scope-validated settings container for existing SettingsTab. No repository data dependency. |
| [components/dashboard/SettingsTab.tsx](../frontend/src/components/dashboard/SettingsTab.tsx) | 2, 7 | Keep settings and standards readers/writes, add scoped refresh, local StandardsUploadPanel, staged validation, reset and receipts. |
| [pages/ProfilePage.tsx](../frontend/src/pages/ProfilePage.tsx) | 7 | Local PolicyChangeSummary and impact-by-installation layout. Preserve versioned write and server-reported result. |
| [pages/HomePage.tsx](../frontend/src/pages/HomePage.tsx) | 7 | Signed-out sign-in hierarchy, existing redirect and recovery plus evidence review of public copy. |
| [pages/AuthCallbackPage.tsx](../frontend/src/pages/AuthCallbackPage.tsx) | 7 | Named pending/error states, preserve single-use exchange and safe return behavior. |
| [pages/InstallationReturnPage.tsx](../frontend/src/pages/InstallationReturnPage.tsx) | 7 | State framing for expired session and verified installation return. |
| [pages/OnboardingPage.tsx](../frontend/src/pages/OnboardingPage.tsx) | 7 | Preserve server-owned handoff, cancellation, verified ID, pending approval and retry. |

**Behavioral reference files.** Keep `main.tsx`, `context/AuthContext.tsx`, `context/InstallationContext.tsx`, `api/client.ts`, `api/contracts.ts`, `api/endpoints.ts`, `api/identity.ts`, `api/resources.ts`, `api/polling.ts` and `api/writes.ts` as the behavior owners. Use current selection/provider methods and small view adapters. If an installation navigation helper is needed, extend the identity helper with a pure URL builder and its tests. Preserve `frontend/vite.config.ts`, dependency pins, backend services and data stores.

**Test ownership.** All names below resolve under `frontend/src/test/`. Extend expectations for intentional new labels, roles or URLs while retaining behavioral assertions.

| Exact file(s) | Coverage to preserve or add |
|---|---|
| `Button.test.tsx`, `IconButton.test.tsx`, `StatCard.test.tsx`, `SeverityBadge.test.tsx` | Variant roles/names, static metrics, static badges, busy/disabled and accessible icon controls. |
| `Tabs.test.tsx`, `ProtectedRoute.test.tsx`, `SearchInput.test.tsx` | Arrow/Home/End, active panel IDs, protected loading, search/clear and keyboard operation. |
| `identity.test.ts`, `reliabilityFlows.test.tsx` | Scoped and legacy routing, selected installation precedence/access loss, late responses and Fleet concurrency. |
| `readFlows.test.tsx`, `finalFlow.test.tsx` | Canonical review link/zero trigger writes, partial/unknown coverage, single-point analytics, filtered findings and installation-return recovery. |
| `writeFlows.test.tsx`, `profileMode.test.tsx` | Explicit rerun and numeric accepted ID, standards, uncertain writes, auto-fix authorization outcomes and versioned bulk policy. |
| `reviewProgress.test.tsx`, `polling.test.tsx` | Current-attempt progress, queue/failure semantics, visibility, retries, cleanup and terminal delivery budget. |
| `auth.test.tsx`, `callbackRecovery.test.tsx`, `OnboardingEmptyState.test.tsx`, `apiClient.test.ts` | Session/callback, scoped installation recovery, safe configured links, parser and retry invariants. |
| Proposed `prActions.test.ts`, `analyticsPresentation.test.tsx` | Table-driven cases for H/I where existing tests do not cover combinations. Continue using existing fixtures.ts with explicitly isolated test data. |
| `ProgressBar.test.tsx`, `AgentHistoryDots.test.tsx` | Keep existing regression coverage for shared primitives. Passing these tests does not establish usage on the redesigned pages. |

## M. Functional, accessibility and visual acceptance

Use fixture-backed reads and stubbed writes for automated scenarios. Inspect a running read-only interface for real layout. Do not trigger live reviews, change policy, operate auto-fix or upload standards to verify visual styling. Capture date, source state, width, browser, locale/timezone and mode of verification. Record defects as actual versus expected; a jsdom assertion alone cannot verify contrast, overflow or focus visibility.

| Scenario | Method and required result |
|---|---|
| Current review, stale head, null head, new auto/manual PR | Parameterize H. Verify href, label and DOM role, POST count/path/body, returned numeric ID and Back. Double activation produces one request. |
| Mixed active/completed/failed/skipped history | Inject known mixed records, missing latest match and stopped search. Preserve cached links and load-more; link to active progress and avoid a fake clean or empty result. |
| Incomplete or absent execution metadata | Same review with OK outcome + missing coverage, degraded outcome + missing records, complete/not applicable records, and partial. Read header, chart, rows and Fleet: the meanings agree and accepted counts are invariant under expansion. |
| Installation access and race | Two accessible installations including same repo name; change selection during a delayed fetch. Verify old content disappears, URL ID is preserved, no scope leakage and Back restores authorized context. Invalid/suspended/ambiguous selection never silently chooses another installation. |
| Auth expiry and deep link | Preserve path, query and finding hash through sign-in. Invalid return and duplicate callback are safe. Cancelled installer and refresh failure give recovery; confirmed update lands in verified account. |
| File, role and reset | Select valid/invalid/oversize files, swap selection mid-validation, check both sides of byte limit, admin/member/suspended roles. Member has no enabled mutation. Cancel sends zero DELETE; confirmed reset sends one and refreshes active state. |
| Policy concurrency | Mixed/no-admin/unchanged/dirty/saving/409/ambiguous/saved. No request on selector change. PATCH includes version. List affected installations before submit; use response count in receipt. No stale success on further edit. |
| Uncertain write and recovery | Simulate network loss after submission for review, standards, policy and auto-fix. Inspect new state before explicit retry; no automatic repeated POST/PATCH/DELETE. Busy and uncertain states remain scoped correctly across navigation. |
| Fix authority and delivery | Test completed vs active/fork/no eligible drafts/stale/unknown head, server 403, conflicting decisions, creating and pending approval. Confirm approval does not merge, rejection leaves branch, skipped targets stay available and posted requires a valid comment link. |
| History and freshness | New PR data with failed history, standards success with stale settings, offline, paused delivery polling. Distinct read/error states, precise time on demand, no background-refresh focus theft or false “all updated”. |
| Plot/table equivalence | Same review IDs, order, status, weighted score, accepted count and caveats in figure alternative and history. Verify visual zero vs skipped marker and insufficient metadata. Use 0, 1, 10 and 50 entries. |
| Keyboard and screen reader | Keyboard-only: skip link, nav, tabs/chooser, search clear, findings, history, reset and cancellation. With NVDA + a documented Windows browser, verify names, landmarks, headings, current location, dialog focus return and announced errors/receipt. Repeated poll without meaningful state change produces no repeated announcement. |
| Contrast, motion, magnification and touch | Measure actual rendered colors including alpha, hover, selected and focus states. Verify 200% zoom, 320 CSS px reflow, forced colors, increased text spacing and reduced motion. No hidden primary operation, word-fragment table, obscured focused control, or focusable duplicate subtree. Use a touch browser for chooser, disclosures, legend alternative and exact timestamps. |
| Visual regression states | Shell at 1920, 1440, 1024, 768, 700, 390, 320. At 700 capture menu open and closed. At 320/390 capture all seven wireframe surfaces, a long repository/path, history table alternative, file error and policy impact. At 1440 capture current/stale PR, no-match list, coverage-limited series and failed scanner detail. At 768 and 1024 verify the transition around 720 px **content** width. |

**Four product walkthroughs.** A reviewer can open HTTPX’s completed result without creating a run. An analyst can explain why 9 completed and 0/10 fully recorded coexist. A developer can reach Quality’s recorded issue #71 and distinguish raw evidence from accepted findings. An administrator can name who else is affected by a policy change before committing it. Verify each using ordinary navigation and keyboard-only interaction. Use isolated fixtures when reproducing the dated sample on a changed dataset.

## N. Risks and compatibility considerations

| Risk | Compatibility measure |
|---|---|
| Two route identities appear to represent one installation, or review detail inherits whichever account was last selected | Canonical review uses the recorded review scope. Preserve explicit installation priority, gated legacy settings resolution and empty/inaccessible repository states. Test direct entry, reload, Back and Forward. |
| A redesign hides an available manual action or interprets an absent permission field as denial | H governs emphasis separately from authorization. Keep existing handlers and server checks. A member can have write access to a repository even when they cannot edit installation standards. |
| A new layout remounts data owners while resizing or opening a disclosure | Put subscriptions above presentation branches; use stable IDs and scoped keys. Form file/draft and write uncertainty survive viewport changes. On actual scope change discard scope-local staged data. |
| Higher density conceals operational limitations | Warnings, affected scope, latest exception and stale/unknown revision remain visible while details collapse. Preserve bounded sample, denominator and unit beside aggregate values. |
| Older records omit fields used by current UI | Exercise nullable source types, absent raw scanner summaries, missing event dates and no coverage metadata. Unknown states remain explicit. Never fill gaps with mock evidence. |
| Visual changes break tests that assert old labels or CSS classes | Update assertions for approved wording, role and behavior in the same slice. Keep request counts, endpoint identity, negative authorization, non-replay and keyboard tests. |
| Rollback reintroduces an unsupported claim or a misleading chart | Revert local view changes while retaining the factual footer and accurate semantics. Use history/table-only analytics as the reversible fallback. No data migration is needed. |
| Insufficient live evidence for auth, writes, speech, touch, zoom and localization | Treat these as acceptance obligations. The master plan adds no claim that these scenarios already passed. |

## O. Product-owner decisions requiring approval

Approval of the following defaults together is sufficient to start the first applicable phase.

| Decision | Recommended default | Practical consequence |
|---|---|---|
| Installation settings address | Add `/settings/installation?installation_id=ID` and keep the old repository settings URL as a checked alias. | Direct access for authorized accounts with no selected repository. Without the additive URL, keep the legacy entry visibly installation-scoped until owner approval. |
| Repository navigation | Horizontal tabs for the three repo views at ≥768 px, native labeled chooser below. Use “Agent history” as the visible label and retain `tab=agents`. | Removes the duplicated rail and offscreen mobile destinations while keeping old bookmarks. |
| Manual reruns | Secondary “Run Another Review” on a matching result, primary “View Review”; retain explicit manual initiation under automatic policy. | Preserves review behavior while giving inspection priority. No new confirmation for a routine rerun. |
| Analytics baseline | Show observed scores with coverage qualification and an equivalent history list. Omit improvement claims and an aggregate health score. | Reported evidence remains available in incomplete historical samples. |
| Repository and profile density | Compact single-destination repo rows, clear filter on installation switch, 7/5 policy/impact layout, and full affected list on demand. | Avoids one repository’s filter or one installation’s scope being mistaken for another. |
| Administrative confirmation | Show scope inline before bulk Apply; retain versioned submission. Use an explicit reset dialog for deleting custom standards. | Keeps current write semantics and makes the destructive decision and its scope visible. |
| Footer | Remove the unverified assurance phrase and retain the product name. | Any future assurance statement requires separately verified, scoped evidence. |

## P. Recommended first implementation milestone

**Approve a small foundation slice that ends on the Connected Repositories screen.** It is easy to compare with S1, exercises real navigation and read states, and leaves review creation and administrative writes outside the change set.

1. Record the S1 baseline at 1440 and 390 with the same installation and loaded dataset. Note timestamp contrast and the repository refresh target, previously 144 × 16 px at 1440.
2. Land P1a type/foreground/action roles, the scoped refresh button treatment on S1, and P1b’s factual footer, skip target and named auth wait state. Keep repository data and route construction in their current owners.
3. Demonstrate the existing repository destination, visible keyboard focus, readable timestamp, 44 px mobile refresh, correct read-only request behavior, and successful focused tests/build. Hand the before/after evidence to the owner before extending the treatment.

The next workflow checkpoint is **PR #1 → View Review → review #79 with zero trigger requests**, using the verified same-head case in phase 3. The roadmap and acceptance criteria are ready for implementation approval.

FRONTEND REDESIGN MASTER PLAN COMPLETE — AWAITING IMPLEMENTATION APPROVAL
