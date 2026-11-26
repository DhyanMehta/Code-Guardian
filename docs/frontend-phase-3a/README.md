# Phase 3a · Connected Repositories

**24 November 2026 · Implemented and verified · Awaiting review**

The Connected Repositories page now has one CodeGuardian workspace link per repository, a secondary GitHub link when the API supplies a matching URL, and a scoped search toolbar with a result count and clear recovery.

## A. Git baseline and preservation

Work started from branch `codex/durable-review-pipeline` at `dc9b6af4149764ae66e2ca10974c151a6bf819a0`, with an empty index, 32 tracked frontend modifications and the existing untracked frontend files, audit, plan and milestone evidence. The baseline matched Phase 2c. The branch, HEAD and index were preserved. The implementation is unstaged.

## B. Exact files modified

| Area | Files |
|---|---|
| Repository list and search | `frontend/src/pages/RepoListPage.tsx`, `frontend/src/components/common/SearchInput.tsx` |
| Tests | `frontend/src/test/repositoryList.test.tsx` (new), `frontend/src/test/readFlows.test.tsx`, `frontend/src/test/reliabilityFlows.test.tsx`, `frontend/src/test/Navbar.test.tsx`, `frontend/src/test/repositoryNavigation.test.tsx` |
| Milestone evidence and checklists | This report and 26 JPEGs in sections N–O, `tasks/todo.md`, `UI_REGRESSION_CHECKLIST.md` |

## C. Previous layout

The page placed a heading and GitHub App access link above the installation context. Search and refresh shared their own panel. The last successful fetch occupied another row before a stack of individual repository cards. Both the repository title and the companion action linked to the same workspace. Visibility relied on the icon, and the count used “open issues / PRs”. The list offered neither a result count nor an explicit clear action and kept search text after an installation switch.

Baseline keyboard order at 320 px was Skip to main content → brand → account menu → Update GitHub App access → Installation → Installation Settings → Search → Refresh → fetch time disclosure → repository title → duplicate workspace link.

## D. New layout

The page uses one list surface with separated rows, aligns its page heading, installation context and search toolbar, and limits the desktop content width to 1152 px. The result count and last successful fetch sit together in the toolbar. The selected installation and review mode remain together above the list. Settings stays available from the installation context even when repository data is empty.

## E. Repository actions

The repository name is a static heading. A filled **View pull requests** link with a repository-specific accessible name opens the scoped workspace. The quieter **GitHub** link carries an external-link icon and announces the new tab. It uses the original API string only when the parsed URL is HTTPS on `github.com` and its repository path matches the record. The new tab uses `noopener noreferrer`. Missing or mismatched URLs leave the workspace link available. Update GitHub App access stays a separate semantic anchor.

## F. Metadata and count

The API supplies `id`, `name`, `full_name`, `private`, `html_url`, `default_branch` and `open_issues_count`. Rows show full owner/name, visibility in text, default branch where present, and the combined open issues and pull requests count. Branch uses monospace. The metadata is 13 px at 768 px and above, and 14 px on compact layouts. A real zero remains visible.

## G. Search and scope behavior

Search filters the full repository name case-insensitively and ignores leading and trailing whitespace. The result count announces changes through a polite status. It retains the same text when a refresh returns an unchanged count. The clear icon and the no-match recovery button both clear the filter and return focus to the field. Ordinary refresh keeps the search and displays the last successful fetch. A scope change replaces the search instance, aborts its previous subscription, and renders the new installation's cache or loading state. A delayed previous response cannot replace it.

Initial loading, absent repositories, zero matches, failed reads, stale results, invalid scope and suspended access have distinct feedback. A failed transient refresh keeps the previous rows and shows a stale-data message and retry.

## H. Responsive measurements

CSS pixels, using the same five live records. Row dimensions describe the first repository. The visible count includes only whole rows. The two phone layouts stack metadata and actions, and the first row's GitHub and workspace links sit on the same line at 320 px.

| Viewport | First row before → after | Row width × height before → after | Fully visible before → after | After document scroll / client |
|---:|---:|---:|---:|---:|
| 1920 × 1080 | 405 → 366 | 1232 × 94 → 1150 × 82 | 5 → 5 | 1920 / 1920 |
| 1440 × 900 | 405 → 366 | 1232 × 94 → 1150 × 82 | 4 → 5 | 1440 / 1440 |
| 1024 × 768 | 401 → 362 | 970 × 94 → 969 × 82 | 3 → 4 | 1018 / 1018 |
| 768 × 900 | 397 → 358 | 714 × 94 → 718 × 82 | 4 → 5 | 768 / 768 |
| 700 × 900 | 453 → 414 | 646 × 94 → 645 × 106 | 4 → 4 | 694 / 694 |
| 390 × 844 | 615 → 544 | 353 × 142 → 351 × 162 | 1 → 1 | 385 / 385 |
| 320 × 760 | 615 → 544 | 282 × 142 → 281 × 162 | 1 → 1 | 314 / 314 |

At 1440 px, the 448 px search field begins at Y262, refresh sits immediately to its right, and the selector and Settings link share Y180. At 320 px, search retains 226 px and refresh is 44 × 44 px on the same line. The selector and Settings link sit above the toolbar. Search, refresh, installation selector, Settings and both row actions measured 40 px high at 768 px and above, and 44 px on narrower layouts. Longer live names grew to 178 px rows at 320 px. The isolated 80-character name wrapped across four lines with its full heading and no document overflow.

## I. Accessibility checks

The page has one H1, repository H2s, a named list, a visible search label and named action controls. At 390 px the keyboard sequence reached the workspace link followed by its GitHub link, with a visible solid outline after reverse tabbing. Clear recovery restored focus to Search. The skip link and single account menu were present, and Escape restored menu-trigger focus at 700 px.

The sampled action colors measured 6.29:1 for white on the base fill and 7.90:1 on the hover fill. Muted metadata on the list panel measured 8.81:1. These measurements cover the stated color pairs.

## J. Request efficiency and write safety

The list still uses the existing user- and installation-scoped repository read. The focused tests observed one initial repository request, one additional GET per manual refresh and zero per-row reads. Local filtering is in memory. A live trace loaded the five repositories, entered `HTTPX`, refreshed with the filter preserved, opened Pull Requests and followed saved review 79. Starting the instrumented development page recorded five fetch invocations, refresh added exactly one, and the full journey recorded 13 GET invocations and zero write attempts. The temporary trace and fixture page was removed before the final build.

## K. Focused tests

`npm test -- repositoryList SearchInput Button IconButton readFlows reliabilityFlows repositoryNavigation identity Navbar ProtectedRoute finalFlow` passed **77 tests across 11 files**. Updated assertions follow the new accessible name of the same scoped destination. The suite covers the remaining protected routes, flow history and prior navigation contracts.

## L. Full frontend suite

`npm test` passed **164 tests across 26 files**. The prior Phase 2c baseline was 156 across 25.

## M. Production build and Git checks

`npm run build` passed TypeScript and the Vite production build. `git diff --check` passed.

## N. Authenticated before and after screenshots

Both sets show the same existing DhyanMehta installation, ID 161715271, in the running local frontend with the five live repository records. The images may exclude the scrollbar gutter.

| Width | Before | After |
|---:|---|---|
| 1920 | [Baseline](before-1920.jpg) | [Redesign](after-1920.jpg) |
| 1440 | [Baseline](before-1440.jpg) | [Redesign](after-1440.jpg) |
| 1024 | [Baseline](before-1024.jpg) | [Redesign](after-1024.jpg) |
| 768 | [Baseline](before-768.jpg) | [Redesign](after-768.jpg) |
| 700 | [Baseline](before-700.jpg) | [Redesign](after-700.jpg) |
| 390 | [Baseline](before-390.jpg) | [Redesign](after-390.jpg) |
| 320 | [Baseline](before-320.jpg) | [Redesign](after-320.jpg) |

[Keyboard focus](focus-390.jpg) · [Matching search](search-match-390.jpg) · [No matches](search-empty-390.jpg) · [Clear recovery](search-cleared-390.jpg) · [Installation Settings](settings-390.jpg) · [Scoped Pull Requests workspace](workspace-1440.jpg)

## O. Fixture-only verification

The browser fixtures use synthetic installations and records with a visible fixture label. They cover [long names and multiple installations](fixture-long-320.jpg), [scope switching](fixture-switched-320.jpg), [empty repositories](fixture-empty-320.jpg), [first-read failure](fixture-failed-320.jpg), [stale data during a transient failure](fixture-stale-320.jpg) and [suspension](fixture-suspended-320.jpg). The regression suite verifies that the previous request is aborted and a response that arrives late is discarded, invalid scope cannot fall back to a remembered installation, and an empty installation can still open Settings.

## P. Remaining limitations

The live account provided one installation. Multiple-installation, denied access, empty and stale states were exercised with fixtures. The GitHub links were verified against the supplied URLs and anchor attributes. Physical touch and screen-reader speech were outside the verification performed.

## Q. Recommendation

**GO for review and separate approval of Phase 3b.** Phase 3a passed the focused and full test suites, production build and authenticated responsive acceptance.
