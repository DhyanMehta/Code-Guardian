# Backend reliability contract

This document describes the `Dhyan` implementation and supersedes older session notes.

## Review flow

1. A signed webhook or an authorized dashboard request creates a pending review in PostgreSQL. A repeated GitHub delivery ID returns the same review. Installation-less PAT webhooks require explicit `LEGACY_PAT_ENABLED=true`.
2. Run `python -m backend.worker` separately from the API. A PostgreSQL advisory lock serializes review attempts. Automatic pending revisions of the same PR are superseded by the newest queued revision. Manual requests remain individually queued.
3. The worker records the start, attempt and heartbeat, validates access, captures the active standards version, and checks out the requested head. The diff uses the PR merge base. Missing history fails explicitly; it does not silently become an empty diff or `HEAD~1` review.
4. Scanners, RAG and AST analysis run through the supervisor. Scanner failures and omitted triage produce degraded coverage. Raw scanner evidence remains available even when the LLM fails. Quality analysis uses bounded batches; reaching a limit is disclosed as degraded coverage.
5. Supported function-length and positional-parameter rules are checked against AST measurements and the cited limit. Other quality suggestions are labeled **Advisory**, carry informational severity, and are not verified violations. Test-gap results mean **no direct static test reference**, not proof of missing runtime coverage.
6. Findings, evidence, agent outcomes, summary and exact Markdown report are committed together. Historical missing outcomes are unknown, never implicitly successful. An incomplete zero-finding run does not say “No issues found.”
7. GitHub delivery has its own state and attempts. Delivery failure does not erase completed analysis. The worker retries pending/failed delivery up to three times; a stable comment marker helps reconcile an uncertain prior post. The report endpoint returns the saved snapshot.

The worker is intentionally serial and intended for one shared PostgreSQL database
and one local persistent Chroma volume. Each attempt has a hard process deadline.
An interrupted running review is retried up to `MAX_REVIEW_ATTEMPTS`, then failed.
The worker waits one provider window between review processes so restarting the
in-memory token limiter does not forget recent usage. This favors correctness over
high throughput; distributed scheduling is outside this implementation.

## Authentication and frontend contract

- Use cookie credentials (`credentials: "include"`). OAuth state and session cookies follow `COOKIE_SECURE`; set false only for local HTTP development.
- User access/refresh tokens are encrypted with `TOKEN_ENCRYPTION_KEY`. Existing users must sign in again after migration. Keep the encryption key stable and outside source control.
- Repository reads check the user's live accessible repositories. Review triggers, auto-fix creation and decisions additionally require repository write permission. Standards/settings changes require a verified personal owner or organization administrator.
- CORS supports GET, POST, PATCH and DELETE for configured origins. Cross-origin browser mutations are rejected. Logout and GitHub authorization-revocation events invalidate existing session versions.
- Review detail exposes `started_at`, `delivery_status`, `delivery_error`, `comment_id`, `standards_version`, finding `evidence`, and agent `raw_findings`.
- Standards upload/status exposes `version`. Upload creates a new collection before switching the database pointer. Reset clears that pointer; old collections remain available to earlier reviews. An explicitly selected missing collection fails rather than using unrelated defaults.
- Pull listings support `page` (default 1) and `per_page` (default 50, maximum 100).
- Approval identity comes from the authenticated session. The legacy `approved_by` request property is ignored; an empty request body is accepted.

## Auto-fix flow

Creation checks write access and current PR head, claims the operation, revalidates
drafts, and writes only inside the checkout. Qualified function identities prevent
same-name methods from receiving each other's fixes. Draft tests must parse and
contain a call; generated tests use distinct filenames and never overwrite an
existing generated file. Docstring edits must leave valid Python. One-line function
suites are skipped with a reason because they require a structural rewrite.

The prepared commit is recorded before pushing. A retry can reconcile that exact
commit after an interrupted push. Branch creation refuses to overwrite an existing
remote branch; the head is checked again before pushing. Approval is an atomic
decision bound to the recorded branch commit. No endpoint merges a branch, and
generated repository code is not executed by the review service.

## Setup and verification

Activate `backend/venv` and confirm the interpreter before running Python commands.
Configure `.env`, including the GitHub App, session and encryption keys, then run:

```powershell
python -m backend.bootstrap
uvicorn backend.main:app --host 127.0.0.1 --port 8080
# Second activated terminal:
python -m backend.worker
```

`bootstrap` migrates the configured application database, so back up existing data
before upgrading. It initializes default standards when absent. Docker Compose runs
the initializer before the API/worker and mounts their shared Chroma data volume.

```powershell
$env:CODEGUARDIAN_TEST_POSTGRES="1"
$env:CODEGUARDIAN_TEST_RUNTIME="1"
python -B -m pytest backend/tests -o addopts= -p no:cacheprovider --tb=short
python -B -m scripts.verify_backend_runtime --github --llm
```

PostgreSQL integration tests create and remove only randomly named `cg_test_...`
schemas. Unit tests mock GitHub and LLM responses and use temporary Chroma storage.
Runtime diagnostics run actual installed scanners on synthetic code, optionally
make a read-only GitHub App request and a small LLM request, and report unavailable
components explicitly. They do not publish comments or branches on a live PR.

The optional runtime pipeline test also runs real Git, all three scanners, RAG,
the supervisor and PostgreSQL together. Its LLM responses and GitHub comment
posting are explicitly mocked so it can assert stable report and draft output.

Readiness requires the current migration, default standards, credential configuration
and a recent worker heartbeat. A liveness response alone does not prove readiness.

## Verification record — 2026-10-06

- Windows virtual environment: all 450 tests passed, including opt-in PostgreSQL and real-scanner pipeline tests. `pip check` found no broken requirements.
- A clean Linux Docker build succeeded. It exposed and resolved the existing Semgrep/PyJWT dependency conflict; PyJWT is now pinned to compatible version 2.13.0.
- All 450 tests also passed inside that Linux image against disposable PostgreSQL, without relying on the local `.env`. Remaining warnings concern pytest collection of imported data classes and deprecated test-client cookie syntax.
- Fresh bootstrap against disposable PostgreSQL succeeded. The real API and worker started; readiness reported database, Chroma, worker and configuration all healthy. Liveness returned 200; unauthenticated review access returned 401.
- Native Bandit and Semgrep detected the expected synthetic assert/eval findings. Gitleaks completed successfully. GitHub App authentication and a small configured Groq JSON request succeeded.
- Staged changes passed Gitleaks secret scanning and `git diff --check`.

The application database was not migrated during verification. Full interactive
OAuth login and posting comments/pushing auto-fix branches on a live PR were not
exercised; their request handling and failure/retry paths were tested with mocks.
No frontend changes are included in this backend implementation.
