# Release verification — November 6, 2026

The requested isolated workflow passes. This document records verification before release-candidate commits on `codex/durable-review-pipeline`. Deployment and correction of the historical public comment remain approval steps. See [the controlled release procedure](CONTROLLED_RELEASE.md) for the subsequent candidate review, push and deployment gates.

| Requirement | Result | Evidence |
| --- | --- | --- |
| Audit all original observations | PASS after corrections | `scratch/review88-full-source-audit.json` checks all 92 original entries. The earlier 87-item preview retained two false module advisories. The corrected preview has 85 observations. |
| Docker image build | PASS | Actual backend Dockerfile built with Node 22.22.2, TypeScript 5.7.3 and installed Python/scanner dependencies. Logs `scratch/docker-build-release-20261106.log`, image identity `scratch/acceptance-image-id.txt`. |
| API/worker/database/frontend startup | PASS | Isolated API readiness reports database, Chroma, worker and configuration all `ok`. Production frontend build served on port 15173. API on 18080, dedicated PostgreSQL on 55436. |
| Full migration chain | PASS | Fresh temporary schema in database `cg_acceptance`, upgrade to `b94e6d27a041`, downgrade coverage migration, upgrade again, nullable coverage column verified. `scratch/acceptance-migration-proof.json` and chain log. |
| Regular database preservation | PASS | Revision remains `a84c2e13d930`; coverage column remains absent; review 88 retains 92 rows and its original report; latest regular review ID remains 88. Checks used read-only transactions. |
| Pinned real PR and all four agents | PASS | Real checkout of `DhyanMehta/OdooXLDCE` PR 1 at `c1c01ffe775bc50061790a4e4e34ec953a6ee90f`. Actual scanners, original frozen standards/embeddings and real Groq requests. Final isolated result has 89 observations. |
| Durable recovery | PASS | One deliberate child-process exit after four complete agent checkpoints committed and before aggregation. Worker recovered all four outputs. Six Quality batch checkpoints preserved. Later corrections were revalidated/replayed without additional provider requests. |
| Scoped frontend checks on real files | PASS | Six actual JS/MJS, TS and TSX files parsed. Static test-reference analysis returned four frontend gaps; existing JSDoc consistency returned zero mismatches. A clearly labeled test-only frontend policy produced two source-verified length findings. The original Python-only policy remained frozen for the full review. |
| Persistence/report/API consistency | PASS | SQL, API, saved Markdown and analytics agree on 89 total and counts 47/14/11/17. Three verified Quality violations and eleven advisory suggestions. |
| Browser review/Fleet/analytics | PASS | Actual production build viewed with isolated fixture session. Review and Fleet show the same counts, exclusions and draft outcomes. Analytics shows one completed review, 89 observations, index 59 and incomplete coverage. |
| Final backend tests | PASS | 517 passed, four classified collection warnings; PostgreSQL/runtime opt-ins enabled against isolated schemas in the dedicated Docker DB. `scratch/backend-final-tests-20261106.log`. |
| Final frontend tests/build | PASS | 96 tests across 21 files; production build passed. Logs under `scratch/frontend-final-*20261106.log`. |
| GitHub publication | Intentionally disabled | Delivery boundary disabled and non-read GitHub requests blocked except installation-token acquisition. Isolated comment ID is null. Existing comment 6637466320 still matches the original body. |

The browser session is a fixture user in the isolated database. Repository identity and PR metadata are read from GitHub using the app. User OAuth sign-in and user-token authorization were outside this acceptance run. The fixture session route, delivery guard and planned fault are mounted test harness code under `scratch/acceptance`; they are excluded from the built production image.

## Correctness defects fixed during verification

- A frontend failure could be overwritten as a successful Quality outcome. Exclusion normalization now happens before frontend analysis, and actual frontend errors retain their failure reason.
- Completed/reused Quality batch counters were incremented twice. The duplicated observation blocks were removed and exact completed/reused counts are regression-tested.
- TypeScript test references used identifier spelling, allowing a locally shadowed import to hide a gap. References now resolve to their actual import binding through the TypeScript checker.
- False missing-future-import claims survived under alternate rule names. Aliases now resolve consistently and the pinned AST contradicts claims when the import exists.
- A purported unsorted local import group was already sorted. The observed named and generic local-group claims are checked conservatively against the source.
- Security file metadata excluded JSON/declaration artifacts even though Gitleaks scanned them. Source-language applicability and secret-scanner applicability are now recorded separately.
- Partial coverage with an `ok` execution could omit the report warning. It now remains visible, and the summary distinguishes four completed executions from complete file coverage.
- Optional drafting reported `completed` when some targets were skipped. Per-target completed/skipped/failed counts now preserve both successful drafts and budget/cap skips.

These are targeted changes to the existing implementation. Tests in `backend/tests/test_release_correctness.py` reproduce the observed defects before their fixes.

## Historical count reconciliation

| Dataset | Security | Quality | Test Gap | Documentation | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Earlier isolated run | 47 | 22 | 7 | 17 | 93 |
| Original GitHub review 88 | 47 | 21 | 7 | 17 | 92 |
| Earlier correction preview | 47 | 16 | 7 | 17 | 87 |
| Audited historical preview | 47 | 14 | 7 | 17 | 85 |
| New isolated acceptance result | 47 | 14 | 11 | 17 | 89 |

The 93 and 92 runs proposed different sets of model advisories; their difference is a net one, not proof that a single finding disappeared. The first correction removed two contradicted length claims and three canonical duplicates. Full source audit removed the false future-import and local-import-sorting advisories as well. The new acceptance result adds four frontend static-reference gaps from the expanded capability scope.

Pinned measurements are club_summary 39 and revenue_by_type 35 logic lines against limit 40. Valid retained length violations are membership_breakdown 42, event_attendance 49 and test_analytics_counts_correct 226. All 47 scanner signals, 17 documentation signals and seven original Python test-reference gaps were reproduced without a provider call. Ten retained Quality docstring advisories corroborate Documentation signals. One import-style interpretation remains explicitly advisory and informational. Totals count agent observations and include that corroboration; they are not a count of unique exploitable defects.

All original saved Quality citations were found in the original four-document `coding_standards` collection. It was exported with its embeddings and restored under the same version in the isolated Chroma volume.

## Final isolated result

| Agent | Execution | Observations | Analyzed/eligible | Excluded | Coverage | Optional drafts |
| --- | --- | ---: | --- | ---: | --- | --- |
| Security | Completed | 47 | 13/13 | 0 | Complete for configured scanners | Not requested |
| Quality | Completed | 14 | 5/5 | 8 | Partial | Not requested |
| Test Gap | Completed | 11 | 10/10 | 3 | Partial | 1 completed, 6 skipped, 0 failed |
| Documentation | Completed | 17 | 11/11 | 2 | Partial | 4 completed, 13 skipped, 0 failed |

Quality has three verified violations and eleven advisory suggestions. Its six batches are correctly reported as reused. There are ten checkpoint rows: six Quality batches plus four complete agent outputs. Five valid draft candidates remain approval-gated.

Quality exclusions comprise JSON and a declaration artifact plus six frontend source files for which the frozen Python standard supplies no applicable frontend rule. Documentation excludes JSON/declarations. Test Gap additionally treats the Python test file as reference input rather than a production target. Exact paths and reasons are in `scratch/acceptance-final-review.json`.

Frontend capability verification used actual `api-codegen.mjs`, `App.tsx`, `AdminAnalyticsPage.tsx`, `AdminHomePage.tsx`, `useBackendHealth.ts` and `nav.ts`. The separate 40-line frontend policy is an acceptance probe, not an invented team requirement or an addition to review 1. Its evidence is `scratch/acceptance-frontend-real-source.json`. No frontend test framework is declared in the pinned repository. Static references do not establish runtime test coverage. Namespace imports, path aliases, re-export graphs and dynamic test execution remain outside this scope.

## Performance measurements

The cold run reached its first recovered saved report in **622.449 seconds**, measured from queue creation to report persistence. This includes cold embedding-model download, the deliberate checkpoint crash, the worker's recovery delay and checkout. Subsequent compatibility corrections reused saved results. The final replay took about four seconds and issued zero provider requests.

| Agent | Provider requests | Reported tokens | Agent elapsed seconds | Token wait seconds |
| --- | ---: | ---: | ---: | ---: |
| Security | 6 | 7,611 | 188.055 | 172.478 |
| Quality | 6 | 20,594 | 488.653 | 427.970 |
| Test Gap | 1 | 1,153 | 549.192 | 52.541 |
| Documentation | 5 | 1,887 | 549.139 | 55.024 |
| Total | 18 | 31,245 | Concurrent durations | 708.013 summed agent waits |

Nineteen logical completion calls led to eighteen dispatched requests. Seventeen responses supplied usage. Known usage therefore excludes any unreported provider work on the request that did not return usage. Estimated reservations total 53,629 tokens. Gate wait totals 4.955 seconds; optional-agent priority waits total 974.987 seconds. Summed waits overlap across agents and must not be read as wall-clock latency. Metrics report zero retried dispatched requests.

No performance improvement is claimed. Platform, cold model initialization, validation scope and the deliberate recovery fault differ from previous runs. Exact metrics are in `scratch/acceptance-performance.json` and original worker logs.

## Recovery and verification harness disclosures

The planned fault occurred after real analysis completed and all four outputs committed, before report aggregation. Attempt 2 recovered those outputs normally. Attempt 3 verified the counter-only correction, and attempt 4 verified tightened validation and draft metadata. These later replays used the same isolated review row. They did not create additional reviews or repeat Groq analysis.

The counter-only replay proved exact source equivalence apart from removing duplicate observations. The later replay revalidated every saved Quality candidate against pinned source and original citations before assigning the new compatibility fingerprint. Draft counts were reconstructed from saved validated drafts and explicit budget exits. These are controlled test-operator corrections, not an automatic production migration of stale checkpoints. Normal checkpoint invalidation still rejects changed validation fingerprints.

An audit-writing harness error occurred after the isolated revalidation transaction committed. The state was inspected and resumed rather than resubmitting analysis. Final SQL/API/report checks pass and preserved source evidence remains available. An initial full-suite launcher resolved a global Python child and failed collection; it was replaced with the explicit venv interpreter. Final passing test results come from that corrected launcher.

## Four pytest warnings

Two warnings in `test_agents/test_supervisor.py` concern imported dataclasses `TestGap` and `TestGapAgentResult`. Two in `test_agents/test_test_gap_agent.py` concern imported `TestGapAgent` and `TestGapAgentResult`. Pytest considers their names as possible test classes, then rejects their constructors. They are application helpers rather than test cases. These are benign collection warnings, not skipped test methods or runtime failures. They remain visible and were not suppressed.

## Deployment procedure after explicit approval

1. Review the uncommitted patch and required new migration/parser/scanner files. Commit/push only after authorization. Retain the tested image identity and evidence bundle.
2. Identify the intended normal database and persistent Chroma volume. Back up that database and preserve the existing token-encryption key, session configuration and GitHub App credentials. The acceptance `.env`, fixture database and harness must not be used as deployment configuration.
3. Stop the intended API/worker during migration. With the approved normal `DATABASE_URL` configured, activate `backend/venv`, verify `(Get-Command python).Source`, then run `python -m alembic upgrade b94e6d27a041`. This command has not been run on the normal database here.
4. Build with `docker build -t codeguardian:<approved-release> -f backend/Dockerfile .`. Run the API and separate worker from that image with the approved Docker-reachable database URL, stable Chroma volume and read-only App-key mount. The entry points are `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000` and `python -m backend.worker`, with the image venv active.
5. For the repository's local Compose topology, `docker compose --env-file .env build backend` and `docker compose --env-file .env up -d postgres migrate backend worker` are the existing deployment commands. Confirm its database/volumes and host-port mapping are the intended target first: the supplied Compose file points to its own PostgreSQL service and publishes 5432. A normal database currently hosted natively requires a reviewed override; starting a new empty Compose volume is not a data migration.
6. Build the frontend with the intended `VITE_API_BASE_URL` and `npm run build`. Serve the resulting static build with SPA fallback. This verification used `npm run preview -- --host 127.0.0.1 --port 15173` for local acceptance.
7. Require `/health/live` and `/health/ready` success, expected migration head, recent worker heartbeat, user authorization and matching report/Fleet/analytics counts before enabling normal review traffic. Approve any real GitHub-publishing smoke test separately.
8. Apply the historical comment correction only through the reviewed procedure in `docs/REVIEW88_COMMENT_CORRECTION_PLAN.md`.

Source readiness is scoped to the tested capabilities and isolated workflow. Human advisory review, user OAuth in the deployment environment, runtime execution of drafted tests and real comment publication were outside this run.
