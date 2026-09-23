@echo off
REM Launch the CodeGuardian backend with the venv ACTIVATED so that
REM bandit/semgrep resolve on PATH (bandit has no Docker fallback).
cd /d "%~dp0..\.."
call backend\venv\Scripts\activate.bat
echo [run_server] python: %VIRTUAL_ENV%
where bandit
where semgrep
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --log-level info
