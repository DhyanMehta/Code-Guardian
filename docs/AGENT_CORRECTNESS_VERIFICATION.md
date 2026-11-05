# Agent correctness implementation and verification

Follow-up verification and corrections from November 6 are recorded in [RELEASE_VERIFICATION_2026-11-06.md](RELEASE_VERIFICATION_2026-11-06.md). That report supersedes readiness and historical-preview counts below while preserving this earlier implementation record.

At the time of this earlier record, work remained uncommitted on `codex/durable-review-pipeline`. Existing frontend and durable-pipeline edits were preserved. This work had not published a correction or created another application review. The subsequent release candidate is described in [CONTROLLED_RELEASE.md](CONTROLLED_RELEASE.md).

## Baseline and historical correction

Review 88 analyzed OdooXLDCE PR 1 at `c1c01ffe775bc50061790a4e4e34ec953a6ee90f`. Its saved report matched GitHub comment `6637466320`. Four agent rows contain Security 47, Quality 21, Test Gap 7 and Documentation 17 findings. Quality completed six provider calls and six saved batches. Its legacy degraded label came from excluded frontend files. The report incorrectly translated that label into “could not run” and hid its count.

The earlier isolated run had 22 Quality findings and 93 total. Comparison of saved rows shows several different model suggestions and rule names across the runs. The difference is a net count of one across differing proposal sets. It cannot be explained solely by a single dropped claim. Both runs produced advisory suggestions whose membership can vary between model calls.

Local evidence and preview artifacts are `scratch/review88-baseline.json`, `scratch/review88-corrected-preview.md`, `scratch/review88-correction-audit.json`, and `scratch/review88-pinned-source/`. The existing comment is https://github.com/DhyanMehta/OdooXLDCE/pull/1#issuecomment-6637466320 .

The preview retains 87 of the original 92 entries. It preserves 84 original entries, recomputes three verified length violations, and rejects five entries. Two claims fail the cited limit: club_summary has 39 logic lines and revenue_by_type has 35. Three entries duplicate already retained canonical length violations. Verified measurements are membership_breakdown 42, event_attendance 49 and test_analytics_counts_correct 226, against a limit of 40. Python logic lines exclude the signature, decorators, blank lines, comment-only lines and the docstring. These are static measurements of the pinned source. Other retained advisory suggestions retain their original informational status and have not become independently verified violations.

## Execution and coverage

Existing agent outcome values remain compatible. A new nullable structured coverage record separates execution, file coverage and optional enrichment. It records eligible/analyzed/excluded files, exclusion reasons, completed/failed/reused batches, findings and scanner applicability. Legacy rows retain null coverage. They display “Coverage not recorded.” Failure and partial coverage retain saved finding counts.

Report summaries with new metadata distinguish completed executions from complete coverage. Dashboard cards display the same metadata, Agent Fleet flags partial coverage, and analytics requires actual coverage metadata before treating a historical point as complete. Existing progress events remain compatible.

## Explicit language scope

| Agent | Supported frontend checks |
| --- | --- |
| Security | Deterministic Semgrep eval/document.write rules for JavaScript/TypeScript, plus Gitleaks. Bandit remains Python-only. Scanner records disclose applicable files and scanner completion. |
| Quality | Parsed exported function declarations and exported const arrow/function expressions. Function-length violations require an explicitly applicable retrieved standard. Python-only standards do not establish frontend requirements. |
| Test Gap | Static named/default relative-import references in .test/.spec JS/TS/TSX files. These are static references, with no claim of runtime execution coverage. |
| Documentation | Existing exported-function JSDoc parameter names checked against actual parameters. Missing frontend JSDoc is not invented as a requirement. |

JS, JSX, MJS, CJS, TS and TSX source extensions are recognized. Generated/vendor directories and declaration files have explicit exclusions. JSON is outside these source-language checks. Namespace imports, path aliases, re-export graphs, dynamic imports and runtime coverage are outside this static test-reference implementation. Unexported functions and classes are outside the frontend symbol checks. These capability limits are disclosed in agent notes. OdooXLDCE's pinned package.json declares no frontend test framework.

The parser uses trusted TypeScript 5.7.3 installed under `backend/tools/parser/`. It parses source data without executing repository code or loading repository configuration. A backend Docker stage supplies Node and the pinned parser. The Docker image has not been built in this session. Local setup requires `npm ci --ignore-scripts` in that parser directory.

## Durable recovery

Checkpoint identity includes source revision, diff, standards version, provider settings and a digest of validation code, frontend parser/lockfile and scanner rules. Compatible completed agent results and Quality batches remain reusable. Whole-agent reuse records reused batch counts. The existing PostgreSQL conflict handling and worker advisory lock are preserved.

## Database and verification

Migration `b94e6d27a041` adds nullable `review_agent_runs.coverage`, following `a84c2e13d930`. It does not fabricate historical metadata. Migration upgrade/downgrade was tested in disposable PostgreSQL schemas. The regular application database has not received this migration. Apply it before restarting the API/worker with this code.

Final backend verification passed 508 tests with PostgreSQL and runtime opt-ins enabled. Four existing collection warnings remain. Tests include the actual pinned analytics function bodies, canonical aliases, duplicate rules, partial and failed counts, parser/JSDoc/static references, checkpoint identity changes, worker recovery, migration roundtrips and delivery behavior. A real Semgrep scan found the new frontend-dangerous-eval rule in a temporary TypeScript fixture.

One intermediate full run exposed an integration fixture that relied on shared session standards. The integration now ingests its own relevant fixture standards into a separate Chroma directory and still uses real embeddings/retrieval. LLM output and GitHub posting remain explicitly mocked in that automated integration. The final full run passed.

Frontend verification passed 96 Vitest tests across 21 files and the production build. The new regression exercises structured partial coverage and count 21 through contract parsing and rendering. Browser-based live dashboard acceptance remains a separate step.

## Files changed in this implementation

- Coverage and persistence: `backend/services/agent_coverage.py`, `backend/agents/state.py`, `backend/agents/supervisor.py`, `backend/db/models.py`, `backend/db/migrations/versions/b94e6d27a041_agent_coverage.py`, `backend/services/review_service.py`, `backend/services/metrics_service.py`, `backend/api/reviews.py`.
- Validation and languages: `backend/agents/quality_agent.py`, `backend/agents/test_gap_agent.py`, `backend/agents/documentation_agent.py`, `backend/agents/frontend_analysis.py`, `backend/tools/frontend_ast.cjs`, `backend/tools/parser/package.json`, its lockfile, `backend/tools/semgrep_rules/frontend_security.yml`, `backend/Dockerfile`, `backend/services/agent_checkpoints.py`.
- Reporting and dashboard: `backend/services/report_builder.py`, `frontend/src/api/contracts.ts`, `frontend/src/components/reviews/ReviewPresentation.tsx`, `frontend/src/components/dashboard/AgentOutcomeChart.tsx`, `frontend/src/components/dashboard/AgentsTab.tsx`.
- Regressions: `backend/tests/test_agent_correctness.py`, `backend/tests/fixtures/odooxldce_quality.json`, `backend/tests/test_api/test_metrics.py`, `backend/tests/test_api/test_reviews.py`, `backend/tests/test_services/test_report_builder.py`, `backend/tests/test_agents/test_quality_agent.py`, `backend/tests/test_postgres_pipeline.py`, `frontend/src/test/readFlows.test.tsx`.
- Historical preview: `scratch/preview_review88_correction.py` and the local evidence artifacts listed above.

## Controlled live acceptance after approval

1. Review the corrected preview and per-finding audit. Confirm approval to edit the existing comment, separately from authorizing a fresh regular review.
2. Approve and apply the coverage migration, install the parser dependency, then restart API and worker. Verify database revision and readiness. Confirm the queue has no unrelated work.
3. Confirm PR head still matches the pinned SHA. Inspect applicable frontend standards and exclusions before authorizing any provider work.
4. Use the normal authenticated manual trigger for one approved review. Observe all four agent executions, coverage records, Quality batch persistence and final report. Any mocked automated-test components must be replaced by genuine services for this acceptance.
5. Compare database findings, report snapshot and dashboard counts. Verify the actual GitHub comment URL, full body, commit SHA and duplicate prevention. A normal GitHub webhook delivery requires a separately observable real GitHub event if that inbound path is included in acceptance.
6. For the historical correction, edit comment 6637466320 only after explicit approval. Preserve its original snapshot and the correction audit. Preview count 87 is a revalidated historical result and is not the expected count for a fresh expanded-language analysis.
