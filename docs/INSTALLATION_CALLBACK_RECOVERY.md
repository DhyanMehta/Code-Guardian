# Installation callback recovery — 2026-10-21

Implemented on Dhyan; changes remain uncommitted.

## Findings and changes
- GitHub public visibility resolved authorization for the fresh account (user confirmed).
- Missing code/state previously left the callback with an error and unresolved auth loading.
- Incomplete callbacks now check the existing session, offer retry/sign-in, and recover installation returns through server-verified access.
- Valid OAuth callbacks still require backend CSRF validation. Rejected exchanges do not fall back to installation access.
- Installation returns without a session now offer sign-in and preserve a bounded internal setup destination, including when the user already has installations.
- The verified GitHub App slug was explicitly configured in local .env. Client ID matched authenticated GitHub App metadata.
- README documents distinct OAuth callback/setup URLs and disabling OAuth during installation for the current two-step design.

## Verification
- Backend: 478 passed with PostgreSQL/runtime checks enabled; four existing collection warnings. Initial sandbox run failed in shared fixture setup; permitted retry passed.
- Frontend: 94 passed, including 11 new callback recovery tests.
- Production TypeScript/Vite build passed.
- Real browser: cleaned callback displays usable sign-in recovery; installation return without a session displays Sign in and continue setup.
- User confirmed signing in again displayed the repository selected during installation.

## Remaining external verification
The user confirmed the callback URL, but the GitHub App Setup URL and OAuth-during-installation checkbox were not inspected. The connected browser cannot access the user's Brave session. Recommended setup URL is http://localhost:5173/auth/install, OAuth during installation disabled, and Redirect on update enabled. A fresh uninterrupted installation roundtrip with those settings remains to be verified. No repository review was rerun and no changes were committed or pushed.
