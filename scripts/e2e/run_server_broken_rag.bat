@echo off
REM Issue C verification: run the backend with CHROMA_PERSIST_DIR pointed at an
REM empty directory, so the coding_standards collection does not exist and the
REM Quality Agent genuinely cannot run. Everything else is unchanged.
cd /d "%~dp0..\.."
call backend\venv\Scripts\activate.bat
set CHROMA_PERSIST_DIR=%TEMP%\cg_empty_chroma
if not exist "%CHROMA_PERSIST_DIR%" mkdir "%CHROMA_PERSIST_DIR%"
echo [broken-rag] CHROMA_PERSIST_DIR=%CHROMA_PERSIST_DIR%
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --log-level info
