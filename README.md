# CodeGuardian AI

An autonomous multi-agent code review and DevSecOps platform. It reviews GitHub pull
requests using a Supervisor Agent (LangGraph) that coordinates four specialist agents —
Security, Quality, Test-Gap, and Documentation — then posts one severity-ranked report
as a PR comment and can open an auto-fix branch that requires explicit human approval.

See [`CONTEXT.md`](CONTEXT.md) for architecture, [`RULES.md`](RULES.md) for the binding
engineering rules, and [`ENDPOINTS.md`](ENDPOINTS.md) for the API contract.

> **Build phase:** Session 1 — scaffold, environment, Docker, FastAPI skeleton, and the
> GitHub webhook receiver. Agents / RAG / dashboard arrive in later sessions.

## Prerequisites
- Python 3.11+ (3.10+ supported)
- Docker + Docker Compose (for the full local stack)
- Git

## Standing environment rule
All Python work runs inside the project virtual environment at `backend/venv`. **Always
activate it before any Python command** and never install packages globally. See
`RULES.md`.

## Local setup (host)

```powershell
# From the project root
python -m venv backend\venv

# Activate (Windows PowerShell)
backend\venv\Scripts\Activate.ps1
# Windows cmd:            backend\venv\Scripts\activate.bat
# Linux/macOS/Docker:     source backend/venv/bin/activate

# Confirm the venv is active (should resolve inside ...\Code-Guardian\backend\venv)
where python        # PowerShell/cmd
python --version

# Install pinned dependencies (inside the venv only)
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

## Configure environment
```powershell
copy .env.example .env      # then edit .env and fill in real values
```
Required keys: `GROQ_API_KEY`, `GITHUB_TOKEN`, `GITHUB_WEBHOOK_SECRET`, `DATABASE_URL`,
`CHROMA_PERSIST_DIR`. `.env` is git-ignored and must never be committed.

## Run the API (host, venv active)
```powershell
uvicorn backend.main:app --reload
```
- Liveness:  `GET http://localhost:8000/health/live`
- Readiness: `GET http://localhost:8000/health/ready`
- Webhook:   `POST http://localhost:8000/webhooks/github`
- Interactive docs: `http://localhost:8000/docs`

## Run the full stack (Docker Compose)
```bash
docker compose up --build
```
Brings up three services: `backend` (FastAPI, port 8000), `postgres` (port 5432), and
`chromadb` (port 8001). The backend image bundles the Semgrep/Bandit Python tools and
the Gitleaks binary for later sessions.

## Run tests (venv active)
```powershell
pytest backend/tests
```

## Security note
The `POST /webhooks/github` endpoint authenticates requests via GitHub's
`X-Hub-Signature-256` HMAC signature (validated against `GITHUB_WEBHOOK_SECRET`). It has
**no other authentication or network access controls**. The provided `docker-compose.yml`
is intended for **local development only** — do not expose these services to the public
internet without adding proper authentication, TLS, and network hardening.
