# Phase 2c · Installation Settings navigation

**24 November 2026 · Implemented and verified · Awaiting review**

Installation Settings now opens from the selected account on Connected Repositories or any of the three repository views. A repository bookmark still checks access to its original repository before opening the installation-wide page.

## A. Git baseline and preservation

Branch `codex/durable-review-pipeline`, HEAD `dc9b6af4149764ae66e2ca10974c151a6bf819a0`. The initial index was empty. The working tree already contained 30 modified tracked frontend files, seven untracked frontend files, prior milestone reports and screenshots, the audit, planning files and unrelated documents. The Phase 2b fourth tab matched the approved migration boundary. Work proceeded in place. The index, HEAD and previous evidence were preserved.

## B. Exact Phase 2c files

| Area | Files |
|---|---|
| Route and canonical URL | `frontend/src/App.tsx`, `frontend/src/api/identity.ts`, `frontend/src/pages/InstallationSettingsPage.tsx` (new) |
| Installation entry points and bookmark resolver | `frontend/src/components/common/InstallationPicker.tsx`, `frontend/src/components/layout/ContextBar.tsx`, `frontend/src/pages/RepoListPage.tsx`, `frontend/src/pages/RepoDashboardPage.tsx` |
| Existing standards reader and form | `frontend/src/components/dashboard/SettingsTab.tsx` |
| Regression tests | `frontend/src/test/repositoryNavigation.test.tsx`, `frontend/src/test/reliabilityFlows.test.tsx` |
| Checklists and evidence | `UI_REGRESSION_CHECKLIST.md`, `tasks/todo.md`, this report and the 12 JPEGs in section L |

## C. Navigation architecture

Previously the dashboard identified the repository, authorized it through its installation's repository list and exposed an installation-wide form in its fourth tab. Now the repository has three views: Pull Requests, Analytics and Agent History. The desktop tablist and the mobile native chooser share this list. The installation selector offers a separate semantic Settings link when its selected account is active. The repository context shows that link with an authorized repository. Connected Repositories offers it independently of repository count. The global header retains its existing account menu.

## D. Dedicated route

`/settings/installation?installation_id=ID` is under the existing `ProtectedRoute`, `AuthProvider` and `InstallationProvider`. It reads installation membership, settings and standards. Direct entry requires zero repository reads. The page names its installation-wide scope, shows the account and known review mode, and provides a scoped return to the repository list. A single H1 identifies the destination. Coding standards have their own section heading.

## E. Bookmark compatibility

The dashboard recognizes `tab=settings` before ordinary invalid-tab normalization. It requests a fresh access check using the existing repository resource, coalescing an in-flight read. This also catches access revoked since a recent cached visit. Only a successful match of repository and installation issues a replace-navigation. The new URL drops `tab`, retains other query values including repeated keys, and uses the validated ID. The legacy branch mounts neither a PR view nor a standards form. Denied or missing repository access leaves the user at the original URL with recovery feedback.

Live example: `/repos/DhyanMehta/httpx?installation_id=161715271&tab=settings&from=bookmark` resolved to `/settings/installation?installation_id=161715271&from=bookmark`. Reload retained the canonical address. The router fixture also verified Back skips the consumed bookmark and Forward returns directly to Settings.

## F. Authorization and scoping

An explicit ID takes precedence over session selection. An invalid ID offers recovery, a suspended installation shows its suspension message, and an ambiguous selection requires the user to choose. Single and remembered selections are written into the canonical URL using replacement. The provider owns the selection throughout. A missing active membership unmounts the form. A denial from either settings reader hides its sibling data and form and exposes retry.

The settings and standards resource keys use both user and installation IDs. The form instance uses the same pair for its React key. Changing scope drops the staged file, validation and reset confirmation. Existing resource cancellation and version checks discard superseded responses. The input is checked again after asynchronous file validation before sending an upload.

## G. Standards and shared policy

The existing reader and mutation owner still uses GET settings, GET standards, multipart POST with field `file`, and confirmed DELETE on the installation's standards endpoint. Markdown extension, UTF-8 and 512 KiB checks remain in place. The form retains version, chunk and upload metadata and the historical-version explanation. Read access and admin-only mutations are enforced server-side in `backend/api/installations.py` and `backend/api/standards.py`. The scoped write key preserves busy and uncertain outcomes across navigation. Explicit reconciliation allows a user to retry after inspecting the result.

The Profile link carries the selected installation ID for return navigation. Policy administration continues to affect eligible active installations administered by the user. `ProfilePage.tsx` and `backend/api/profile.py` both use a versioned PATCH to `/profile/review-mode`; the existing conflict and server-confirmed success paths were covered in the focused suite.

## H. Responsive and accessibility verification

On each live Settings screen there was one installation select, one page heading and no repository identity panel. Measurements are CSS pixels. A scrollbar accounts for the difference between requested and available width.

| Viewport | Document scroll / available width | Installation select / refresh height |
|---:|---:|---:|
| 1920 | 1920 / 1920 | 40 / 40 |
| 1440 | 1440 / 1440 | 40 / 40 |
| 1024 | 1018 / 1018 | 40 / 40 |
| 768 | 768 / 768 | 40 / 40 |
| 700 | 700 / 700 | 44 / 44 |
| 390 | 385 / 385 | 44 / 44 |
| 320 | 314 / 314 | 44 / 44 |

At 320 px, Tab moved from Installation to its 44 px Settings link, with a visible solid outline. Enter opened the scoped page. The repository chooser listed all three views. At 700 px the global disclosure exposed scoped Repositories, Profile settings and Sign out; Escape returned focus to its trigger. Desktop tabs retained keyboard selection and panel associations in the regression tests.

## I. Focused tests

`npm test -- repositoryNavigation identity reliabilityFlows readFlows writeFlows profileMode Tabs Navbar ProtectedRoute auth callbackRecovery finalFlow` passed **89 tests across 12 files**. Existing tab keyboard and history assertions now exercise the three repository views, with separate assertions for the installation link and canonical page.

## J. Full frontend suite

`npm test` passed **156 tests across 25 files**. Phase 2b's previously recorded baseline was 144.

## K. Production build and Git checks

`npm run build` passed TypeScript and Vite production bundling. `git diff --check` passed. No dependency, backend source, schema or deployment changes were required.

## L. Authenticated screenshots and journeys

The running Vite app and FastAPI used the existing signed-in session for DhyanMehta, installation 161715271, repository DhyanMehta/httpx and saved review 79. The installation showed Automatic review mode and Default standards. Database, ChromaDB and configuration readiness were OK; the intentionally stopped worker accounted for readiness HTTP 503.

| Settings desktop | Tablet | Phone and compact |
|---|---|---|
| [1920 px](settings-1920.jpg) | [1024 px](settings-1024.jpg) | [700 px](settings-700.jpg) |
| [1440 px](settings-1440.jpg) | [768 px](settings-768.jpg) | [390 px](settings-390.jpg) · [320 px](settings-320.jpg) |

Additional captures show [Connected Repositories](connected-repositories-1440.jpg), [three desktop tabs](repository-tabs-1440.jpg), [mobile chooser and focused Settings link](repository-chooser-320.jpg), [resolved legacy bookmark](legacy-resolved-1440.jpg) and [700 px account menu](account-menu-700.jpg).

Verified live journeys included entry from the list and each repository view, direct URL, legacy URL, reload, scoped return to the list, Profile and Back/Forward, and navigation to saved review 79. All screenshots came from the ordinary authenticated frontend. A separate instrumented replay of these navigation paths used the real frontend entry point, session and backend, counted application fetch methods and would block any write attempt. It observed **34 GET calls and zero other methods**. The temporary verification entry was removed before the final build.

## M. Isolated fixture evidence

The live account had one installation using defaults. Vitest supplied the remaining states in `repositoryNavigation.test.tsx`, `writeFlows.test.tsx`, `reliabilityFlows.test.tsx` and `profileMode.test.tsx`.

| Scenario | Verified result |
|---|---|
| Signed out, member, admin and installation with zero repositories | Sign-in protection; members can read standards with disabled mutation controls; admins can stage an upload and confirm reset. The direct route makes exactly one settings and one standards GET and zero repository GETs. |
| Missing, remembered, ambiguous, invalid and suspended selection | Correct canonical selection or explicit recovery. The blocked states issue zero settings reads before a valid choice. |
| Lost membership, denied read, inaccessible repository and warm cached bookmark | Revoked membership hides the form. Either reader's access error gates the content. Legacy entry checks repository membership before resolving. |
| Scope switch, delayed response and resize | Old subscription aborted; late data discarded. Staged file cleared on switch. Resizing retains the same file input and request count. |
| Multipart upload, confirmed reset and uncertain result | Mock server returned the active custom version and subsequent defaults. An uncertain DELETE that settled after navigation remained associated with its original installation. Returning required explicit reconciliation and issued no automatic retry. |
| Policy and review compatibility | Versioned PATCH and conflict coverage, canonical review identity and finding hash, legacy PR resolution and guarded auto-fix behavior passed using test responses. |

## N. Checklist corrections

The regression checklist now records the current suite, the static SeverityBadge label, semantic button selectors, focus outline and measured contrast pairs, profile PATCH method, historical browser evidence and approved phase numbering. Phases 3–8 have separate pending entries. The implementation checklist in `tasks/todo.md` records completed gates and the outstanding product review.

## O. Remaining limitations

Member access, custom standards, revoked access, concurrent selection and write recovery were verified with isolated responses. Live checks used existing records and read navigation. Screen-reader speech, physical touch and a complete WCAG audit were outside this milestone.

## P. Recommendation

**GO for Phase 3 review and separate approval.** Phase 2c met its routing, authorization, responsive, test and build gates. Product review is pending.
