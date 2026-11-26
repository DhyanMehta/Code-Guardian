# CodeGuardian AI — Agent Setup & Operations Guide

> **Primary reference for every AI coding agent working in this repository.**
> Read this file first, then read [`RULES.md`](RULES.md). Both are binding.

---

## A. Project Overview

CodeGuardian AI is an autonomous multi-agent code review and DevSecOps platform.
It reviews GitHub pull requests using four specialist agents coordinated by a
Supervisor Agent, then posts a single severity-ranked PR comment and can open an
auto-fix branch that always requires explicit human approval before merging.

### Technology Stack

| Layer | Technologies |
|---|---|
| **Backend API** | FastAPI `0.139.2`, Uvicorn `0.51.0`, Python `3.11+` (`>=3.10` in `pyproject.toml`) |
| **Agent orchestration** | LangGraph `1.2.9` (`StateGraph`, conditional parallel fan-out via `Send` API) |
| **LLM provider** | Groq `1.5.0` (default model: `openai/gpt-oss-20b`); Gemini supported via `openai` `3.16.2` client (`gemini-3.5-flash-lite`) |
| **RAG vector store** | ChromaDB `1.5.9` (embedded `PersistentClient`, local disk — no separate server) |
| **Database** | PostgreSQL `16+` (SQLAlchemy `2.0.51`, Alembic `1.18.5`, `psycopg2-binary` `2.9.12`) |
| **Security scanners** | Semgrep `1.171.0`, Bandit `1.8.2`, Gitleaks `8.18.4+` (native binary; Docker fallbacks supported) |
| **JS/TS static parser** | Node.js `18+` + TypeScript `5.7.3` (`backend/tools/frontend_ast.cjs` & `backend/tools/parser/`) |
| **Frontend** | React `19.1`, Vite `6.2`, Tailwind CSS `4.1`, TypeScript `~5.7.3`, React Router `7.3`, Vitest `3.x` |
| **GitHub integration** | GitHub App (OAuth, installation access tokens, webhooks) via PyGithub `2.9.1` & `httpx` `0.28.1` |
| **Auth & crypto** | HS256 session JWTs (`PyJWT` `2.13.0`), Fernet-encrypted user OAuth credentials (`cryptography` `49.0.0`) |
| **Containerization** | Docker + Docker Compose (`docker-compose.yml`, optional local stack) |

### Architecture

```
GitHub PR event (webhook) OR Dashboard manual trigger
      │
      ▼
FastAPI receiver/API ──► PostgreSQL queue (`reviews` table)
      │                               │
      │ (returns 202)                 ▼
      │                        Durable Worker (`backend/worker.py`, advisory lock)
      │                               │
      │                               ▼
      │                        Checkout PR head & merge-base diff (`workspace.py`)
      │                               │
      │                               ▼
      │                        Supervisor (`LangGraph StateGraph`)
      │                          │ parallel Send fan-out
      │        ┌─────────────────┼─────────────────┬─────────────────┐
      │        ▼                 ▼                 ▼                 ▼
      │  Security Agent    Quality Agent    Test-Gap Agent    Documentation Agent
      │  (Semgrep,         (ChromaDB RAG    (Python AST +     (Python AST +
      │   Bandit,           + AST gates +    TS AST refs +     TS JSDoc check +
      │   Gitleaks +        supported rules  LLM starter       LLM docstring
      │   LLM triage)       + LLM enrichment) test drafts)     drafts)
      │        └─────────────────┴─────────────────┴─────────────────┘
      │                               │ fan-in `_aggregate` + report builder
      │                               ▼
      │                        PostgreSQL persistence
      │                        (`findings`, `review_agent_runs`, `review_progress`,
      │                         `review_agent_checkpoints`, saved `report_markdown`)
      │                               │
      │                               ├──► Separate GitHub delivery queue (bot PR comment)
      │                               └──► Optional auto-fix branch (human approval mandatory)
      │
      ▼
React + Vite + Tailwind Dashboard (`frontend/`) ◄── HTTP + cookies (`credentials: "include"`)
```

### Deterministic vs. LLM-Driven Processing

CodeGuardian AI strictly separates deterministic evidence from LLM-generated output (`RULES.md` #5):

- **Deterministic orchestration:** `build_supervisor_graph()` in `backend/agents/supervisor.py` compiles a fixed LangGraph `StateGraph` (`START` → parallel `Send` to four agents → `_aggregate` → `END`). There is no LLM-driven routing or agentic planning loop.
- **Deterministic analysis:**
  - **Security Agent:** Semgrep, Bandit, and Gitleaks produce raw findings scoped to PR diff hunks.
  - **Quality Agent:** Supported Python rules (`maximum_function_length`, `maximum_positional_parameters`, `future_annotations_import`) and supported frontend function-length rules are evaluated deterministically via AST/tokenizer (`backend/agents/quality_rules.py`, `backend/agents/frontend_analysis.py`), and LLM proposals are constrained by rule-passage anchoring, AST symbol existence, and countable-claim verification.
  - **Test-Gap Agent:** Untested modified functions/methods are detected deterministically from Python AST + test file discovery (and TS/JS static relative import references via `frontend_ast.cjs`).
  - **Documentation Agent:** Missing/outdated docstrings are detected deterministically by AST signature/docstring comparison (and JSDoc parameter mismatch for exported TS/JS functions).
- **LLM-driven processing:**
  - **Security:** Triages, explains, and severity-ranks existing raw findings (unmatched fingerprints are dropped; untriaged findings are never surfaced as triaged findings).
  - **Quality:** Enriches supported findings and produces advisory style findings grounded in retrieved ChromaDB passages.
  - **Test-Gap & Documentation:** Draft optional starter pytest unit tests and Google-style docstrings, subject to AST import/call/parameter validation and remaining review budget (`optional_draft_budget`).

### Backend & Frontend Responsibilities

| Component | Role |
|---|---|
| **FastAPI API** (`backend/main.py`) | HTTP endpoints (`/auth`, `/installations`, `/reviews`, `/metrics`, `/profile`, `/health`, `/webhooks`), CORS & origin checks |
| **Durable Worker** (`backend/worker.py`) | Polls PostgreSQL queue, acquires advisory lock `73194201`, runs each attempt in a bounded child process, retries GitHub comment delivery |
| **Review Service** (`backend/services/review_service.py`) | Serializes execution (`_review_run_lock`), manages git checkouts, compiles/runs supervisor graph, persists findings/outcomes/reports, delivers PR comments |
| **PostgreSQL** | Persistent store for installations, encrypted user tokens, review queue, findings, agent runs, progress events, checkpoints, and worker heartbeat |
| **ChromaDB** | Embedded vector store (`PersistentClient`) indexing coding standards for the Quality Agent |
| **React Frontend** (`frontend/src/`) | Cookie-authenticated SPA (`AuthContext`, `InstallationContext`), scoped resource cache & polling (`api/resources.ts`, `polling.ts`), guarded write operations (`api/writes.ts`), and dashboard pages (`/`, `/repos`, `/repos/:owner/:repo`, `/reviews/:reviewId`, `/settings/installation`, `/profile`) |

---

## B. AI Coding Agent Instructions

Every AI coding agent (Codex, Antigravity, Claude Code, etc.) **MUST**:

1. **Read `AGENTS.md` first**, then read and follow [`RULES.md`](RULES.md).
2. **Inspect the Git working tree** (`git status`, `git diff`, `git log --oneline -10`) before making any changes.
3. **Preserve existing implementation** — do not rewrite working code, tests, or API contracts without explicit authorization.
4. **Use the correct virtual environment** (`backend/venv`) for all Python work and confirm the interpreter path before executing Python commands (`RULES.md` #1–3).
5. **Never expose secrets** — no API keys, database passwords, private keys, session secrets, cookies, or OAuth tokens in code, commits, logs, or responses.
6. **Never modify live data unnecessarily** — do not alter the regular PostgreSQL database, ChromaDB collections, or live GitHub repositories/installations without explicit authorization.
7. **Never trigger paid AI requests** (Groq, Gemini, OpenAI) without an appropriate task and explicit authorization. Groq's free tier supports roughly **~12 full reviews per day** (`CONTEXT.md`).
8. **Never start duplicate worker processes** — `backend/worker.py` holds a PostgreSQL advisory lock to prevent concurrent execution, and orphaned workers waste resources.
9. **Never push directly to `main` or `master`** without explicit authorization. Always work on and push only to the authorized development branch (`codex/durable-review-pipeline`) or a feature branch/PR.
10. **Never commit secrets or generated artifacts** — `.env`, `.pem` private keys, `backend/venv/`, `node_modules/`, `dist/`, `chroma_db/`, logs, raw API captures, and temporary verification harnesses must stay untracked/ignored.

---

## C. System Prerequisites

### Mandatory

| Prerequisite | Version / Details | Notes |
|---|---|---|
| **Python** | `3.11+` (`>=3.10` in `pyproject.toml`; tested on `3.11.9`) | Required for FastAPI backend, worker, agents, and Python scanners |
| **Node.js** | `18+` (tested on `22.22.2`) | Required for both the React/Vite frontend and the backend's JS/TS static AST parser (`backend/tools/frontend_ast.cjs`) |
| **npm** | Bundled with Node.js (tested on `10.9.7`) | Installs `frontend/` and `backend/tools/parser/` dependencies |
| **PostgreSQL** | `16+` (Docker image uses `16-alpine`; tested locally with `18.4`) | Required for API persistence, review queue, and durable worker advisory locks |
| **Git** | `2.30+` (tested on `2.54.0`) | Required for repository operations and PR checkout (`workspace.py`) |
| **ChromaDB** | `1.5.9` (installed via `backend/requirements.txt`) | Embedded `PersistentClient` inside `backend/venv`; no separate server process required |

### Optional / Scanner-Dependent

| Prerequisite | Version / Details | Notes |
|---|---|---|
| **Bandit** | `1.8.2` | Python security scanner; installed automatically in `backend/venv` via `backend/requirements.txt` |
| **Semgrep** | `1.171.0` | Multi-language scanner; installed in `backend/venv` via `backend/requirements.txt` (falls back to Docker image `returntocorp/semgrep:1.171.0` if native binary is missing or blocked) |
| **Gitleaks** | `8.18.4+` (tested on `8.30.1` native / `v8.18.4` Docker) | Standalone Go binary from [github.com/gitleaks/gitleaks/releases](https://github.com/gitleaks/gitleaks/releases); place in `backend\venv\Scripts\` or `PATH` (falls back to Docker image `zricethezav/gitleaks:v8.18.4`) |
| **Docker & Docker Compose** | Docker `20+`, Compose `v2+` | Optional: runs containerized `postgres`, `migrate`, `backend`, and `worker` stack, or serves as scanner fallback |
| **ngrok** | Recent CLI (`backend/package.json` includes `ngrok` `^5.0.0-beta.2`) | Optional: forwards live GitHub webhooks to `http://127.0.0.1:8080/webhooks/github` during local development |

### Windows Notes

- `backend/worker.py` uses `multiprocessing` (`spawn` context) and `taskkill /PID <pid> /T /F` on Windows (`os.name == "nt"`) to enforce hard per-attempt review timeouts.
- If PowerShell blocks `Activate.ps1` due to execution policy, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, or invoke `.\backend\venv\Scripts\python.exe` directly.
- On Windows sandboxes or restricted environments (e.g., AppControl blocking OCaml `socketpair`), native `semgrep.exe` may fail; Semgrep automatically falls back to Docker when `docker` is on `PATH`.

---

## D. Fresh Clone Setup

Use Windows PowerShell as the primary shell from the parent directory where you want to store the repository:

```powershell
# 1. Clone the repository
git clone https://github.com/DhyanMehta/Code-Guardian.git

# 2. Enter the repository root
Set-Location Code-Guardian

# 3. Check out the development branch
git checkout codex/durable-review-pipeline

# 4. Inspect repository status and recent history
git status
git log --oneline -5
```

---

## E. Python Virtual Environment

All Python commands **MUST** run inside **`backend\venv`**. Never install Python packages globally (`RULES.md` #1–3).

### Create the virtual environment

```powershell
# From the repository root:
python -m venv backend\venv
```

### Activate the environment

```powershell
# Windows PowerShell (primary):
.\backend\venv\Scripts\Activate.ps1

# Windows cmd:
backend\venv\Scripts\activate.bat

# Linux / macOS / Docker:
source backend/venv/bin/activate
```

### Verify Python and pip belong to `backend\venv`

```powershell
(Get-Command python).Source
(Get-Command pip).Source
python -m pip --version
# Both commands must resolve inside ...\Code-Guardian\backend\venv\Scripts\
```

### Install backend dependencies and editable package

`backend/requirements.txt` contains all pinned runtime **and** test dependencies (`pytest`, `pytest-asyncio`, `httpx`). `pyproject.toml` configures the `codeguardian-backend` package so `from backend.x import y` resolves cleanly from any working directory:

```powershell
# With backend\venv active:
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
pip install -e . --no-deps
```

### Explicit venv invocation (recommended in scripts/automation)

When running commands without relying on shell activation state, invoke the venv binary explicitly:

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend/tests
.\backend\venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8080
```

### Safe environment recreation

If `backend\venv` becomes corrupted:

```powershell
Remove-Item -Recurse -Force backend\venv
python -m venv backend\venv
.\backend\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
pip install -e . --no-deps
```

*(Note: If you placed `gitleaks.exe` inside `backend\venv\Scripts\`, back it up or copy it back after recreating the venv.)*

---

## F. Backend Dependencies and Configuration

### Dependency manifests

- **`backend/requirements.txt`** — pinned Python production and test dependencies.
- **`pyproject.toml`** — editable `codeguardian-backend` package metadata (`requires-python >= 3.10`).
- **`backend/tools/parser/package.json` & `package-lock.json`** — pins `typescript@5.7.3` for `backend/tools/frontend_ast.cjs`. Install locally before running JS/TS AST analysis:
  ```powershell
  Set-Location backend\tools\parser
  npm ci
  Set-Location ..\..\..
  ```
- **`backend/package.json`** — optional `ngrok` (`^5.0.0-beta.2`) Node dependency.

### Backend directory structure

```
backend/
├── agents/                  # Four specialist agents + LangGraph supervisor
│   ├── security_agent.py
│   ├── quality_agent.py
│   ├── quality_rules.py     # Deterministic Python rule predicates
│   ├── frontend_analysis.py # Bounded JS/TS/TSX AST analysis extension
│   ├── test_gap_agent.py
│   ├── documentation_agent.py
│   ├── supervisor.py        # LangGraph StateGraph orchestration & aggregate node
│   ├── state.py             # ReviewState TypedDict, AgentOutcome, agent result dataclasses
│   ├── _diff_utils.py       # Unified diff hunk & bounded batching utilities
│   └── _validation.py       # AST symbol existence, naming & draft validation helpers
├── api/                     # FastAPI routers
│   ├── auth.py              # GitHub OAuth login/callback, session JWT cookie, /auth/me, refresh
│   ├── autofix.py           # Auto-fix branch creation & human approve/reject endpoints
│   ├── health.py            # GET /health/live and GET /health/ready
│   ├── installations.py     # Installation, repo, PR listing & manual review trigger
│   ├── metrics.py           # GET /metrics/trends
│   ├── profile.py           # GET/PATCH /profile/review-mode (atomic policy updates)
│   ├── reviews.py           # Review list, detail, and saved Markdown report endpoints
│   ├── standards.py         # Per-installation custom standards upload/status/reset
│   └── webhooks.py          # POST /webhooks/github (HMAC-SHA256 verified)
├── db/
│   ├── database.py          # Lazy SQLAlchemy engine & session factory
│   ├── models.py            # ORM models (reviews, findings, installations, users, checkpoints, heartbeat)
│   └── migrations/          # Alembic env.py and versioned migration scripts
├── rag/
│   ├── ingest.py            # Chunk & embed coding standards into ChromaDB
│   ├── retriever.py         # Query ChromaDB for standards passages
│   └── standards/           # Default coding standards corpus (`python_coding_standards.md`)
├── services/
│   ├── agent_checkpoints.py # Per-agent & Quality batch checkpoint persistence
│   ├── agent_coverage.py    # File eligibility & coverage metadata tracking
│   ├── authorization.py     # Fernet token encryption & live GitHub permission checks
│   ├── autofix_service.py   # Auto-fix commit/branch creation & approval state machine
│   ├── metrics_service.py   # Code-health trend aggregation
│   ├── progress.py          # Persisted real-time review execution events
│   ├── report_builder.py    # Severity ranking, deduplication, and PR Markdown formatting
│   └── review_service.py    # Review lifecycle, checkout, graph run, persistence, comment delivery
├── tools/
│   ├── parser/              # Pinned TypeScript npm package for `frontend_ast.cjs`
│   ├── semgrep_rules/       # Custom Semgrep YAML rules (`frontend_security.yml`, etc.)
│   ├── bandit_runner.py     # Bandit subprocess runner & JSON parser
│   ├── semgrep_runner.py    # Semgrep runner (native + Docker fallback)
│   ├── gitleaks_runner.py   # Gitleaks runner (native + Docker fallback)
│   ├── frontend_ast.cjs     # Node.js static TypeScript AST analyzer
│   ├── github_app.py        # GitHub App JWT & per-installation token cache
│   ├── github_client.py     # Scoped PyGithub client helpers
│   ├── git_auth.py          # Temporary credential-scoped Git checkout authentication
│   ├── llm_client.py        # Groq/Gemini client, retries, semaphore & TokenBucketLimiter
│   ├── llm_metrics.py       # Per-agent call/token/wait telemetry
│   ├── review_budget.py     # Deadline, ProviderRequestBudget, & optional_draft_budget
│   ├── results.py           # RawFinding, Severity, ScannerError hierarchy, _resolve_executable
│   └── workspace.py         # PR checkout & merge-base temp workspace manager
├── tests/                   # Pytest unit, API, RAG, service, tool & PostgreSQL integration tests
├── bootstrap.py             # Runs Alembic upgrade head + default ChromaDB standards check
├── config.py                # pydantic-settings typed configuration (`Settings`)
├── Dockerfile               # Container image (Python 3.11 + Node 22 parser + Gitleaks + Semgrep + Bandit)
├── main.py                  # FastAPI entrypoint & middleware
├── worker.py                # Durable queue worker entrypoint
└── requirements.txt
```

### Environment configuration

Copy `.env.example` to `.env` at the repository root and populate real values (`.env` is git-ignored):

```powershell
Copy-Item .env.example .env
```

#### Required environment variables

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | Groq API key used by `LLMClient` when `LLM_PROVIDER=groq` |
| `GITHUB_APP_ID` | Numeric GitHub App ID |
| `GITHUB_APP_PRIVATE_KEY_PATH` | Filesystem path to the GitHub App `.pem` private key |
| `GITHUB_APP_CLIENT_ID` | GitHub App OAuth client ID |
| `GITHUB_APP_CLIENT_SECRET` | GitHub App OAuth client secret |
| `GITHUB_APP_SLUG` | Public GitHub App slug (used for `/auth/installation-url`) |
| `GITHUB_WEBHOOK_SECRET` | Shared HMAC-SHA256 secret for `POST /webhooks/github` |
| `SESSION_SECRET` | Signing secret for HS256 dashboard `session_jwt` cookies |
| `TOKEN_ENCRYPTION_KEY` | Stable Fernet key for encrypting stored GitHub user tokens |
| `DATABASE_URL` | PostgreSQL connection URL (SQLAlchemy format) |

#### Optional environment variables & defaults (`backend/config.py`)

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `groq` | Active LLM provider (`groq` or `gemini`) |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Default Groq model ID |
| `GROQ_TIMEOUT_SECONDS` | `30` | Per-request timeout for LLM calls |
| `GROQ_MAX_RETRIES` | `3` | Retry attempts for transient provider errors |
| `GEMINI_API_KEY` | `""` | Gemini API key (required if `LLM_PROVIDER=gemini`) |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Default Gemini model ID |
| `LLM_MAX_CONCURRENT_CALLS` | `1` | Process-wide semaphore limiting concurrent LLM requests |
| `LLM_MIN_CALL_INTERVAL_SECONDS` | `1.5` | Minimum delay between consecutive LLM call starts |
| `LLM_TPM_LIMIT` | `8000` | Rolling 60-second tokens-per-minute limit for `TokenBucketLimiter` |
| `LLM_TPM_SAFETY_MARGIN` | `0.8` | Headroom multiplier applied to `LLM_TPM_LIMIT` |
| `LLM_EMPTY_GENERATION_RETRY_DELAY` | `2.0` | Delay before retrying empty JSON generation responses |
| `REVIEW_TIMEOUT_SECONDS` | `900` | Hard per-attempt worker process deadline |
| `MAX_REVIEW_ATTEMPTS` | `2` | Max attempts before an interrupted review is marked `failed` |
| `WORKER_POLL_SECONDS` | `2.0` | Idle polling interval in `backend/worker.py` |
| `REVIEW_PROVIDER_REQUEST_LIMIT` | `None` | Optional hard cap on LLM sends per attempt (requires `MAX_REVIEW_ATTEMPTS=1`) |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | Directory where ChromaDB persists vector collections |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed browser origins (never `*`) |
| `COOKIE_SECURE` | `true` | Set `false` for local HTTP `http://localhost:5173`; `true` in HTTPS production |
| `LEGACY_PAT_ENABLED` | `false` | Opt-in flag for legacy installation-less PAT webhook reviews |
| `GITHUB_TOKEN` | `""` | Legacy PAT (only needed when `LEGACY_PAT_ENABLED=true`) |
| `ALEMBIC_URL` | unset | Optional SQLAlchemy URL override used by `backend/db/migrations/env.py` |

#### Example `.env` using placeholders

```env
LLM_PROVIDER=groq
GROQ_API_KEY=<your-groq-api-key>
GROQ_MODEL=openai/gpt-oss-20b

GITHUB_APP_ID=<your-github-app-id>
GITHUB_APP_PRIVATE_KEY_PATH=./backend/secrets/your-app.private-key.pem
GITHUB_APP_CLIENT_ID=<your-github-app-client-id>
GITHUB_APP_CLIENT_SECRET=<your-github-app-client-secret>
GITHUB_APP_SLUG=<your-github-app-slug>
GITHUB_WEBHOOK_SECRET=<your-webhook-secret>

SESSION_SECRET=<your-random-session-secret>
TOKEN_ENCRYPTION_KEY=<your-generated-fernet-key>
LEGACY_PAT_ENABLED=false

DATABASE_URL=postgresql+psycopg2://guardian:guardian@localhost:5432/codeguardian
CHROMA_PERSIST_DIR=./chroma_db

CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
COOKIE_SECURE=false
```

Generate `TOKEN_ENCRYPTION_KEY` once inside `backend\venv`:

```powershell
.\backend\venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Keep `TOKEN_ENCRYPTION_KEY` stable; rotating it makes stored encrypted GitHub credentials unreadable and requires users to sign in again.

### API host, port, and health endpoints

- **Local host/port:** `http://127.0.0.1:8080` (matches `frontend/.env.example`)
- **Docker Compose mapping:** host `8080` → container `8000`
- **Endpoints:**
  - `GET /` — basic service banner (`{"service": "CodeGuardian AI", ...}`)
  - `GET /docs` — FastAPI interactive Swagger UI
  - `GET /health/live` — liveness probe (`200 {"status": "alive"}`)
  - `GET /health/ready` — readiness probe (`200 ready` / `503 not_ready`) checking `database`, `chromadb`, `worker` heartbeat, and `configuration`

### Backend startup & shutdown

```powershell
# Start API (with backend\venv active):
uvicorn backend.main:app --host 127.0.0.1 --port 8080 --reload
```

Press `Ctrl+C` in the uvicorn terminal to shut down cleanly.

---

## G. PostgreSQL Setup

### Connection configuration

Default `DATABASE_URL`:

```text
postgresql+psycopg2://guardian:guardian@localhost:5432/codeguardian
```

*(Note: `docker-compose.yml` uses `postgresql+psycopg2://guardian:guardian@postgres:5432/codeguardian` inside Docker Compose.)*

### Initialize database (fresh setup)

Ensure PostgreSQL is running, then create the user and database if they do not exist:

```powershell
psql -U postgres -c "CREATE USER guardian WITH PASSWORD 'guardian';"
psql -U postgres -c "CREATE DATABASE codeguardian OWNER guardian;"
```

### Run migrations and initialize defaults

```powershell
# With backend\venv active:
python -m backend.bootstrap
```

`backend/bootstrap.py` runs `alembic upgrade head` (using `alembic.ini` → `backend/db/migrations`) and ingests default ChromaDB coding standards if missing or empty. It is idempotent and safe on both fresh and existing databases.

### Inspect migration status

```powershell
.\backend\venv\Scripts\python.exe -m alembic current
.\backend\venv\Scripts\python.exe -m alembic heads
```

*(Optionally set `$env:ALEMBIC_URL` to override `DATABASE_URL` when inspecting or generating offline SQL migrations.)*

### Verify database connectivity

- Via readiness endpoint (when API is running):
  ```powershell
  Invoke-RestMethod http://localhost:8080/health/ready
  # `checks.database` should be "ok"
  ```
- Directly via Python in `backend\venv`:
  ```powershell
  .\backend\venv\Scripts\python.exe -c "from sqlalchemy import text; from backend.db.database import get_engine; print(get_engine().connect().execute(text('SELECT 1')).scalar())"
  ```

### Fresh setup vs. existing database

- `python -m backend.bootstrap` applies only pending migrations without dropping tables or rows.
- **Never** drop an existing database as an ordinary setup step. Back up existing data before upgrading schemas.

---

## H. ChromaDB and RAG Setup

### How ChromaDB works

ChromaDB (`1.5.9`) runs as an **embedded `chromadb.PersistentClient`** writing directly to `CHROMA_PERSIST_DIR` (default `./chroma_db`). There is no separate Chroma server process.

> **Important:** RAG ingestion is vector indexing, **not** model fine-tuning. It splits Markdown coding standards into passages, embeds them locally in ChromaDB, and retrieves relevant rules at review time. The underlying LLM weights are never modified.

### Default coding standards & chunking

- **Default corpus directory:** `backend/rag/standards/`
- **Default file:** `backend/rag/standards/python_coding_standards.md` (`README.md` in that folder is intentionally ignored by `_load_source_documents()`).
- **Chunking rules (`backend/rag/ingest.py`):** Splits on `\n---\n` separators (falling back to `## ` headings), discards chunks under `30` characters, and assigns deterministic SHA-256 content-hash IDs (`_stable_id`).

### Ingestion & collection versioning

- **Bootstrap initialization:** `python -m backend.bootstrap` ingests default standards automatically if the active collection is missing or empty.
- **Manual re-ingestion:**
  ```powershell
  .\backend\venv\Scripts\python.exe -m backend.rag.ingest
  ```
- **Collection naming & version pointer:**
  - Default ingestion creates a new UUID-suffixed collection `coding_standards_default_<uuid>` and atomically updates `chroma_db/active_standards.json`.
  - If `active_standards.json` does not exist, `resolve_active_collection()` falls back to `"coding_standards"`.
  - Custom per-installation uploads via `POST /installations/{id}/standards` (admin-only, `.md` UTF-8, max `512 KB`) create `coding_standards_<installation_id>_<uuid>` and persist `standards_version` on the `installations` row in PostgreSQL.
  - Each `Review` captures `standards_version` at start so historical reviews remain reproducible even after later uploads or resets (`DELETE /installations/{id}/standards` clears the DB pointer while keeping older collections intact).

### Retrieval configuration (`backend/rag/retriever.py`)

- `DEFAULT_TOP_K = 5`
- `_MIN_RELEVANCE_SCORE = 1.65` (ChromaDB L2 distance cutoff; lower = more similar; passages above `1.65` are filtered out).
- Lookup order in `_get_collection()`: explicit `collection_name` (`standards_version`) → legacy custom collection `coding_standards_<installation_id>` (if present and non-empty) → `resolve_active_collection()`.

### Verification & diagnostics

- **Verify default corpus:** `Invoke-RestMethod http://localhost:8080/health/ready` (`checks.chromadb` must be `"ok"`).
- **Diagnose `chromadb: unavailable`:**
  1. Confirm `CHROMA_PERSIST_DIR` points to the intended directory (relative `./chroma_db` from repo root).
  2. Confirm `backend/rag/standards/python_coding_standards.md` is present and non-empty.
  3. Run `.\backend\venv\Scripts\python.exe -m backend.rag.ingest` to rebuild and activate a fresh default collection.
- **Avoid overwriting custom standards:** `python -m backend.rag.ingest` only writes a new default collection (`coding_standards_default_<uuid>`) and updates `active_standards.json`; it never modifies custom installation collections (`coding_standards_<id>_*`) or installation DB pointers.

---

## I. Groq Integration

### Configuration & overrides (`backend/config.py`, `backend/tools/llm_client.py`)

| Variable | Default | Notes |
|---|---|---|
| `GROQ_API_KEY` | `""` (required for `groq`) | Never commit or log |
| `LLM_PROVIDER` | `groq` | Supported: `groq`, `gemini` |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Overridable; for `gpt-oss` models, `reasoning_effort="low"` is sent automatically so reasoning tokens do not exhaust `max_tokens` before emitting JSON |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | `""` / `gemini-3.5-flash-lite` | Used when `LLM_PROVIDER=gemini` |
| `GROQ_TIMEOUT_SECONDS` | `30` | Per-call timeout (clamped to remaining review deadline when active) |
| `GROQ_MAX_RETRIES` | `3` | Retry count for transient rate-limit, timeout, connection, and 5xx errors |
| `LLM_MAX_CONCURRENT_CALLS` | `1` | Process-wide semaphore gating simultaneous provider calls across the 4 parallel agents |
| `LLM_MIN_CALL_INTERVAL_SECONDS` | `1.5` | Minimum spacing between consecutive provider calls |
| `LLM_TPM_LIMIT` | `8000` | Rolling 60-second token cap enforced by `TokenBucketLimiter` |
| `LLM_TPM_SAFETY_MARGIN` | `0.8` | Safe TPM budget (`max(100, int(8000 * 0.8)) = 6400` tokens/min) |
| `LLM_EMPTY_GENERATION_RETRY_DELAY` | `2.0` | Delay before retrying Groq `json_validate_failed` empty-generation responses (up to 3 attempts) |
| `REVIEW_PROVIDER_REQUEST_LIMIT` | `None` | Optional shared per-attempt LLM request cap (`ProviderRequestBudget`); requires `MAX_REVIEW_ATTEMPTS=1` |

### Rate limits, budgets & retry behavior

- **Retries & cooldowns:** Transient errors (`RateLimitError`, timeout, connection, 5xx) retry with exponential backoff (`backoff_base * 2**attempt`, `backoff_base=0.5`), honoring `retry-after` headers and `retry in Xs` messages up to `MAX_RATE_LIMIT_WAIT = 65.0` seconds. Auth errors (`401`/`403`) fail immediately as `LLMAuthError`.
- **Priority budgeting (`backend/tools/review_budget.py`):** When `analysis_deadline` is active in the worker, `optional_draft_budget()` makes Test-Gap and Documentation wait for Security + Quality required analysis to finish before claiming up to 60 seconds for optional test/docstring drafting.

### Safe verification without calling Groq

- Start the API and check `GET /health/ready` (validates local secrets/DB/Chroma without calling Groq).
- Run `.\backend\venv\Scripts\python.exe -m scripts.verify_backend_runtime` **without** `--llm` to verify scanners safely.
- **Do NOT** pass `--llm` or run live reviews unnecessarily (`RULES.md` / `CONTEXT.md`: ~12 reviews/day ceiling on free tier).

---

## J. Four Specialist Agents and Supervisor

All four specialist agents run **inside the LangGraph supervisor graph** invoked by `review_service.py` (which is invoked by `backend/worker.py`). They do **not** have standalone CLI entrypoints for running against arbitrary repos individually outside tests.

### 1. Security Agent
- **Source:** `backend/agents/security_agent.py` (with `backend/tools/semgrep_runner.py`, `bandit_runner.py`, `gitleaks_runner.py`, `results.py`, and `backend/agents/_diff_utils.py`).
- **Responsibilities:** Run Semgrep, Bandit, and Gitleaks over the workspace, normalize paths to repo-relative form, scope raw findings to PR diff hunks, and call the LLM strictly to triage, explain, and priority-rank those raw findings. Any LLM item whose `fingerprint` does not match a real `RawFinding` is dropped.
- **Dependencies & required services:** Installed scanners (or Docker fallback) + Groq/Gemini LLM (only when raw findings exist).
- **Inputs:** `workspace_path: str`, `diff: str`.
- **Output (`SecurityAgentResult`):** `raw_findings`, `triaged_findings`, `scanner_statuses`, `notes`, `outcome` (`AgentOutcome`), `failure_reason`.
- **Isolated tests:**
  ```powershell
  .\backend\venv\Scripts\python.exe -B -m pytest backend/tests/test_agents/test_security_agent.py
  ```

### 2. Quality Agent
- **Source:** `backend/agents/quality_agent.py`, `backend/agents/quality_rules.py`, `backend/agents/_validation.py`, `backend/agents/frontend_analysis.py`.
- **Responsibilities:** Split diffs into bounded batches (`bounded_diff_batches`), skip unsupported/generated files, query ChromaDB RAG for coding standards, evaluate deterministic supported Python rules (`maximum_function_length`, `maximum_positional_parameters`, `future_annotations_import`) before optional LLM enrichment, and enforce 3 anti-hallucination gates on LLM proposals (rule-passage citation, AST symbol existence + line correction, countable-claim verification). Frontend JS/TS/TSX files are checked via `frontend_analysis.py` (`frontend_ast.cjs`) only when an applicable frontend rule is retrieved.
- **Dependencies & required services:** ChromaDB (`CHROMA_PERSIST_DIR`), Python AST/`tokenize`, Node.js + `backend/tools/parser` (for JS/TS files), Groq/Gemini LLM (for optional enrichment/advisories).
- **Inputs:** `diff: str`, `changed_files: list[str]`, `workspace_path: str`, `installation_id: int | None`, `standards_version: str | None`.
- **Output (`QualityAgentResult`):** `findings` (`QualityFinding` with `evidence_kind: "verified" | "advisory"`), `retrieval_context`, `notes`, `outcome`, `failure_reason`.
- **Isolated tests:**
  ```powershell
  .\backend\venv\Scripts\python.exe -B -m pytest backend/tests/test_agents/test_quality_agent.py backend/tests/test_agents/test_quality_agent_regressions.py backend/tests/test_agents/test_quality_discovery.py
  ```

### 3. Test Gaps Agent
- **Source:** `backend/agents/test_gap_agent.py`, `backend/agents/_validation.py`, `backend/agents/frontend_analysis.py`.
- **Responsibilities:** Deterministically scan modified Python functions/methods via AST, exclude test files (`test_*.py`, `*_test.py`), check for direct static references in test files, score complexity/length risk (`0–10`), and optionally call the LLM to draft starter pytest unit tests (validated for syntax, target call, and valid workspace imports). For JS/TS/TSX files, checks relative import references in `.test/.spec` files.
- **Dependencies & required services:** Python AST, Node.js + `backend/tools/parser` (for JS/TS), LLM client (optional drafting only; detection runs without LLM).
- **Inputs:** `diff: str`, `changed_files: list[str]`, `workspace_path: str`.
- **Output (`TestGapAgentResult`):** `gaps` (`TestGap`), `drafted_tests` (`DraftedTest`), `notes`, `outcome`.
- **Isolated tests:**
  ```powershell
  .\backend\venv\Scripts\python.exe -B -m pytest backend/tests/test_agents/test_test_gap_agent.py
  ```

### 4. Documentation Agent
- **Source:** `backend/agents/documentation_agent.py`, `backend/agents/_validation.py`, `backend/agents/frontend_analysis.py`.
- **Responsibilities:** Deterministically check modified Python functions/methods for missing docstrings or outdated parameter docs against the AST signature, and optionally call the LLM to draft Google-style docstrings (dropped if they reference non-existent parameters or targets). For JS/TS/TSX files, flags exported functions whose existing JSDoc `@param` tags mismatch current parameters.
- **Dependencies & required services:** Python AST, Node.js + `backend/tools/parser` (for JS/TS), LLM client (optional drafting only).
- **Inputs:** `diff: str`, `changed_files: list[str]`, `workspace_path: str`.
- **Output (`DocAgentResult`):** `flagged_functions` (`DocTarget`), `drafted_docstrings` (`DraftedDocstring`), `notes`, `outcome`.
- **Isolated tests:**
  ```powershell
  .\backend\venv\Scripts\python.exe -B -m pytest backend/tests/test_agents/test_documentation_agent.py
  ```

### 5. Supervisor (Orchestration Mechanism)
- **Source:** `backend/agents/supervisor.py`, `backend/agents/state.py`, `backend/services/agent_coverage.py`, `backend/services/agent_checkpoints.py`.
- **Mechanism:** Deterministic LangGraph `StateGraph(ReviewState)` compiled via `build_supervisor_graph()`. Uses a conditional edge from `START` (`_fan_out`) returning `Send` objects for `("security", "quality", "test_gap", "documentation")`, partial-failure isolation per node, reducer-based state merging (`_merge_dicts`), checkpoint loading/saving (`review_agent_checkpoints`), coverage tracking (`AgentCoverage`), frontend analysis enrichment (`extend_result`), and a deterministic `_aggregate` node → `END`.
- **Isolated tests:**
  ```powershell
  .\backend\venv\Scripts\python.exe -B -m pytest backend/tests/test_agents/test_supervisor.py backend/tests/test_agent_correctness.py backend/tests/test_pipeline_recovery.py backend/tests/test_release_correctness.py
  ```

---

## K. Security Scanner Setup

| Scanner | Installation | Version / Check | Supported Scope & Limitations | Unavailable / Fallback Behavior |
|---|---|---|---|---|
| **Bandit** | Included in `backend/requirements.txt` (`bandit==1.8.2`) | `.\backend\venv\Scripts\bandit.exe --version` | Python (`.py`) files only; scoped to PR diff hunks | Raises `ScannerError` → Security Agent marks Bandit failed (`DEGRADED` if all scanners fail) |
| **Semgrep** | Included in `backend/requirements.txt` (`semgrep==1.171.0`) | `.\backend\venv\Scripts\semgrep.exe --version` | `.py`, `.js`, `.jsx`, `.mjs`, `.cjs`, `.ts`, `.tsx` (`.d.ts` excluded); runs rules from `backend/tools/semgrep_rules/` | Falls back to Docker (`returntocorp/semgrep:1.171.0`) if native binary is missing/blocked (e.g., Windows AppControl or sandbox `socketpair` restriction) |
| **Gitleaks** | Download binary from [gitleaks releases](https://github.com/gitleaks/gitleaks/releases) and place in `backend\venv\Scripts\` (Windows) or `PATH` | `.\backend\venv\Scripts\gitleaks.exe version` | Secrets scan (`--no-git`) across all changed files | Falls back to Docker (`zricethezav/gitleaks:v8.18.4`) if native binary is missing; reports `DEGRADED` if both fail |

### Executable resolution & safe local check

`backend/tools/results.py` (`_resolve_executable`) checks `shutil.which(name)` and then looks in `Path(sys.executable).parent` (the `backend/venv` `Scripts/` or `bin/` folder) so subprocesses locate pip-installed scanners reliably on Windows.

Verify all three scanners locally against synthetic code without calling GitHub or Groq:

```powershell
.\backend\venv\Scripts\python.exe -m scripts.verify_backend_runtime
```

When a scanner is unavailable and cannot fall back to Docker, the Security Agent catches `ScannerError`, records `ok=False` in `scanner_statuses`, never suppresses findings from working scanners, and marks `agent_outcomes["security"]` as `degraded` if all scanners failed (`supervisor.py`).

---

## L. Review Worker

- **Entry point:** `backend/worker.py` (`python -m backend.worker`)
- **Required environment:** **PostgreSQL** (`engine.dialect.name != "postgresql"` raises `RuntimeError`), configured `.env` secrets, initialized DB migrations, and populated ChromaDB standards.
- **Relationship with API:** The FastAPI API (`POST /webhooks/github` and manual trigger `POST /installations/{id}/repos/{owner}/{repo}/pulls/{n}/review`) only inserts `pending` `Review` rows and returns `202`. The separate worker executes reviews and delivers comments.
- **Queue & concurrency:**
  1. Each poll (`WORKER_POLL_SECONDS=2.0`) spawns a fresh `multiprocessing.get_context("spawn")` child process bounded by `REVIEW_TIMEOUT_SECONDS` (default `900s`).
  2. The child acquires PostgreSQL session advisory lock `LOCK_ID = 73194201`, guaranteeing **only one active review attempt system-wide**.
  3. Any stale `running` review from a crashed prior worker is recovered (`pending` if `attempt < MAX_REVIEW_ATTEMPTS`, else `failed`).
  4. Duplicate queued automatic revisions (`requested_by IS NULL`) for the same `(installation_id, repo_full_name, pr_number)` are marked `skipped` in favor of the newest queued row; manual reviews remain queued individually.
  5. Due report deliveries (`status='completed'`, `delivery_attempts < 3`, `delivery_status='pending'` or retryable `'failed'`) run before new pending reviews.
  6. A heartbeat thread updates `worker_heartbeat` (`id=1`) every `15s` (and `reviews.heartbeat_at` while running).
  7. After executing a review (`did_review.is_set()`), the parent sleeps at least `60s` so the child process's rolling 60s LLM TPM window expires before the next review.
- **Checkpoints & retries:** Completed agents and Quality batches save fingerprinted payloads in `review_agent_checkpoints` (`backend/services/agent_checkpoints.py`) and reuse them on retry (`attempt < MAX_REVIEW_ATTEMPTS`). Execution stages are recorded in `review_progress`.
- **Readiness & duplicate avoidance:** Never start two `python -m backend.worker` processes. Check `GET /health/ready` (`checks.worker` is `"ok"` when `worker_heartbeat.updated_at` is within 90 seconds).
- **Safe shutdown:** Press `Ctrl+C` in the worker terminal (`KeyboardInterrupt` invokes `terminate_attempt()` cleanly).
- **Troubleshooting stuck reviews:**
  - `pending` indefinitely → Check `GET /health/ready` (`worker: unavailable` means the worker is stopped).
  - Stuck `running` after an unclean kill → Restarting the worker acquires advisory lock `73194201` and resets stale `running` rows automatically.
- **Worker/pipeline tests:**
  ```powershell
  .\backend\venv\Scripts\python.exe -B -m pytest backend/tests/test_review_lock.py backend/tests/test_pipeline_recovery.py
  # With PostgreSQL running (uses disposable cg_test_* schemas):
  $env:CODEGUARDIAN_TEST_POSTGRES = "1"
  .\backend\venv\Scripts\python.exe -B -m pytest backend/tests/test_postgres_pipeline.py -o addopts= --tb=short
  ```

---

## M. Frontend Setup

- **Prerequisites:** Node.js `18+` (tested on `22.22.2`) and npm.
- **Install dependencies (using lockfile):**
  ```powershell
  Set-Location frontend
  npm ci
  ```
- **Environment variables:** Create `frontend\.env` from `frontend\.env.example`:
  ```env
  VITE_API_BASE_URL=http://localhost:8080
  VITE_GITHUB_APP_SLUG=your-github-app-slug
  ```
- **Backend pairing:** Ensure root `.env` sets `CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173` and `COOKIE_SECURE=false` for local HTTP development, and browse using `http://localhost:5173` consistently so cookies/OAuth origin match.
- **Development server (`http://localhost:5173`, `strictPort: true` in `vite.config.ts`):**
  ```powershell
  npm run dev
  ```
- **Type check, production build, and preview:**
  ```powershell
  npx tsc -b --noEmit
  npm run build      # runs `tsc -b && vite build` -> outputs to frontend/dist/ (git-ignored)
  npm run preview
  ```
- **Test suite (`Vitest` + Testing Library + `jsdom`):**
  ```powershell
  npm test           # runs `vitest run`
  ```
- **Read-only / UI-only frontend development mode:** For UI/component work or running `npm test` / `npm run build`, only the `frontend/` terminal (`npm run dev`) is needed. The FastAPI API, review worker, PostgreSQL, and ngrok are not required (unbacked pages simply show connection/auth states while all Vitest integration tests use controlled responses).

---

## N. GitHub App Setup

CodeGuardian AI uses a GitHub App for multi-tenant authentication, repository discovery, PR comments, and auto-fix branch creation.

### GitHub App Registration Settings (Local Dev)

| Setting | Value |
|---|---|
| **Callback URL** | `http://localhost:5173/auth/callback` |
| **Setup URL** | `http://localhost:5173/auth/install` |
| **Request user authorization (OAuth) during installation** | **Disabled** |
| **Redirect on update** | **Enabled** |
| **Visibility** | Public (if external accounts install it) or Private (owner account only) |

### Required GitHub App Permissions & Events

- **Permissions:**
  - **Pull requests:** Read & Write (read PR diffs/metadata, publish review comments)
  - **Contents:** Read & Write (clone repositories, push human-gated auto-fix branches)
  - **Metadata:** Read (repository discovery)
  - **Checks:** Read (PR status context)
- **Webhook Events:**
  - `pull_request` (`opened`, `synchronize`, `reopened`)
  - `installation` (`created`, `deleted`, `suspend`, `unsuspend`, `new_permissions_accepted`)

### Credentials & Access Flow

- **Private key & secret:** Store the downloaded `.pem` key outside version control (e.g., `backend/secrets/` which is git-ignored) and set `GITHUB_APP_PRIVATE_KEY_PATH` and `GITHUB_WEBHOOK_SECRET` in `.env`.
- **Auth & cookies (`backend/api/auth.py`):** `/auth/github/login` sets an `oauth_state` httpOnly cookie; `POST /auth/github/callback` exchanges the code, Fernet-encrypts user OAuth tokens (`TOKEN_ENCRYPTION_KEY`), syncs `user_installations`, and sets an HS256 `session_jwt` cookie (30-day expiry, `COOKIE_SECURE=false` for local HTTP).
- **Installation verification:** `/auth/install` reconciles access via `POST /auth/installations/refresh` (query params never grant access).
- **Review modes (`auto` vs `manual`):**
  - `auto`: Webhook `pull_request` events enqueue reviews automatically; installation-level mode checked in `backend/api/webhooks.py`.
  - `manual`: Webhooks ignore PR triggers; reviews are triggered from the dashboard (`POST /installations/{id}/repos/{owner}/{repo}/pulls/{number}/review`).
  - Configured via `PATCH /installations/{id}/settings` or atomically across all administered installations via `PATCH /profile/review-mode`.
- **Authorization gates (`backend/services/authorization.py`):**
  - Read endpoints check live GitHub repository access.
  - Manual review triggers and auto-fix branch creation/approval/rejection require live repository `write` permission.
  - Installation settings and custom standards uploads/resets require installation `admin` role.
  - `LEGACY_PAT_ENABLED` defaults to `false` (legacy PAT fallback is disabled unless explicitly opted in).

---

## O. ngrok and Webhook Setup

ngrok is **optional** and only needed during local development when testing real GitHub webhook deliveries against your local machine.

- **Local target exposed:** FastAPI backend on port `8080` (`POST /webhooks/github`).
- **Start tunnel (in a dedicated terminal):**
  ```powershell
  ngrok http 8080
  ```
  *(Alternatively, `scripts/pr_webhook_forwarder.py` provides a loopback-only scoped relay on port `8081` for controlled PR smoke tests.)*
- **GitHub Webhook URL format:** `https://<your-ngrok-domain>/webhooks/github`
- **Signature requirement:** Set the GitHub App webhook secret to match `GITHUB_WEBHOOK_SECRET` in `.env`. Every `POST /webhooks/github` request requires a valid `X-Hub-Signature-256` (`sha256=...`) HMAC-SHA256 digest of the raw request body (`backend/api/webhooks.py`).
- **Safe shutdown:** Press `Ctrl+C` in the ngrok terminal when finished. Do not leave public tunnels open unattended.

---

## P. Complete Startup Sequence

### Full-stack local development (separate PowerShell terminals)

**1. PostgreSQL**
Ensure your PostgreSQL service is running and the `codeguardian` database/user exist (or run `docker compose up postgres -d`).

**2. Terminal 1 — Environment, DB Migration, Standards Init & FastAPI Backend**
```powershell
Set-Location <repo-root>
.\backend\venv\Scripts\Activate.ps1
(Get-Command python).Source

# Run migrations + ensure default ChromaDB standards exist (idempotent):
python -m backend.bootstrap

# Start FastAPI API on port 8080:
uvicorn backend.main:app --host 127.0.0.1 --port 8080 --reload
```

**3. Terminal 2 — Durable Review Worker** *(only start one worker)*
```powershell
Set-Location <repo-root>
.\backend\venv\Scripts\Activate.ps1
python -m backend.worker
```

**4. Terminal 3 — React / Vite Frontend**
```powershell
Set-Location <repo-root>\frontend
npm run dev
```

**5. Terminal 4 — Optional ngrok Tunnel** *(only when testing live GitHub webhooks)*
```powershell
ngrok http 8080
```

**6. GitHub Auth & Readiness Verification**
- Open `http://localhost:5173` in your browser, sign in via GitHub OAuth, and verify connected installations/repositories.
- Verify backend readiness: `Invoke-RestMethod http://localhost:8080/health/ready` (`database`, `chromadb`, `worker`, and `configuration` should all report `ok`).

*(Alternative containerized stack: `docker compose up --build` starts `postgres`, one-shot `migrate` running `python -m backend.bootstrap`, `backend` on host port `8080`, and `worker`, plus run the Vite frontend separately.)*

### Frontend-only (read-only UI & test) mode

If you are only developing or testing UI components without running reviews or webhooks, skip PostgreSQL, the FastAPI API, the durable worker, and ngrok — run **only** Terminal 3 (`Set-Location frontend; npm run dev`, `npm test`, `npm run build`).

---

## Q. Verification and Testing

| Check | Command (from repo root unless noted) | Safety / External Requirements |
|---|---|---|
| **Offline backend suite** | `.\backend\venv\Scripts\python.exe -B -m pytest backend/tests -p no:cacheprovider --tb=short` | Safe; mocks LLM & GitHub, uses SQLite/temp Chroma |
| **Agent unit tests** | `.\backend\venv\Scripts\python.exe -B -m pytest backend/tests/test_agents backend/tests/test_agent_correctness.py` | Safe; no live API calls |
| **Supervisor & worker tests** | `.\backend\venv\Scripts\python.exe -B -m pytest backend/tests/test_agents/test_supervisor.py backend/tests/test_pipeline_recovery.py backend/tests/test_review_lock.py` | Safe; mocked DB/LLM |
| **RAG tests** | `.\backend\venv\Scripts\python.exe -B -m pytest backend/tests/test_rag` | Safe; uses temp Chroma dirs |
| **PostgreSQL pipeline tests** | `$env:CODEGUARDIAN_TEST_POSTGRES="1"; .\backend\venv\Scripts\python.exe -B -m pytest backend/tests/test_postgres_pipeline.py -o addopts= --tb=short` | Requires local PostgreSQL; creates & drops disposable `cg_test_*` schemas |
| **Real scanner + DB pipeline test** | `$env:CODEGUARDIAN_TEST_POSTGRES="1"; $env:CODEGUARDIAN_TEST_RUNTIME="1"; .\backend\venv\Scripts\python.exe -B -m pytest backend/tests/test_postgres_pipeline.py -o addopts= --tb=short` | Requires PostgreSQL + installed scanners; LLM/GitHub stay mocked |
| **Scanner diagnostics** | `.\backend\venv\Scripts\python.exe -m scripts.verify_backend_runtime` | Safe; runs Bandit, Semgrep, Gitleaks on synthetic temp Python file |
| **Live GitHub / LLM check** | `.\backend\venv\Scripts\python.exe -m scripts.verify_backend_runtime --github --llm` | **Consumes Groq quota & calls GitHub API** — run only when authorized |
| **Frontend tests** | `Set-Location frontend; npm test` | Safe; Vitest + jsdom |
| **Frontend typecheck & build** | `Set-Location frontend; npx tsc -b --noEmit; npm run build` | Safe; static check & bundle |
| **Health & readiness** | `Invoke-RestMethod http://localhost:8080/health/live; Invoke-RestMethod http://localhost:8080/health/ready` | Safe; no Groq or GitHub calls |

---

## R. Troubleshooting

| Issue | Likely Cause & Fix |
|---|---|
| **Incorrect Python interpreter / `ModuleNotFoundError`** | Global Python used instead of `backend\venv`. Activate `.\backend\venv\Scripts\Activate.ps1` and verify `(Get-Command python).Source`. |
| **Missing virtual environment** | Create it with `python -m venv backend\venv`, activate, install `backend/requirements.txt` and `pip install -e . --no-deps`. |
| **Missing Python or JS parser dependencies** | Run `pip install -r backend/requirements.txt` in `backend\venv`, and `npm ci` inside `backend/tools/parser/` (and `frontend/`). |
| **PostgreSQL unavailable (`database: unavailable`)** | PostgreSQL service stopped or `DATABASE_URL` invalid. Start PostgreSQL and verify `psql -U guardian -d codeguardian -c "SELECT 1;"`. |
| **Database migration errors** | Run `.\backend\venv\Scripts\python.exe -m backend.bootstrap` or inspect `alembic current` vs `alembic heads`. |
| **ChromaDB collection missing (`chromadb: unavailable`)** | Run `.\backend\venv\Scripts\python.exe -m backend.bootstrap` or `.\backend\venv\Scripts\python.exe -m backend.rag.ingest`. Verify `CHROMA_PERSIST_DIR`. |
| **Default coding standards unavailable** | Ensure `backend/rag/standards/python_coding_standards.md` exists and is non-empty, then re-run `python -m backend.rag.ingest`. |
| **Groq `401` auth error or `429` rate limit** | For `401`, check `GROQ_API_KEY` in `.env`. For `429`, wait for the 60s TPM window (or next UTC day for daily TPD/RPD limits); do not spam retries. |
| **Missing security scanner (`DEGRADED` Security Agent)** | Install `bandit`/`semgrep` in `backend\venv` and `gitleaks` in `backend\venv\Scripts\` (or enable Docker fallback). On Windows sandboxes, `semgrep.exe` may require running outside the sandbox or using Docker. |
| **Worker not running (`worker: unavailable`)** | Reviews stay `pending`. Start `python -m backend.worker` in a separate activated terminal. |
| **Duplicate workers** | Stop extra worker instances; only one worker can hold advisory lock `73194201`. |
| **Backend connection refused (`ERR_CONNECTION_REFUSED`)** | Start uvicorn on `127.0.0.1:8080` and confirm `frontend/.env` `VITE_API_BASE_URL=http://localhost:8080`. |
| **Frontend CORS errors or missing login cookie** | Ensure `CORS_ALLOWED_ORIGINS` includes `http://localhost:5173`, `COOKIE_SECURE=false` for local HTTP, and browse on `http://localhost:5173` (not mixed `127.0.0.1` vs `localhost`). Restart backend after `.env` edits. |
| **Expired GitHub session (`401`)** | Re-authenticate via "Sign in with GitHub" on the dashboard; session JWTs expire or are invalidated on logout/revocation. |
| **Webhook delivery failure** | Confirm ngrok is running against port `8080`, GitHub App webhook URL ends with `/webhooks/github`, and `GITHUB_WEBHOOK_SECRET` matches. |
| **Incorrect installation access (`403` / missing repos)** | Click refresh access in the UI (`POST /auth/installations/refresh`) and verify repository permissions on GitHub. |
| **Port conflicts (`8080` or `5173` in use)** | Find the owning PID with `netstat -ano | findstr ":8080"` or `":5173"` and stop only that specific conflicting process. |

---

## S. Shutdown and Restart

1. **Frontend:** Press `Ctrl+C` in the Vite (`npm run dev`) terminal.
2. **Backend API:** Press `Ctrl+C` in the uvicorn terminal.
3. **Review Worker:** Press `Ctrl+C` in the `python -m backend.worker` terminal (`KeyboardInterrupt` cleanly stops active child attempts via `terminate_attempt()`).
4. **ngrok Tunnel (if running):** Press `Ctrl+C` in the ngrok terminal.
5. **PostgreSQL:** Leave running or stop via Windows Services / `docker compose stop postgres`.

> **Warning:** Never run broad process-killing commands like `taskkill /IM python.exe /F` or `Stop-Process -Name python` — they can terminate unrelated applications or IDE services.

To restart, follow Section **P** in order (PostgreSQL → API → single Worker → Frontend).

---

## T. Git and Development Workflow

- **Authorized development branch:** `codex/durable-review-pipeline`
- **Inspect state safely before staging/committing:**
  ```powershell
  git status
  git diff --check
  git diff --stat
  git log --oneline -10
  ```
- **Explicit staging only:**
  ```powershell
  git add <explicit-file-paths>
  git diff --cached --check
  git diff --cached --stat
  ```
  **Never** run `git add -A` or `git add .` — local logs, `.env`, `.pem` keys, `chroma_db/`, `dist/`, temporary verification harnesses, and raw captures could be staged unintentionally.
- **Commit conventions:** Use clear imperative messages (`feat(...)`, `fix(...)`, `docs(...)`, `test(...)`).
- **Push to the development branch only:**
  ```powershell
  git push -u origin codex/durable-review-pipeline
  ```
- **Hard restrictions:**
  - Never commit `.env`, `.pem` files, credentials, `backend/venv/`, `node_modules/`, `dist/`, `chroma_db/`, logs, or temporary verification scripts.
  - Never push directly to `main` or `master` or merge automatically (`RULES.md` #12–13).
  - Never force-push (`--force` / `--force-with-lease`).

---

## Appendix: Key Project References

| File | Purpose |
|---|---|
| [`RULES.md`](RULES.md) | Binding engineering, environment, and safety rules |
| [`CONTEXT.md`](CONTEXT.md) | Project context, known limitations, and rate-limit constraints |
| [`ENDPOINTS.md`](ENDPOINTS.md) | Living HTTP API contract |
| [`README.md`](README.md) | Quick-start project overview |
| [`docs/BACKEND_RELIABILITY.md`](docs/BACKEND_RELIABILITY.md) | Durable worker, authorization, auto-fix, and reliability contract |
| [`.env.example`](.env.example) | Backend environment template with placeholders |
| [`frontend/.env.example`](frontend/.env.example) | Frontend environment template (`VITE_API_BASE_URL`, `VITE_GITHUB_APP_SLUG`) |
| [`docker-compose.yml`](docker-compose.yml) | Local Docker Compose development stack |
| [`alembic.ini`](alembic.ini) | Alembic database migration configuration |
| [`pyproject.toml`](pyproject.toml) | Backend editable package metadata |
| [`pytest.ini`](pytest.ini) | Pytest configuration |
