# Deferred frontend flow plan

Checkpoint: 2026-10-08. Resumed by the user on 2026-10-09; superseded by [FRONTEND_FINAL_PLAN.md](FRONTEND_FINAL_PLAN.md). Retained as historical context.

1. Align backend contracts and status meanings before changing presentation. Persist genuine pipeline stages/agent progress; do not invent progress from elapsed time.
2. Preserve installation and review identity throughout login, navigation, polling, and mutations.
3. Public landing page and GitHub sign-in; first-time users complete GitHub App repository selection before seeing connected repositories. Returning users retain access to existing installations.
4. Profile-level Auto/Manual control covering **all installations the user administers**. This is shared installation policy, not a conflicting per-user preference. Members cannot change it. Auto processes eligible PR webhooks; manual exposes a review action.
5. Review loading/progress screen with animation and actual persisted agent stages; distinguish queued, running, retrying, failed, completed, and delivery state. Pause polling when hidden and resume when visible.
6. Clear findings/evidence and review-level Create fix branch action. No per-finding autofix endpoint exists. Keep human approval and no automatic merge.
7. Agent Fleet graphs and analytics based on recorded outcomes, with explicit incomplete/degraded coverage.
8. Groq optimization remains a separate proposed phase: measure token/request usage; bound context/output, deduplicate/cache safe repeat work, enforce shared concurrency/rate budgets, honor Retry-After with bounded backoff, and evaluate model routing/fallback with quality checks. No provider/model change is authorized by this checkpoint.
9. Verify complete onboarding, review, failure/recovery, policy and autofix flows before release.

Confirmed incident: review #80 for DhyanMehta/flask-task-api PR #2 was pending with attempt=0 and no start time; the worker heartbeat predated the request. Starting the API/frontend alone does not execute reviews. Worker startup and honest queue feedback are part of the current repair, not the deferred redesign.
