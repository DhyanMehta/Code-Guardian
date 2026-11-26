# Phase 4b · Findings and agent coverage

Verified on 25 November 2026 with saved reviews **#79** and **#90**. Review #79 shows why this change matters. All four specialists recorded OK, but the review has no execution coverage records. Review #90 records OK, completed execution and complete coverage for each specialist. The redesigned cards let a reader see the difference before opening technical evidence.

## A. Git baseline

Branch `codex/durable-review-pipeline`, HEAD `dc9b6af4149764ae66e2ca10974c151a6bf819a0`. The index was empty. Earlier milestone implementations, plans, screenshots and unrelated files were present as unstaged or untracked work. There was no separate Phase 1–4a checkpoint at HEAD. The comparison below uses the authenticated working tree at milestone entry. No checkpoint, staging or commit was performed.

## B. Files changed for this milestone

| File | Responsibility |
|---|---|
| [ReviewDetailPage.tsx](../../frontend/src/pages/ReviewDetailPage.tsx) | Integrates both sections, keeps section navigation available on phones and delegates finding fragments to the list. |
| [FindingsList.tsx](../../frontend/src/components/reviews/FindingsList.tsx) | Filter state, totals, reset, local matching and linked finding focus. |
| [FindingCard.tsx](../../frontend/src/components/reviews/FindingCard.tsx) | Finding identity, disclosure, citation and draft. |
| [ReviewPresentation.tsx](../../frontend/src/components/reviews/ReviewPresentation.tsx) | Extracted the former finding card. Existing Agent History uses its existing agent presentation. |
| [ReviewAgentResults.tsx](../../frontend/src/components/reviews/ReviewAgentResults.tsx) | Specialist outcomes, execution, coverage and scanner evidence on Review Detail. |
| [findingsEvidence.test.tsx](../../frontend/src/test/findingsEvidence.test.tsx) | Filter and anchor behavior, contract edge cases and request regression checks. |
| [Implementation checklist](../../tasks/todo.md) and [regression checklist](../../UI_REGRESSION_CHECKLIST.md) | Phase 4b verification and pending Phase 4c approval. |
| This directory | This report, both response summaries, four geometry files, two journey ledgers and the screenshots indexed below. |

## C. Previous presentation

The original toolbar searched title, file and description. The display denominator came from the array length. Agent rows placed execution or outcome in the same header slot, pushed coverage into a fine-print sentence and showed the scanner hierarchy above the fold. On a 320 px viewport, #79 placed its first finding at document y=1332 and its first Security card at y=4673.

## D–E. Findings architecture, filtering and counts

Review Detail still owns the authorized review resource and shared current-head lookup. It passes the validated finding array, persisted total, recorded standards version and review ID to the list. Severity, agent and case-insensitive search intersect locally. Search includes title, description, path, line, severity, specialist label and stored rule evidence. Records retain response order and stable IDs. There is no list cap.

The overview retains the response severity distribution. The matching count has its own status region. When individual records and reported totals disagree, the list explains how many individual records were supplied. The UI distinguishes a confirmed zero, a nonzero total with unavailable records, and a filter with zero matches. Clearing restores all records and focuses search.

## F. Disclosures and fragments

The collapsed summary shows written severity, title, agent, file and available line, a recorded rule qualifier and a chevron. A native disclosure opens the explanation, permalink and available evidence. Small result sets retain their initial expanded state. A finding fragment waits for the authorized record, clears conflicting filters with a visible notice when needed, opens the target, and focuses its summary. An unrecognized ID leaves the current view alone. Ordinary refresh leaves an already resolved target under the reader’s control. Direct entry and browser Forward restored finding #715 open and focused about 81 px below the viewport top. [Forward to #715](direct-forward-79.jpg)

## G. Historical rule and draft evidence

The backend serializes persisted title, rank, ID, agent, severity, file, line, detail, evidence and eligible fix data. Quality rules carry their identity in the finding title and may include kind, symbol, standards source filename, quoted passage and recorded version. Finding #996 in review #90 shows an advisory for `review_smoke.py:1`, symbol `normalize_task_title`, source `python_coding_standards.md` and historical version `coding_standards`. A finding’s recorded version takes precedence over the review snapshot. Unrecognized or absent provenance receives a written qualification. The displayed explanation and eligible saved test code or docstring supply remediation where available. Code, quotes and drafts render as text. [Historical citation](historical-citation-90.jpg) · [Saved draft](draft-preview-90.jpg)

## H–I. Agent results and evidence semantics

Each specialist has a heading followed by recorded outcome, execution, coverage, accepted findings and draft enrichment. Accepted findings come from the review’s persisted `agent_counts`. A differing run count is labeled separately. Recorded notes, failures and failed scanner indicators remain visible when technical details are closed.

| Recorded combination | What the reader sees |
|---|---|
| OK with complete coverage | OK, execution state and Complete in independent fields. |
| OK with absent coverage | OK with execution, coverage and draft enrichment each marked Not recorded. |
| Completed execution and partial coverage | Completed and Partial together, including when the outcome is OK or degraded. |
| Degraded or failed outcome | Recorded reason and available notes. A zero count describes accepted findings only. |
| Not applicable or unknown coverage | The recorded value, alongside the independent execution state. |
| Missing agent or outcome | The specialist keeps its place. Missing evidence is labeled Not recorded, and the persisted accepted count remains visible. An unrecognized recorded outcome can read Unknown. |
| Enrichment skipped or failed | Its own status and any recorded explanation. Missing coverage leaves enrichment unrecorded. |

Technical disclosures expose recorded eligible/analyzed paths, exclusions and reasons, batches, enrichment counts, per-scanner status and raw detection metadata. A scanner observation never increments accepted counts. Gitleaks match messages are withheld in the raw detection list. The isolated scanner case shows two raw detections and one accepted Security finding. [Scanner count comparison](fixture-scanner-counts.jpg)

## J. Authenticated response comparison

Both journeys opened the saved result through the corresponding repository under installation `161715271`. Counts below follow Critical / High / Medium / Low / Info / Unknown. Specialist order is Security / Quality / Test gaps / Documentation.

| Saved review | Analysis and GitHub delivery | Reported / returned | Severity counts | Accepted by specialist | Outcomes and coverage |
|---|---|---:|---|---|---|
| DhyanMehta/httpx, PR #1, #79 | Completed · Posted | 16 / 16 | 0 / 1 / 4 / 11 / 0 / 0 | 1 / 0 / 9 / 6 | Four OK. No execution or coverage record for any specialist. |
| DhyanMehta/flask-task-api, PR #4, #90 | Completed · Posted | 3 / 3 | 0 / 0 / 1 / 1 / 1 / 0 | 0 / 1 / 1 / 1 | Four OK, four completed executions, four complete coverage records. |

The attached summaries project only the response fields used in the comparison. [#79 response](response-79.json) · [#90 response](response-90.json)

## K. Responsive measurements

CSS pixels. First finding y is relative to the document origin. Findings were unfiltered for each comparison. The first #79 finding starts collapsed, while the three-record #90 review opens its findings initially. The final column gives document scroll width and available layout width, which matched in every before/after sample for both records.

| Viewport | First finding y, both | Filter height | #79 first card height | #90 first card height | Scroll / available |
|---:|---:|---:|---:|---:|---:|
| 1920 | 780 → 768 | 64 → 64 | 84 → 75 | 262 → 298 | 1914 / 1914 |
| 1440 | 780 → 768 | 64 → 64 | 84 → 75 | 262 → 298 | 1434 / 1434 |
| 1024 | 776 → 764 | 64 → 64 | 84 → 75 | 262 → 304 | 1018 / 1018 |
| 768 | 949 → 937 | 64 → 64 | 84 → 75 | 277 → 304 | 762 / 762 |
| 700 | 1038 → 961 | 134 → 68 | 115 → 75 | 309 → 308 | 694 / 694 |
| 390 | 1288 → 1138 | 190 → 140 | 177 → 127 | 419 → 380 | 385 / 385 |
| 320 | 1332 → 1138 | 190 → 140 | 201 → 127 | 459 → 380 | 314 / 314 |

At 1440 px the first Security card in #79 went from 610 × 285 to 1232 × 116. At 320 px it went from 282 × 379 to 282 × 296. Expanded findings give the recorded explanation and draft more room at desktop widths. The compact phone section chooser preserves access to the overview, findings, agents, execution, delivery and eligible fix decisions. Screenshot heights vary by capture. The geometry uses document coordinates for comparisons. [#79 before](before-79.json) · [#79 after](after-79.json) · [#90 before](before-90.json) · [#90 after](after-90.json)

## L. Accessibility checks

The filter order is Severity, Agent, Search, then Clear filters when active. Native summaries support keyboard activation, findings have stable IDs, and paths wrap at narrow widths. The previous toolbar placed Agent before Severity and had no clear-all action. Filter targets measured 40 px on desktop and 44 px below 768 px, compared with 30 px and 44 px at baseline. Finding titles measured 17 px on desktop and 16 px below 768 px. Metadata and monospace paths use 14 px roles. The long synthetic draft occupied 1888 px inside a 257 px scrollable code region while the available and document widths both measured 314 px.

Visual inspection caught a Tailwind color/typography token collision on file paths. The corrected path measured 14 px JetBrains Mono, foreground `#AAB8CA` on `#101827` (8.81:1). Other representative contrast pairs were 16.22:1 for primary text on its panel, 9.75:1 for links on canvas and 8.69:1 for a High badge on its fill. Keyboard focus on the target summary had a visible indigo outline. These components use native disclosure and static jumps and inherit the existing reduced-motion rules. [Keyboard focus](keyboard-focus-90.jpg) · [Long path and code](fixture-unknown-long-path.jpg)

## M–O. Automated verification and build

| Check | Result |
|---|---|
| Focused Vitest run | 111 passed across 11 files. Included findingsEvidence, reviewWorkspace, readFlows, reliabilityFlows, finalFlow, writeFlows, reviewProgress, polling, SeverityBadge, FriendlyTimestamp and SharedFeedback. |
| Full frontend suite | 228 passed across 31 files. |
| Production build | TypeScript project build and Vite production bundle passed. |
| Whitespace | `git diff --check` passed. |

The new suite contributed 13 test cases covering combined filtering, reset, zero versus unavailable records, safe code rendering, historical provenance, unknown or hidden target resolution, focus during refresh, seven outcome/coverage combinations, scanner count separation and local interactions with zero additional requests. Existing suites exercise asynchronous deep links, permission loss, polling, uncertain writes and auto-fix guards with isolated responses.

## P. Authenticated screenshots

Each pair links the working-tree baseline followed by the accepted implementation. These are viewport screenshots of the running local application.

| Width | #79 findings | #79 agents | #90 findings | #90 agents |
|---:|---|---|---|---|
| 1920 | [Before](before-79-findings-1920.jpg) / [After](after-79-findings-1920.jpg) | [Before](before-79-agents-1920.jpg) / [After](after-79-agents-1920.jpg) | [Before](before-90-findings-1920.jpg) / [After](after-90-findings-1920.jpg) | [Before](before-90-agents-1920.jpg) / [After](after-90-agents-1920.jpg) |
| 1440 | [Before](before-79-findings-1440.jpg) / [After](after-79-findings-1440.jpg) | [Before](before-79-agents-1440.jpg) / [After](after-79-agents-1440.jpg) | [Before](before-90-findings-1440.jpg) / [After](after-90-findings-1440.jpg) | [Before](before-90-agents-1440.jpg) / [After](after-90-agents-1440.jpg) |
| 1024 | [Before](before-79-findings-1024.jpg) / [After](after-79-findings-1024.jpg) | [Before](before-79-agents-1024.jpg) / [After](after-79-agents-1024.jpg) | [Before](before-90-findings-1024.jpg) / [After](after-90-findings-1024.jpg) | [Before](before-90-agents-1024.jpg) / [After](after-90-agents-1024.jpg) |
| 768 | [Before](before-79-findings-768.jpg) / [After](after-79-findings-768.jpg) | [Before](before-79-agents-768.jpg) / [After](after-79-agents-768.jpg) | [Before](before-90-findings-768.jpg) / [After](after-90-findings-768.jpg) | [Before](before-90-agents-768.jpg) / [After](after-90-agents-768.jpg) |
| 700 | [Before](before-79-findings-700.jpg) / [After](after-79-findings-700.jpg) | [Before](before-79-agents-700.jpg) / [After](after-79-agents-700.jpg) | [Before](before-90-findings-700.jpg) / [After](after-90-findings-700.jpg) | [Before](before-90-agents-700.jpg) / [After](after-90-agents-700.jpg) |
| 390 | [Before](before-79-findings-390.jpg) / [After](after-79-findings-390.jpg) | [Before](before-79-agents-390.jpg) / [After](after-79-agents-390.jpg) | [Before](before-90-findings-390.jpg) / [After](after-90-findings-390.jpg) | [Before](before-90-agents-390.jpg) / [After](after-90-agents-390.jpg) |
| 320 | [Before](before-79-findings-320.jpg) / [After](after-79-findings-320.jpg) | [Before](before-79-agents-320.jpg) / [After](after-79-agents-320.jpg) | [Before](before-90-findings-320.jpg) / [After](after-90-findings-320.jpg) | [Before](before-90-agents-320.jpg) / [After](after-90-agents-320.jpg) |

| Interaction | #79 | #90 |
|---|---|---|
| Combined filters and one matching finding | [Search](search-79.jpg) | [Search](search-90.jpg) |
| No filter matches | [Empty selection](no-matches-79.jpg) | [Empty selection](no-matches-90.jpg) |
| Expanded finding | [Evidence](expanded-79.jpg) | [Evidence](expanded-90.jpg) |
| Stable fragment | [#715](fragment-79.jpg) | [#994](fragment-90.jpg) |
| Specialist evidence | [Security](technical-79.jpg) · [Mobile scanner detail](mobile-scanner-evidence-79.jpg) | [Security](technical-90.jpg) |

## Q. Read-only navigation traces

Each final instrumented journey recorded **15 GET attempts and zero writes**, from the scoped repository through the saved review and back. The temporary verification entry used the existing local session and real app, recorded the method and endpoint for application fetches and rejected non-GET methods. Filtering, clearing, opening disclosures and jumping to findings or sections added **zero application requests**. Each trace includes an intermediate snapshot and a final cumulative ledger. The counts use the final ledger once per review. [#79 journey](journey-79.txt) · [#90 journey](journey-90.txt)

## R. Isolated visual evidence

These clearly labeled synthetic records exercise cases missing from the authenticated reference pair.

| State | Screenshot |
|---|---|
| Confirmed zero reported findings | [Empty review](fixture-zero.jpg) |
| Unknown severity, long file path, absent provenance, long draft | [Expanded finding at 320 px](fixture-unknown-long-path.jpg) |
| Advisory classification, source, version and citation | [Advisory record](fixture-advisory.jpg) |
| Completed execution with partial coverage, degraded outcome, failed outcome, missing specialist, not-applicable coverage and provider-unavailable enrichment note | [Four specialist rows](fixture-coverage-matrix.jpg) |
| Two raw detections and one accepted Security finding | [Expanded scanner evidence](fixture-scanner-counts.jpg) |

## S. Limitations

The stored contracts have no separate impact or recommendation field and no general-purpose citation chunk ID. Enrichment accepts completed, skipped or failed. An unavailable provider can be described by a recorded note, and absent historical enrichment remains unrecorded. The UI does not retrieve current installation standards to reconstruct missing historical evidence. Browser and keyboard checks cover the listed records and viewport sizes. A full screen-reader or WCAG conformance assessment is outside these results.

## T. Decision

**GO for separate Phase 4c review and approval.** Phase 4b’s frontend, authenticated, responsive and build gates passed. Execution, delivery and auto-fix workflow presentation remain future work.
