# CodeGuardian AI — Project Context

## Purpose
CodeGuardian AI is an autonomous multi-agent code review and DevSecOps platform.
It reviews GitHub pull requests automatically and posts a single, severity-ranked
report as a PR comment. It can optionally open an auto-fix commit on a separate
branch, which always requires explicit human approval before merge.

## Architecture
The current backend reliability contract is described in
[docs/BACKEND_RELIABILITY.md](docs/BACKEND_RELIABILITY.md). Reviews now run in a
separate durable worker; OAuth credentials are encrypted and authorize user actions;
standards versions and report snapshots are retained for each review. Historical
session notes below describe earlier iterations where these differed.

- A FastAPI backend receives GitHub webhook events (PR opened / synchronize).
- A Supervisor Agent (LangGraph) fans out to four specialist agents in parallel,
  then aggregates their outputs into one deduplicated, severity-ranked report.
- Deterministic scanners produce the raw findings; the LLM (Groq) only triages,
  explains, and prioritizes — it never originates a finding.
- Results are persisted to PostgreSQL and surfaced in a React + Tailwind dashboard.

```
GitHub PR event
      │
      ▼
FastAPI webhook receiver  ──►  Review service  ──►  Supervisor Agent (LangGraph)
                                                        │  fan-out (parallel)
                        ┌───────────────┬───────────────┼───────────────┐
                        ▼               ▼               ▼               ▼
                  Security Agent   Quality Agent   Test-Gap Agent   Documentation Agent
                        └───────────────┴───────────────┴───────────────┘
                                        │  aggregate + severity-rank
                                        ▼
                        Report builder ──► PR comment  (+ optional auto-fix branch)
                                        ▼
                              PostgreSQL  ──►  React + Tailwind dashboard
```

## Agents
- **Security Agent**: runs Semgrep, Bandit, and Gitleaks. The LLM is used only to
  triage / explain / prioritize the raw scanner output. It must never invent a finding.
- **Quality Agent**: checks style / complexity / naming, grounded via RAG (ChromaDB)
  over the team's own coding-standards document.
- **Test-Gap Agent**: identifies untested functions / branches and drafts starter unit tests.
- **Documentation Agent**: flags missing / outdated docstrings and drafts replacements.
- **Supervisor Agent**: coordinates the four specialists, deduplicates and aggregates
  their findings, severity-ranks them, builds the PR comment, and gates the optional
  auto-fix branch behind explicit human approval.

## Tech Stack
- **Backend**: FastAPI, LangGraph, Groq (openai/gpt-oss-20b), ChromaDB, PyGithub,
  Semgrep, Bandit, Gitleaks (binary), Docker, PostgreSQL.
- **Frontend**: React + Tailwind (minimal, professional; no gradients, no emojis,
  sharp typography).

## Current Build Phase
**Session 8 — GitHub App Authentication Migration (JWT + per-installation access tokens + OAuth login + multi-tenant DB).**
Complete end-to-end migration from single shared PAT to GitHub App:
- App-level authentication (`backend/tools/github_app.py`) using `Auth.AppAuth` and `GithubIntegration`.
- Dynamic per-installation token generation and caching with automatic refresh for git clone URLs and PyGithub client operations.
- Multi-tenant DB schema: `installations`, `users` (without token storage), `user_installations`, and nullable `reviews.installation_id` foreign key via Alembic migration `d4e5f6a7b8c9`.
- Webhook receiver (`backend/api/webhooks.py`) handles `installation` (created/deleted/suspend/unsuspend) and resolves `installation_id` on reviewable `pull_request` events with auto-creation fallback.
- OAuth user authentication endpoints (`backend/api/auth.py`): `/auth/github/login`, `/auth/github/callback`, `/auth/me`, `/auth/logout` using HS256 session JWTs (PyJWT 2.14.0).
- Installation and repo discovery API (`backend/api/installations.py`): `/installations`, `/installations/{id}/repos` (live query), `/installations/{id}/repos/{owner}/{repo}/pulls`.
- Real end-to-end verification completed on `DhyanMehta/httpx` PR #1: review executed with installation token, comment #5743024834 posted by `codeguardian-ai-devsecops-platform[bot]` (not old PAT user), and auto-fix branch created and pushed with installation token.

### Previous phases
**Session 7 — End-to-end testing on real repos + polish + demo.**
**Session 6 — React + Tailwind dashboard (review history, review detail, code-health trends).**
**Session 5 — Supervisor Agent (LangGraph) + Aggregation + Persistence + Auto-Fix Gate.**
Sessions 1 (scaffold + webhook), 2 (security tools + Security Agent), 3 (RAG +
Quality Agent), and 4 (Test-Gap + Documentation Agents) are complete.

### Session roadmap
1. Scaffold + webhook skeleton *(complete)*
2. Security tools integration + Security Agent *(complete)*
3. ChromaDB RAG ingestion + Quality Agent *(complete)*
4. Test-Gap Agent + Documentation Agent *(complete)*
5. Supervisor Agent (LangGraph) + aggregation + persistence + auto-fix gate *(complete)*
6. React + Tailwind dashboard *(complete)*
7. End-to-end testing on real repos + polish + demo *(complete)*
8. GitHub App authentication migration *(complete)*

## In Scope (5-day build)
 - Webhook-triggered PR review with the four specialist agents + supervisor.
- Single severity-ranked PR comment per review.
- Auto-fix branch behind explicit human approval.
- RAG over one coding-standards document.
- Dashboard: review history + code-health trends.
- Local dev via docker-compose; single-repo / small-repo focus.

## Out of Scope (5-day build)
- Multi-tenant auth / organization management.
- Non-GitHub providers (GitLab, Bitbucket).
- Auto-merge without human approval.
- Model fine-tuning; production-grade scaling / HA.
- Languages beyond the primary target set for the scanners (Python-first to start).




## Known Limitations (deliberate scope boundaries)

These are conscious design decisions, not oversights or unfinished work. They should
be stated as such in the final project report.

### Quality Agent verifies anchors and counts, not free-form reasoning
Unlike the Security Agent — where every finding is anchored to a deterministic
scanner fingerprint and the LLM only triages — the Quality Agent's findings
*originate* with the LLM, because the rules live in a prose standards document
rather than in a tool. Three checks constrain that, and each was added in response
to an observed real failure:

1. **Rule anchoring** — the finding must cite a standards passage that was actually
   retrieved. Prevents invented rules.
2. **Symbol existence** — the finding must name a function, class, method, or
   module-level symbol that genuinely exists in the changed file's AST, and its
   reported line number is taken from the AST rather than from the model. Prevents
   findings about code that does not exist. A finding claiming file scope
   (`<module>`) whose own explanation names a real definition is re-anchored to that
   definition, so file scope cannot be used to sidestep this check.
3. **Countable claims** — parameter counts and definition lengths asserted by a
   finding are recomputed from the AST, and the finding is dropped when the real
   value clearly contradicts the claim.

**What is not verified:** the truth of any other assertion the model makes. Claims
such as "this does not read as a question", "the cyclomatic complexity is high", or
a naming judgement that misreads the identifier are grounded in a real rule and
attached to real code, but their reasoning is the model's and is not independently
checked. A real run, for example, correctly flagged `get_user_from_db` under the
naming rule while explaining it as "PascalCase", which it is not.

Closing that gap would mean reimplementing each standards rule as deterministic
analysis and demoting the LLM to explaining precomputed results — the Security
Agent's architecture. That is a redesign of the agent, not a guard on it, and it is
deliberately out of scope for this build. Quality findings should therefore be read
as *advisory and human-reviewed*, whereas Security findings are tool-verified.

Rejections in all three categories are counted, logged at WARNING with the offending
symbol, and summarized in the review's notes, so a misbehaving model stays visible
rather than silently degrading the review (`RULES.md` #9).

### Untriaged security findings are withheld, not downgraded (follow-up, not implemented)
When the Security Agent's LLM triage fails — most realistically a Groq free-tier
rate-limit exhaustion, which was observed for real during Session 6 — the raw scanner
findings still exist and are retained in the agent's result as context, but they are
**not reported as findings**. They never went through triage, so they have no reviewed
severity and no explanation, and promoting them would mean the report mixes triaged
and untriaged items under the same visual language.

What the system does instead is refuse to call that a clean run: the agent's outcome
is `DEGRADED`, the review renders "Security — could not run", the finding count shows
as an em dash rather than `0`, and a note records how many raw findings from which
scanners were left untriaged. The failure is visible; the coverage gap is stated.

The deferred alternative (considered and explicitly not built in Session 6) is to
surface those raw findings with their original scanner severity, clearly marked as
untriaged and unexplained. That is a change to what a security finding *is* — it
alters the Session 2 contract that the LLM triages every reported scanner finding —
so it belongs in its own scoped change with its own report-rendering decisions, not
bolted onto a dashboard session.

### LLM calls are throttled process-wide
The supervisor fans out to four agents in parallel and each may call Groq. On the free
tier (8,000 tokens/minute for openai/gpt-oss-20b) four simultaneous calls reliably trip a 429; in a real run
this cost the Security Agent its entire triage. LLM calls are therefore gated by a
process-wide semaphore (`LLM_MAX_CONCURRENT_CALLS`, default 1) with a minimum spacing
between call starts (`LLM_MIN_CALL_INTERVAL_SECONDS`, default 1.5s). This throttles
the *calls only* — the graph still schedules and runs the four agents in parallel, so
scanners, AST analysis, and retrieval continue to overlap. Reviews take somewhat
longer in exchange for not silently losing an agent's output. The interval is set to 0
in the test suite, where there is no real provider to protect.

### Reviews are serialized globally
To fully eliminate AI token quota exhaustion when handling concurrent webhooks (e.g. two separate repositories receiving PRs simultaneously), CodeGuardian AI uses a global lock (`_review_run_lock`) around the review execution logic. This means that reviews across the entire system (all installations) now run strictly one at a time, queuing sequentially rather than running in parallel. This is an intentional tradeoff prioritizing correctness and stability over throughput, given the strict rate limit constraints of the shared LLM provider budget (Gemini/Groq). This is a deliberate design choice to guarantee that 100% of the token quota is dedicated to one review at a time.

### Daily review volume is constrained

> [!WARNING]
> **TEMPORARY MEASURE**: The LLM provider is currently set to Groq (`openai/gpt-oss-20b`) pending an OpenAI API key purchase.
> Groq's free tier imposes a hard limit of 200,000 tokens per day (TPD) and 1,000 requests per day (RPD). Given that a single comprehensive PR review fans out across multiple agents, generates ~10-15+ LLM calls, and was measured to consume ~16,000 tokens in a real end-to-end run, CodeGuardian AI is effectively capped by the TPD limit at approximately **12 full reviews per day**. 
> 
> **Do not exceed this hard ceiling.** Triggering more than ~12 reviews across a single day, including any testing right before a demo, risks the exact same degraded-agent problem returning.
