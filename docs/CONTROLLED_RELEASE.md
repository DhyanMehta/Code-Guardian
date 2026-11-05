# Controlled release candidate — November 6, 2026

Scope: `codex/durable-review-pipeline`. This candidate preserves the existing frontend work and the verified durable pipeline. It adds no automatic merge, no permission expansion and no automatic historical-comment editing. Deployment and the historical correction require separate approval. Nothing in this procedure has been executed against the regular database.

## Release review and checks

- Backend: **517 passed**, including opt-in PostgreSQL migration, recovery and runtime tests against disposable schemas in the dedicated `cg_acceptance` database on port 55436. Four benign imported-class collection warnings remain visible; see [the isolated verification](RELEASE_VERIFICATION_2026-11-06.md).
- Frontend: **96 passed in 21 files** after the release wording correction and regression assertion (14.54 seconds); TypeScript/Vite production build passed (4.92 seconds). Backend rerun completed in 80.35 seconds.
- The candidate Dockerfile was rebuilt as `codeguardian-release-candidate:20261106`, image `sha256:36754578d56cc1634e14a41658cf63b8efa9163b6e363d38dcd83a97c61bb855`. Both isolated API and worker were restarted on that exact image; liveness and readiness passed with database, Chroma, worker and configuration `ok`. The acceptance write guard remained mounted; no new review was queued. This local image is not a published deployment artifact.
- Gitleaks 8.18.4 scanned the complete staged candidate diff with redaction: no leaks found. Generated artifacts and secrets were separately checked against the staged filename inventory.
- Regression evidence repaired: the Odoo fixture previously contained no functions because its generator omitted async definitions. It now contains the four real pinned async functions and asserts their exact names before testing all length aliases.
- A deliberate future-import validator mutation makes its regression fail; restoring the original bytes makes it pass. The first attempt was blocked in fixture setup by Windows sandbox temporary-file permissions; the successful check ran outside that restriction.
- Fleet's outcome chart describes `ok` as an outcome, without claiming complete coverage. Per-agent cards retain explicit coverage/exclusion/draft counts.
- Auth, installation authorization and server-side auto-fix approval code are unchanged from the branch baseline. The full suite exercises permissions, stale-head checks, human decisions, immutable checkpoints, batching and recovery. Frontend auto-fix requests remain user actions; approval does not merge.
- A fresh explicitly read-only regular-database check confirms head `a84c2e13d930`, no coverage column, latest review ID 88, review 88 still containing 92 findings, delivery `posted` and comment ID 6637466320. The live GitHub body still matches the original snapshot SHA-256. Neither was corrected by release preparation.
- Local harnesses, credentials, downloaded repositories, binaries, logs and generated reports stay under ignored `scratch/` or `testsprite_tests/`. The unchanged, already-tracked `scratch/verify_checkpoint_a.py` is historical; adding an ignore rule does not remove it from history.
- Existing `UI_IMPLEMENTATION_ROADMAP.md`, `UI_REGRESSION_CHECKLIST.md` and `backend/backend-prd.md` are preserved locally and excluded from the candidate because their historical claims do not describe this implementation.
- Only curated report/audit documents under `docs/releases/review88/` are published. No database export, embeddings, session fixture or acceptance environment file belongs in the release.

The commit IDs and remote equality check are supplied in the release handoff; [the file inventory](RELEASE_CANDIDATE_FILES.md) lists each commit's paths. No release tag or merge is part of this candidate push. There is no tracked GitHub Actions workflow in this branch; remote PR-triggered workflow results are inspected after pushing when available. Local verification is not described as CI.

## Migration chain

The complete single-head chain, confirmed from the Alembic scripts, is:

```text
base
 -> ca09c608d315 -> b7f2a1e3d456 -> c3d9e1f2a7b8 -> c8a4b6d2e910
 -> d4e5f6a7b8c9 -> adf3640e2779 -> 08efb9630e44 -> 21e2df33e83d
 -> f1e2d3c4b5a6 -> a12b34c56d78 -> e23f45a67b89 -> f638a1d2b490
 -> a84c2e13d930 -> b94e6d27a041
```

The regular database's last verified version is `a84c2e13d930`. Its required upgrade is **only `b94e6d27a041`**, adding nullable `review_agent_runs.coverage TEXT`, with no invented historical backfill. The new-to-Git `a84c2e13d930` script must also be shipped: it already exists in that database's history and adds/schedules `reviews.delivery_retry_at`. Do not stamp the head or skip revisions. The PostgreSQL suite verifies fresh-chain migration and rollback/re-upgrade in isolated schemas.

## Pre-deployment gate

1. Approve the exact candidate SHA, intended database identity, deployment configuration and downtime window. Record the previous API/worker image or checkout, frontend bundle, Python dependencies and migration head. Do not deploy from the dirty development folder; use a clean checkout of the approved SHA or its built image.
2. Stop new review requests and GitHub webhook ingress at the proxy. Queue inspection is read-only: list pending/running reviews, attempts, heartbeat, standards version, delivery state and checkpoints. Let active work finish if possible. Stop **all** API/worker instances across machines, not just one terminal. Preserve unfinished checkpoints; do not reset rows to force work.
3. Identify the actual PostgreSQL server/database/user and persistent Chroma directory/volume. This installation has used native PostgreSQL; the repository Compose file starts a separate database on port 5432. Starting an empty Compose volume does not upgrade native data. Do not run the default Compose stack against an unreviewed topology.
4. Take a PostgreSQL custom-format backup and globals/role backup with the installed PostgreSQL tools. Use protected `PGPASSFILE`/service configuration; do not put passwords in command history. Keep database and Chroma backups outside the repository, with restricted access. Preserve the original token-encryption key, session secret and GitHub App key; rotating them is outside this release. Check `pg_restore --list` and perform a restore rehearsal in a separate disposable database before the approved cutover.
5. Compare `SELECT version_num FROM alembic_version` with `a84c2e13d930`; confirm `coverage` absent. Record database name/server, row counts and review 88's report hash, finding IDs, comment ID, agent rows and delivery state. Confirm GitHub App permissions, callback/setup URLs, public accessibility, installation selection and webhook secret. No permission changes are required.

### Concrete native Windows procedure (after approval only)

Use a clean checkout at the approved SHA with its own prepared `backend/venv`. The approved application environment must supply `DATABASE_URL` for the **regular** database and the existing `CHROMA_PERSIST_DIR`. Do not copy the acceptance environment. Provision dependencies from the pinned requirements and parser lockfile before maintenance; no global Python installs.

```powershell
. ./backend/venv/Scripts/Activate.ps1
(Get-Command python).Source
python -m alembic current
python -m alembic heads
```

Require current `a84c2e13d930`, head `b94e6d27a041`. PostgreSQL tools use libpq connection configuration, not SQLAlchemy's `postgresql+psycopg2` URL:

```powershell
# PGHOST, PGPORT, PGDATABASE, PGUSER and protected PGPASSFILE identify the approved DB.
# These example backup paths must exist on the protected backup volume.
pg_dump --format=custom --file D:/CodeGuardianBackups/pre-b94.dump
pg_dumpall --globals-only --file D:/CodeGuardianBackups/pre-b94-globals.sql
pg_restore --list D:/CodeGuardianBackups/pre-b94.dump
# After successful independent restore rehearsal and quiescing all writers:
python -m alembic upgrade b94e6d27a041
python -m alembic current
```

Check every command's exit code; abort on failure. Require exactly one migration head and the nullable coverage column. Start the API and worker from the **same clean release**, in separate service processes with the same environment and venv:

```powershell
. ./backend/venv/Scripts/Activate.ps1
(Get-Command python).Source
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

```powershell
. ./backend/venv/Scripts/Activate.ps1
(Get-Command python).Source
python -m backend.worker
```

Use the existing service manager for persistent/background processes. Keep ingress paused while checking startup; workers can process existing queued jobs/deliveries as soon as started, so obtain explicit approval for draining those jobs or ensure the queue is empty first. There is no claimed dry-run switch that makes a normal worker safe from GitHub writes.

In `frontend/`, set `VITE_API_BASE_URL` to the approved externally reachable API origin, then run `npm ci` and `npm run build`. Publish `dist/` atomically to the existing static host with SPA fallback and retain the previous bundle. Production TLS, CORS, cookie security and OAuth origins must match that deployment. `npm run preview` was an isolated verification server, not the proposed production host.

### Container alternative

Build the actual Dockerfile from the clean approved SHA:

```powershell
docker build -t codeguardian:<approved-sha> -f backend/Dockerfile .
```

The image activates `/app/backend/venv` through `PATH`. API entry point: `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`; worker: `python -m backend.worker`; migration: `python -m alembic upgrade b94e6d27a041`. Use an approved env file outside Git, read-only App-key mount and persistent Chroma mount. With native host PostgreSQL on Docker Desktop, the container database host typically becomes `host.docker.internal`; verify the actual target first. Keep the same database identity and data. Review a topology-specific Compose override before using Compose; the supplied default database URL and volume are not a production migration plan.

### Post-deployment checks before reopening ingress

- Confirm API and worker image IDs/release SHA match, no old worker survives and migration head is `b94e6d27a041`. Logs must contain no missing-column/parser/scanner/startup errors. Node and the locked TypeScript dependency must be available to the worker.
- GET `/health/live` => 200 and `alive`; GET `/health/ready` => 200 and database/Chroma/worker/configuration `ok`. The worker heartbeat must be newer than 90 seconds. Liveness alone is insufficient.
- Verify OAuth with an actual authorized account and repository selection. An unauthorized user must not access another installation's reports/settings/actions. Confirm frontend assets and direct SPA routes load.
- Read existing review details, report endpoint, Fleet and analytics; compare SQL/API/UI counts, outcomes, coverage and draft statuses. Review 88 must still have 92 observations until separately corrected; historical coverage remains unknown.
- Inspect the queue and delivery retry state before restoring ingress. Separately approve any new live review, GitHub-publishing smoke test or auto-fix operation. Reopen normal traffic only within the approved release window/scope.

## Version overlap and rollback

The schema addition is nullable and structurally additive, but **do not run mixed workers**. Validation/parser digests invalidate incompatible saved outputs; older binaries may ignore new metadata and regenerate results. A single advisory lock limits concurrent work, not semantic differences between versions. Cross-platform line-ending differences in fingerprinted source can also invalidate reuse safely, rather than guaranteeing no repeated provider work. Preserve old checkpoints and allow only the approved worker to resume compatible entries.

Old readiness code compares the database revision to its own exact Alembic head. Leaving the DB at `b94e6d27a041` while reverting to code expecting `a84c2e13d930` will fail readiness even though the column is additive. Therefore do not promise an automatic schema-retaining binary rollback.

The pre-candidate branch baseline `a4f27b3` has migration head `f638a1d2b490`, not `a84c2e13d930`; the latter script was previously uncommitted although already applied locally. Blindly checking out that baseline is therefore **not** the rollback procedure. Before production approval, identify and rehearse an archived previous runtime compatible with `a84c2e13d930` (including that migration script), or approve a separately rehearsed restore/version pairing. If no such artifact exists, rollback readiness is a deployment blocker until that pairing is prepared.

If rollback is approved: pause ingress; stop all new workers/API; export post-cutover findings, coverage/checkpoints and correction audit; back up the current DB; use the **release candidate's** migration scripts and environment to run `python -m alembic downgrade a84c2e13d930`; verify the head; then restore the previous compatible API/worker release and frontend bundle. This downgrade drops coverage metadata; archive it first. Do not downgrade below `a84c2e13d930`. Verify readiness, worker heartbeat, queue/delivery states and authorization before resuming. If migration failed, inspect the actual revision/column state before deciding whether any downgrade is needed.

Restore the full database backup only for a separately approved recovery requiring it: it discards post-backup changes unless a reviewed point-in-time recovery strategy preserves them. Never delete checkpoint rows merely to make rollback pass. No historical comment correction should be coupled to the migration transaction.

## Historical review 88 correction

The curated [85-observation preview](releases/review88/corrected-comment-preview.md), [original snapshot](releases/review88/original-comment-snapshot.md), [audit](releases/review88/correction-audit.json), [source audit](releases/review88/source-audit.json), [manifest](releases/review88/correction-manifest.json) and [verification summary](releases/review88/verification-summary.json) are part of this candidate. They contain no provider credentials or raw database backup. The procedure is [REVIEW88_COMMENT_CORRECTION_PLAN.md](REVIEW88_COMMENT_CORRECTION_PLAN.md).

The preview is **85 justified observations**, not 85 unique verified defects: Security 47, Quality 14, Test Gap 7, Documentation 17. Quality comprises three measured violations, ten source-corroborated documentation advisories and one explicitly unverified informational import-style interpretation. Four agents executed historically; absence of complete coverage is not absence of execution. The new isolated 89-observation result is a separate dataset with four added frontend static-reference gaps; it must never replace the historical snapshot wholesale.

After separate approval for DB correction and editing comment 6637466320: stop all delivery workers, preserve original rows/snapshot/checkpoints and acquire an operator lock; compare all expected IDs/hashes; PATCH only that existing comment ID; read it back; reconcile the audited DB transaction to exactly 85 with the same comment ID; verify SQL/report/API/UI/comment agreement and exactly one marker; only then restart delivery. Never queue automatic delivery of a changed historical body. The normal automatic reconciler matches exact bodies and could otherwise create a duplicate. Hash-match retries and a persisted operator audit/journal handle a GitHub-success/DB-failure split without creating another comment. Abort on unknown hashes/concurrent edits rather than overwriting them.

## Remaining limitations and approval checklist

- Scoped JS/TS/TSX analysis covers exported functions, relative named/default test imports and existing JSDoc parameter consistency. It does not establish runtime coverage, resolve arbitrary alias/re-export graphs, or execute generated drafts.
- Frozen Python standards intentionally exclude eight Quality files in the pinned mixed-language PR. Unknown historical metadata is not backfilled. Optional drafts can be capped/skipped; human inspection and approval remain required.
- The earlier cold isolated run was 622.449 seconds with 18 dispatched provider requests and 31,245 reported tokens; one dispatched request returned no usage. Waiting durations overlap. No comparable performance improvement is claimed and this release preparation repeats no expensive provider analysis.
- Four pytest collection warnings are benign, unsuppressed imported helpers. User OAuth in the target deployment and real GitHub publication remain post-approval acceptance checks; isolated fixture-session tests do not prove them.

Approval items: exact candidate SHA and topology; backup/restore rehearsal; regular DB upgrade and service cutover (including any queued writes); rollback downtime/data handling; separate historical DB correction and existing-comment PATCH; separately scoped new live-review/auto-fix tests. The source candidate can be reviewed/pushed independently. Production rollout has not been executed or declared validated.
