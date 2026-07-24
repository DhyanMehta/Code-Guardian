# CodeGuardian AI — Project Context

## Purpose
CodeGuardian AI is an autonomous multi-agent code review and DevSecOps platform.
It reviews GitHub pull requests automatically and posts a single, severity-ranked
report as a PR comment. It can optionally open an auto-fix commit on a separate
branch, which always requires explicit human approval before merge.

## Architecture
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
- **Backend**: FastAPI, LangGraph, Groq (Llama 3.1 / Mistral), ChromaDB, PyGithub,
  Semgrep, Bandit, Gitleaks (binary), Docker, PostgreSQL.
- **Frontend**: React + Tailwind (minimal, professional; no gradients, no emojis,
  sharp typography).

## Current Build Phase
**Session 1 — scaffold + venv + Docker + env + FastAPI skeleton + GitHub webhook receiver.**
(Update this section at the start of each session.)

### Session roadmap
1. Scaffold + webhook skeleton *(current)*
2. Security tools integration + Security Agent
3. ChromaDB RAG ingestion + Quality Agent
4. Test-Gap Agent + Documentation Agent
5. Supervisor Agent (LangGraph) + aggregation + persistence + auto-fix gate
6. React + Tailwind dashboard
7. End-to-end testing on real repos + polish + demo

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
