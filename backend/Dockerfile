# CodeGuardian AI backend image.
# Build context is the PROJECT ROOT (see docker-compose.yml) so the `backend`
# package is importable as `backend.main:app`.

FROM python:3.11-slim

# System deps: git (repo ops), curl (fetch Gitleaks), libpq for psycopg2 at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates libpq5 \
    && rm -rf /var/lib/apt/lists/*

# --- Gitleaks binary (deterministic secret scanner used by the Security Agent) ---
ARG GITLEAKS_VERSION=8.18.4
RUN curl -sSL \
      "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" \
      -o /tmp/gitleaks.tar.gz \
    && tar -xzf /tmp/gitleaks.tar.gz -C /usr/local/bin gitleaks \
    && rm /tmp/gitleaks.tar.gz \
    && gitleaks version

WORKDIR /app

RUN python -m venv /app/backend/venv
ENV VIRTUAL_ENV=/app/backend/venv
ENV PATH="/app/backend/venv/bin:$PATH"

# Install Python deps first for better layer caching. Semgrep + Bandit come from
# requirements.txt (pinned).
COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy the application code.
COPY backend /app/backend
COPY alembic.ini /app/alembic.ini

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
