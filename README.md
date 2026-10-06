# CodeGuardian AI

An autonomous multi-agent code review and DevSecOps platform. It reviews GitHub pull
requests using a Supervisor Agent (LangGraph) that coordinates four specialist agents —
Security, Quality, Test-Gap, and Documentation — then posts one severity-ranked report
as a PR comment and can open an auto-fix branch that requires explicit human approval.

See [`CONTEXT.md`](CONTEXT.md) for architecture, [`RULES.md`](RULES.md) for the binding
engineering rules, and [`ENDPOINTS.md`](ENDPOINTS.md) for the API contract.

## How it works

```
GitHub PR event → FastAPI webhook → PostgreSQL queue → Worker → Supervisor (LangGraph)
                                        │ parallel fan-out
              ┌─────────────┬───────────┼───────────┐
              ▼             ▼           ▼           ▼
        Security       Quality     Test-Gap   Documentation
        (Semgrep,      (RAG over   (AST       (docstring
         Bandit,        standards)  analysis)   coverage)
         Gitleaks)
              └─────────────┴───────────┴───────────┘
                         │ aggregate + rank
                         ▼
          PR comment + optional auto-fix branch
                         ▼
              PostgreSQL → React dashboard
```

Key design principle: deterministic scanners produce the raw findings; the LLM (Groq)
only triages, explains, and prioritizes — it never originates a finding.

## Prerequisites
- Python 3.11+
- Node.js 18+ (for the frontend dashboard)
- Docker + Docker Compose (for the full local stack)
- Git
- Scanner binaries: Semgrep, Gitleaks (Bandit installs via pip)

## Local setup

### Backend

```powershell
# From the project root
python -m venv backend\venv

# Activate (Windows PowerShell)
backend\venv\Scripts\Activate.ps1
# Windows cmd:            backend\venv\Scripts\activate.bat
# Linux/macOS/Docker:     source backend/venv/bin/activate

# Confirm the venv is active
where python        # should resolve inside backend\venv

# Install dependencies
python -m pip install --upgrade pip
pip install -r backend/requirements.txt

# Install Gitleaks native binary
# Download from https://github.com/gitleaks/gitleaks/releases
# Extract and copy gitleaks.exe to backend\venv\Scripts\ (or add to your PATH)
```

### Frontend

```powershell
cd frontend
npm install
```

### Configure environment

```powershell
copy .env.example .env      # then edit .env and fill in real values
```

Required keys (see `.env.example` for descriptions):
- `GROQ_API_KEY` — Groq API key for LLM triage/explanation
- `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY_PATH`, `GITHUB_APP_CLIENT_ID`, `GITHUB_APP_CLIENT_SECRET` — GitHub App credentials
- `SESSION_SECRET` — dashboard session signing key
- `TOKEN_ENCRYPTION_KEY` — stable Fernet key for encrypted user credentials
- `GITHUB_WEBHOOK_SECRET` — shared HMAC secret for webhook verification
- `DATABASE_URL` — PostgreSQL connection string
- `CHROMA_PERSIST_DIR` — path for ChromaDB vector store persistence
- `CORS_ALLOWED_ORIGINS` — browser origins for the dashboard (default: localhost:5173)

The frontend uses `frontend/.env` with `VITE_API_BASE_URL` (defaults to
`http://127.0.0.1:8080`). This is the single source of truth for the backend
URL — change it here if the backend runs on a different port.

## Run the backend (venv active)

Apply migrations and initialize default standards first:

```powershell
python -m backend.bootstrap
```

Generate a Fernet key once with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
and save it as `TOKEN_ENCRYPTION_KEY` in your local `.env`. Keep that key stable;
changing it makes existing encrypted GitHub credentials unreadable. Existing users
must sign in again after upgrading from the old token-free schema.

```powershell
uvicorn backend.main:app --host 127.0.0.1 --port 8080 --reload
```

In a second terminal, activate the same venv and run the durable worker:

```powershell
backend\venv\Scripts\Activate.ps1
(Get-Command python).Source
python -m backend.worker
```

The API only queues reviews. A worker is required for analysis and delivery retries.
See [backend reliability and verification](docs/BACKEND_RELIABILITY.md) for the
updated flow, compatibility changes, and validation commands.
- Liveness:  `GET http://localhost:8080/health/live`
- Readiness: `GET http://localhost:8080/health/ready`
- Webhook:   `POST http://localhost:8080/webhooks/github`
- Interactive docs: `http://localhost:8080/docs`

## Run the frontend

```powershell
cd frontend
npm run dev
```
Opens at `http://localhost:5173`. Pages: review history, review detail (findings +
agent status + auto-fix panel), and code-health trends.

## Run the full stack (Docker Compose)

```bash
docker compose up --build
```
Starts `postgres`, a one-shot `migrate` initializer, `backend` (port 8000), and
`worker`. API and worker share a persistent Chroma volume. Chroma runs embedded;
there is no separate Chroma server. Mount the GitHub App private key using
`GITHUB_APP_PRIVATE_KEY_PATH`. The backend image bundles the three scanners.

## Run tests

```powershell
# Backend
pytest backend/tests

# Real PostgreSQL migration and worker checks, using disposable schemas
$env:CODEGUARDIAN_TEST_POSTGRES="1"
pytest backend/tests -o addopts= --tb=short

# Installed scanners and read-only external integration diagnostics
python -m scripts.verify_backend_runtime --github --llm

# Frontend
cd frontend && npm test
```

## Ingest coding standards (for the Quality Agent)

The Quality Agent uses RAG over your team's coding standards. To ingest:

```powershell
python -m backend.rag.ingest
```

The default standards document is `backend/rag/standards/python_coding_standards.md`.
Replace or extend it with your own standards, then re-run ingest.

## Trigger a review manually

Either configure a GitHub webhook pointing at `/webhooks/github`, or use the E2E
scripts to simulate one:

```powershell
python scripts/create_e2e_test_repo.py      # creates a test PR with planted issues
python scripts/e2e/step3_4_trigger_and_poll.py  # fires the webhook and waits
```

## Security note

The `POST /webhooks/github` endpoint authenticates requests via GitHub's
`X-Hub-Signature-256` HMAC signature (validated against `GITHUB_WEBHOOK_SECRET`). It has
no other authentication or network access controls. The provided `docker-compose.yml`
is intended for **local development only** — do not expose these services to the public
internet without adding proper authentication, TLS, and network hardening.

The auto-fix branch never merges automatically — explicit human approval is mandatory.
