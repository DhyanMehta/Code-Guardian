# Phase 7 · Administration and entry acceptance

**Passed on 26 November 2026.** Phase 7 covers Installation Settings, Coding Standards, shared review automation, Profile, the public landing page, sign-in recovery and GitHub App onboarding. The authenticated walkthrough recorded **11 GET attempts and zero writes**. The three live pages and four isolated entry states were captured before and after at seven widths.

[Installation Settings](evidence/after-settings-1440.jpg) · [Profile](evidence/after-profile-1440.jpg) · [Public landing](evidence/after-home-1440.jpg)

## Git baseline and files

The branch was `codex/durable-review-pipeline` at `dc9b6af4149764ae66e2ca10974c151a6bf819a0`, one commit ahead of its tracking branch. The index was empty. Earlier milestones were present as tracked edits and untracked reports, components, tests and screenshots. Their work stayed in place.

| Files | Change |
|---|---|
| `frontend/src/pages/InstallationSettingsPage.tsx`, `frontend/src/components/dashboard/SettingsTab.tsx` | Installation identity and scope, scoped freshness, active standards, staged file, validation and receipts |
| `frontend/src/components/common/ConfirmationDialog.tsx`, `frontend/src/components/common/WriteFeedback.tsx` | Native destructive confirmation and access to reconciliation after a successful read |
| `frontend/src/pages/ProfilePage.tsx` | Account identity, persisted policy, version-bound draft, affected installations and confirmed result |
| `frontend/src/pages/HomePage.tsx`, `frontend/src/components/layout/Navbar.tsx` | Public specialist and workflow descriptions, sign-in hierarchy, shared navigation and feedback |
| `frontend/src/pages/AuthCallbackPage.tsx`, `frontend/src/pages/InstallationReturnPage.tsx`, `frontend/src/pages/OnboardingPage.tsx` | Sign-in progress, recoverable callback, expiration, installation verification and access recovery |
| `frontend/src/components/common/EntryPanel.tsx`, `frontend/src/components/common/ProtectedRoute.tsx`, `frontend/src/components/common/OnboardingEmptyState.tsx`, `frontend/src/components/common/InstallationPicker.tsx` | Shared entry presentation, accessible actions and scoped access feedback |
| `frontend/src/test/administration.test.tsx`, `frontend/src/test/repositoryNavigation.test.tsx`, `frontend/src/test/profileMode.test.tsx`, `frontend/src/test/writeFlows.test.tsx` | Form, receipt and scope regressions plus updated interaction assertions |
| `tasks/todo.md`, `UI_REGRESSION_CHECKLIST.md`, `docs/frontend-phase-7/` | Milestone tracking, report and evidence |

## Finding resolution

| Finding | Resolution |
|---|---|
| CG-UX-003 and CG-UX-029 | The public page uses factual capability descriptions and static cards. The accepted factual footer remains the shell identity. |
| CG-UX-004, CG-UX-013 and CG-UX-019 | One picker controls the installation. The page names the selected account, role and mode. Shared automation routes to Profile. The previously guarded Settings bookmark remains available. |
| CG-UX-005 and CG-UX-010 | Settings, Profile and entry use established heading, support, status, link and button roles. Buttons handle operations and links lead to destinations. |
| CG-UX-009 and CG-UX-018 | A scoped freshness disclosure reports successful fetches and independent read failures. Recorded upload times use FriendlyTimestamp with the exact source timestamp available on demand. |
| CG-UX-016 and CG-UX-028 | Protected checks, callbacks, expired sessions, missing access and explicit cancellation have readable states and recovery actions. The preexisting repository empty state and account menu were rechecked. |
| CG-UX-021 and CG-UX-022 | Active default/custom source leads the form. Technical metadata, file validation, safe destructive confirmation and confirmed receipts have distinct presentation. |
| CG-UX-023 and CG-UX-024 | The 7:5 desktop policy and impact columns stack on narrow screens. The draft, affected accounts, persisted modes and confirmed result have distinct labels. The receipt clears on edit. |

## Installation Settings and Coding Standards

The selected installation and its role come from the existing InstallationProvider. The account strip names the active installation and links to the shared policy in Profile. Coding Standards has separate active and upload panels. The active panel displays the current source, a filename and date when available, and a disclosure for stored version and chunk metadata. Missing metadata is explicit. The authorized live installation was using defaults.

The native file input associates the Markdown, UTF-8 and 512 KiB requirements with the field. A validation error is included in its accessible description. A selected file shows its filename and exact byte count. Replace via the picker or clear explicitly. The validation generation and file identity guard prevent an earlier read from applying to a replacement. The keyed installation form discards staged state on a scope change and ignores late receipts. The existing successful response gates clearing the file and announcing a receipt. Recoverable and uncertain failures retain the selection.

Reset uses a named native dialog with the selected account and the effect across its repositories. Cancel receives focus. Escape dismisses the dialog and returns focus to Reset. The destructive action selects defaults for subsequent reviews. Existing reviews retain their recorded versions. The reset receipt follows the validated response.

| Contract | Preservation |
|---|---|
| GET installation settings and standards | Existing scoped reads with source-specific recovery |
| POST installation standards | Existing multipart field `file`, administrator gate and one scoped write at a time |
| DELETE installation standards | Existing endpoint, native confirmation and validated installation ID |
| Authorization | Member read-only access, provider gating for invalid/suspended selections and server denial precedence |
| Uncertain writes | Restore a successful current read, then explicitly reconcile before another attempt |

## Profile and shared automation

Profile shows signed-in identity separately from shared administration. Current persisted modes and the proposed mode appear beside the affected installations. All names are available before Apply, with additional accounts disclosed after the first five. The draft uses the version of its source snapshot. The shared impact copy states who is affected and explains what happens to queued reviews and newly connected installations. Apply identifies the affected count and is disabled for an unchanged mode, unavailable policy or unresolved write.

The existing `PATCH /profile/review-mode` sends `review_mode` and the server version. A version conflict refreshes the scope and clears the attempted draft so the user can review and choose again. An uncertain result stays locked until the current policy is read and the user explicitly reconciles it. Only the returned mode and count produce a confirmed receipt.

## Public and entry states

The landing page introduces GitHub PR reviews and the Security Agent, Quality Agent, Test Gaps Agent and Documentation Agent. The main sign-in is visually primary. The header keeps its secondary action and the established return-path behavior. Callback, expired session and installation return use the same entry card hierarchy. They describe the operation underway, name the recovery action and preserve the configured GitHub App destination and verified access checks. The callback uses the existing exchange and strips callback values from display. Protected routes keep their existing access checks and redirects.

## Automated gates

| Check | Result |
|---|---|
| Focused administration, write, policy, repository, entry and shared component suites | **122 passed** in 15 files |
| Full frontend suite | **266 passed** in 35 files |
| Production build | Passed |
| `git diff --check` | Passed |

Coverage includes direct and legacy Settings routes, zero-repository installations, administrator and member reads, unsupported extensions, encoding and size, replacing and clearing files, delayed validation and writes across installations, reset focus, multipart upload and confirmed reset, write uncertainty and duplicate prevention. It also covers the versioned shared policy, no-op, mixed policy, conflict, no administered installations, stale receipts, signed-out and protected routes, callback recovery and verified installation return. Mutation tests used isolated responses.

## Responsive and accessibility verification

The browser measured the original and redesigned pages at 1920, 1440, 1024, 768, 700, 390 and 320 CSS pixels. All measured document widths matched the available width. At 1440/320, the scoped Settings refresh and Upload controls measured 40/44px high, the native file field 50/54px, and the Profile Apply control 40/44px. Callback retry and installation refresh measured 40/44px. The shared design tokens retain 15px supporting and control text and use a visible focus outline. At 320px the affected-installations list precedes Apply. Long account names wrap in the policy impact list.

The fixture dialog focused Cancel on entry and restored focus to Reset on Escape. The write suite verified the canceled dialog sent zero DELETE requests. The selected-file error is linked to the native control, and the uploaded and reset receipts are announced as status. [Viewport findings and GET summary](evidence/verification-summary.json) · [Settings geometry](evidence/after-settings.json) · [Profile geometry](evidence/after-profile.json) · [Dialog focus](evidence/fixture-reset-focus.json)

### Authenticated before and after

| Width | Installation Settings | Profile | Connected Repositories |
|---:|---|---|---|
| 1920 | [Before](evidence/before-settings-1920.jpg) · [After](evidence/after-settings-1920.jpg) | [Before](evidence/before-profile-1920.jpg) · [After](evidence/after-profile-1920.jpg) | [Before](evidence/before-repos-1920.jpg) · [After](evidence/after-repos-1920.jpg) |
| 1440 | [Before](evidence/before-settings-1440.jpg) · [After](evidence/after-settings-1440.jpg) | [Before](evidence/before-profile-1440.jpg) · [After](evidence/after-profile-1440.jpg) | [Before](evidence/before-repos-1440.jpg) · [After](evidence/after-repos-1440.jpg) |
| 1024 | [Before](evidence/before-settings-1024.jpg) · [After](evidence/after-settings-1024.jpg) | [Before](evidence/before-profile-1024.jpg) · [After](evidence/after-profile-1024.jpg) | [Before](evidence/before-repos-1024.jpg) · [After](evidence/after-repos-1024.jpg) |
| 768 | [Before](evidence/before-settings-768.jpg) · [After](evidence/after-settings-768.jpg) | [Before](evidence/before-profile-768.jpg) · [After](evidence/after-profile-768.jpg) | [Before](evidence/before-repos-768.jpg) · [After](evidence/after-repos-768.jpg) |
| 700 | [Before](evidence/before-settings-700.jpg) · [After](evidence/after-settings-700.jpg) | [Before](evidence/before-profile-700.jpg) · [After](evidence/after-profile-700.jpg) | [Before](evidence/before-repos-700.jpg) · [After](evidence/after-repos-700.jpg) |
| 390 | [Before](evidence/before-settings-390.jpg) · [After](evidence/after-settings-390.jpg) | [Before](evidence/before-profile-390.jpg) · [After](evidence/after-profile-390.jpg) | [Before](evidence/before-repos-390.jpg) · [After](evidence/after-repos-390.jpg) |
| 320 | [Before](evidence/before-settings-320.jpg) · [After](evidence/after-settings-320.jpg) | [Before](evidence/before-profile-320.jpg) · [After](evidence/after-profile-320.jpg) | [Before](evidence/before-repos-320.jpg) · [After](evidence/after-repos-320.jpg) |

### Isolated entry before and after

| Width | Public landing | Incomplete OAuth callback | Canceled installation return | Expired session |
|---:|---|---|---|---|
| 1920 | [Before](evidence/before-home-1920.jpg) · [After](evidence/after-home-1920.jpg) | [Before](evidence/before-callback-1920.jpg) · [After](evidence/after-callback-1920.jpg) | [Before](evidence/before-onboarding-1920.jpg) · [After](evidence/after-onboarding-1920.jpg) | [Before](evidence/before-expired-1920.jpg) · [After](evidence/after-expired-1920.jpg) |
| 1440 | [Before](evidence/before-home-1440.jpg) · [After](evidence/after-home-1440.jpg) | [Before](evidence/before-callback-1440.jpg) · [After](evidence/after-callback-1440.jpg) | [Before](evidence/before-onboarding-1440.jpg) · [After](evidence/after-onboarding-1440.jpg) | [Before](evidence/before-expired-1440.jpg) · [After](evidence/after-expired-1440.jpg) |
| 1024 | [Before](evidence/before-home-1024.jpg) · [After](evidence/after-home-1024.jpg) | [Before](evidence/before-callback-1024.jpg) · [After](evidence/after-callback-1024.jpg) | [Before](evidence/before-onboarding-1024.jpg) · [After](evidence/after-onboarding-1024.jpg) | [Before](evidence/before-expired-1024.jpg) · [After](evidence/after-expired-1024.jpg) |
| 768 | [Before](evidence/before-home-768.jpg) · [After](evidence/after-home-768.jpg) | [Before](evidence/before-callback-768.jpg) · [After](evidence/after-callback-768.jpg) | [Before](evidence/before-onboarding-768.jpg) · [After](evidence/after-onboarding-768.jpg) | [Before](evidence/before-expired-768.jpg) · [After](evidence/after-expired-768.jpg) |
| 700 | [Before](evidence/before-home-700.jpg) · [After](evidence/after-home-700.jpg) | [Before](evidence/before-callback-700.jpg) · [After](evidence/after-callback-700.jpg) | [Before](evidence/before-onboarding-700.jpg) · [After](evidence/after-onboarding-700.jpg) | [Before](evidence/before-expired-700.jpg) · [After](evidence/after-expired-700.jpg) |
| 390 | [Before](evidence/before-home-390.jpg) · [After](evidence/after-home-390.jpg) | [Before](evidence/before-callback-390.jpg) · [After](evidence/after-callback-390.jpg) | [Before](evidence/before-onboarding-390.jpg) · [After](evidence/after-onboarding-390.jpg) | [Before](evidence/before-expired-390.jpg) · [After](evidence/after-expired-390.jpg) |
| 320 | [Before](evidence/before-home-320.jpg) · [After](evidence/after-home-320.jpg) | [Before](evidence/before-callback-320.jpg) · [After](evidence/after-callback-320.jpg) | [Before](evidence/before-onboarding-320.jpg) · [After](evidence/after-onboarding-320.jpg) | [Before](evidence/before-expired-320.jpg) · [After](evidence/after-expired-320.jpg) |

## Live request trace

The existing authenticated session returned HTTP 200 for `GET /auth/me`. The journey entered Connected Repositories, opened Settings for DhyanMehta, followed Shared review automation to Profile, then returned through Settings to the scoped repository list. The trace includes 11 GET attempts, seven HTTP 200 responses and four development cancellations. The browser verification forwarded only reads to the live API. [Live navigation trace](evidence/live-navigation-requests.json)

## Isolated mutation and recovery evidence

| Scenario | Verified state |
|---|---|
| Invalid file | Associated extension error and disabled upload. [Fixture capture](evidence/fixture-invalid-file.jpg) |
| Confirmed upload and reset | One mocked multipart POST and one mocked DELETE. The upload receipt records the returned file and version, then reset shows confirmed defaults. [Upload](evidence/fixture-upload-receipt.jpg) · [Reset dialog](evidence/fixture-reset-dialog.jpg) · [Reset receipt](evidence/fixture-reset-receipt.jpg) · [Fixture trace](evidence/fixture-standards-requests.json) |
| Uncertain upload | One mocked POST returned 503, the file stayed staged and retry required reconciliation. [Fixture capture](evidence/fixture-uncertain-upload.jpg) · [Fixture trace](evidence/fixture-uncertain-requests.json) |
| Mixed policy and conflict | The mixed fixture listed both names before Apply. A successful mocked PATCH confirmed both, and a separate 409 fixture refreshed to one eligible installation. [Impact](evidence/fixture-mixed-impact.jpg) · [Receipt](evidence/fixture-mixed-result.jpg) · [Conflict](evidence/fixture-conflict-result.jpg) · [Success trace](evidence/fixture-mixed-requests.json) · [Conflict trace](evidence/fixture-conflict-requests.json) |
| Member and onboarding | Member controls were disabled, pending approval was recoverable, and an empty repo list retained its scoped settings link. [Member](evidence/fixture-member.jpg) · [Approval pending](evidence/fixture-pending.jpg) · [Empty repository list](evidence/fixture-empty.jpg) |

## Limitations and next gate

**GO for the separately authorized Phase 8 audit.** The live account was an administrator with default standards and one administered installation. Member restrictions, multiple installations, mutation outcomes and signed-out states used isolated responses. Browser automation timed out while controlling the operating-system file chooser. A labeled fixture then staged synthetic files on the actual native input and exercised browser validation and the explicit upload action. The operating-system picker itself remains outside the completed browser interaction checks. The browser verification covers one browser environment. Phase 8 and the Git commit remain pending.
