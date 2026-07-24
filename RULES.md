# CodeGuardian AI — Hard Rules for AI Coding Agents

These rules are binding for **every** session in this repository, including all future
implementation sessions. Read this file before doing any work.

## Environment
1. A Python virtual environment lives at `./venv`. **ALWAYS activate it before running
   ANY Python-related command** — installing dependencies, running FastAPI, running
   scanners (Semgrep / Bandit / Gitleaks), and running tests.
   - Windows PowerShell: `venv\Scripts\Activate.ps1`
   - Windows cmd: `venv\Scripts\activate.bat`
   - Linux/macOS / inside Docker: `source venv/bin/activate`
2. Before running any Python command, **CONFIRM the venv is active** (verify `where python`
   / `which python` resolves inside `...\Code-Guardian\venv`). If it is not active, activate
   it first — do not run the command against a global interpreter.
3. **NEVER install Python packages globally.** All installs go into `./venv`.
4. **Pin dependency versions** in `backend/requirements.txt`. No unpinned or open ranges.

## Correctness & Integrity
5. **LLM output is NEVER treated as a security or quality finding by itself.** The LLM
   only explains, triages, and prioritizes deterministic tool output.
6. **No mock, placeholder, or fabricated data disguised as real results.** If a step is
   stubbed, label it clearly as a stub.
7. **No invented library APIs.** Verify every API call against the installed package
   version before using it (this is why versions are pinned).
8. **Ask before assuming any unstated requirement.** Do not silently expand scope.

## Reliability
9. **Every external call** (LLM / Groq, scanners, GitHub API, database) **MUST have
   explicit error handling.** No silent failures; surface and log errors with context.
10. **Timeouts and retries** are required for all network calls (LLM, GitHub).

## Safety
11. **Secrets only via environment variables.** Never hardcode or commit secrets.
    `.env` is git-ignored; `.env.example` documents the required keys with empty values.
12. **The auto-fix branch NEVER merges automatically** — explicit human approval is mandatory.
13. **Do not push to `main`/`master` directly.** Use feature branches and pull requests.
