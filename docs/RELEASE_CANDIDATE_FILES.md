# Release candidate file inventory

Branch: `codex/durable-review-pipeline`. The documentation commit also adds this inventory. Its final SHA is recorded in the release handoff.

## Pinned parser, frontend scanner rules and Docker tooling

Commit: `faa1d61def85b05d58c7cb5b42894fb9ea874c2e`

- `.dockerignore`
- `backend/Dockerfile`
- `backend/tools/frontend_ast.cjs`
- `backend/tools/parser/package-lock.json`
- `backend/tools/parser/package.json`
- `backend/tools/semgrep_rules/frontend_security.yml`

## Durable analysis, coverage, delivery migrations and backend regressions

Commit: `8d0459c88441dc2ab6577c78beee90245020cc77`

- `backend/agents/documentation_agent.py`
- `backend/agents/frontend_analysis.py`
- `backend/agents/quality_agent.py`
- `backend/agents/state.py`
- `backend/agents/supervisor.py`
- `backend/agents/test_gap_agent.py`
- `backend/api/reviews.py`
- `backend/db/migrations/versions/a84c2e13d930_delivery_retry.py`
- `backend/db/migrations/versions/b94e6d27a041_agent_coverage.py`
- `backend/db/models.py`
- `backend/services/agent_checkpoints.py`
- `backend/services/agent_coverage.py`
- `backend/services/metrics_service.py`
- `backend/services/report_builder.py`
- `backend/services/review_service.py`
- `backend/tests/fixtures/odooxldce_quality.json`
- `backend/tests/test_agent_correctness.py`
- `backend/tests/test_agents/test_quality_agent.py`
- `backend/tests/test_api/test_metrics.py`
- `backend/tests/test_api/test_reviews.py`
- `backend/tests/test_pipeline_recovery.py`
- `backend/tests/test_postgres_pipeline.py`
- `backend/tests/test_release_correctness.py`
- `backend/tests/test_services/test_report_builder.py`
- `backend/tests/test_services/test_review_service.py`
- `backend/tests/test_tools/test_llm_client.py`
- `backend/tools/llm_client.py`
- `backend/tools/llm_metrics.py`
- `backend/tools/review_budget.py`
- `backend/worker.py`

## Preserved frontend presentation, coverage/progress contracts and regressions

Commit: `da978c091ad40b38130046c23635eb78ab0d2305`

- `frontend/src/api/contracts.ts`
- `frontend/src/components/common/Button.tsx`
- `frontend/src/components/common/IconButton.tsx`
- `frontend/src/components/common/InstallationPicker.tsx`
- `frontend/src/components/common/SearchInput.tsx`
- `frontend/src/components/common/StatCard.tsx`
- `frontend/src/components/common/Tabs.tsx`
- `frontend/src/components/dashboard/AgentOutcomeChart.tsx`
- `frontend/src/components/dashboard/AgentsTab.tsx`
- `frontend/src/components/dashboard/AnalyticsTab.tsx`
- `frontend/src/components/dashboard/PullsTab.tsx`
- `frontend/src/components/dashboard/SettingsTab.tsx`
- `frontend/src/components/layout/AppLayout.tsx`
- `frontend/src/components/layout/ContextBar.tsx`
- `frontend/src/components/layout/Navbar.tsx`
- `frontend/src/components/reviews/AgentTimeline.tsx`
- `frontend/src/components/reviews/AutofixActions.tsx`
- `frontend/src/components/reviews/FindingsList.tsx`
- `frontend/src/components/reviews/ReviewPresentation.tsx`
- `frontend/src/components/reviews/ReviewProgress.tsx`
- `frontend/src/index.css`
- `frontend/src/pages/HomePage.tsx`
- `frontend/src/pages/ProfilePage.tsx`
- `frontend/src/pages/RepoDashboardPage.tsx`
- `frontend/src/pages/RepoListPage.tsx`
- `frontend/src/pages/ReviewDetailPage.tsx`
- `frontend/src/test/readFlows.test.tsx`
- `frontend/src/test/reviewProgress.test.tsx`

## Release documentation and local-artifact exclusions

- `.gitignore`
- `docs/AGENT_CORRECTNESS_VERIFICATION.md`
- `docs/CONTROLLED_RELEASE.md`
- `docs/RELEASE_CANDIDATE_FILES.md`
- `docs/RELEASE_VERIFICATION_2026-11-06.md`
- `docs/releases/review88/corrected-comment-preview.md`
- `docs/releases/review88/correction-audit.json`
- `docs/releases/review88/correction-manifest.json`
- `docs/releases/review88/original-comment-snapshot.md`
- `docs/releases/review88/source-audit.json`
- `docs/releases/review88/verification-summary.json`
- `docs/REVIEW88_COMMENT_CORRECTION_PLAN.md`

Preserved outside the candidate: UI_IMPLEMENTATION_ROADMAP.md, UI_REGRESSION_CHECKLIST.md, backend/backend-prd.md. Local acceptance harnesses and raw logs remain ignored. No production database, GitHub comment, auto-fix, merge or new live review is part of these commits.
