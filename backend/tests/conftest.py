"""Shared pytest fixtures for the backend test suite."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from backend.db.models import Base

# A deterministic secret used to sign test webhook payloads.
TEST_WEBHOOK_SECRET = "test-webhook-secret"

_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSessionLocal = sessionmaker(bind=_test_engine)


def _get_test_db():
    """Yield a test DB session (in-memory SQLite)."""
    session = _TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session", autouse=True)
def _configure_env(tmp_path_factory) -> None:
    """Set required environment before the app settings are first read."""
    os.environ["GITHUB_WEBHOOK_SECRET"] = TEST_WEBHOOK_SECRET
    os.environ["GITHUB_TOKEN"] = "fake-token-for-tests"
    os.environ["SESSION_SECRET"] = TEST_SESSION_SECRET
    from cryptography.fernet import Fernet
    os.environ["TOKEN_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    os.environ["LEGACY_PAT_ENABLED"] = "true"
    os.environ["CHROMA_PERSIST_DIR"] = str(tmp_path_factory.mktemp("standards"))
    os.environ["LLM_TPM_LIMIT"] = "1000000"
    # Disable LLM call pacing under test: the throttle exists to protect a real
    # provider's rate limit, and real-time sleeps would only slow the suite down.
    os.environ["LLM_MIN_CALL_INTERVAL_SECONDS"] = "0"

    from backend.config import get_settings

    get_settings.cache_clear()

    from backend.rag.ingest import ingest
    ingest()

    from backend.tools.llm_client import reset_throttle

    reset_throttle()


TEST_USER_ID = 1
TEST_USER_LOGIN = "testuser"
TEST_USER_GITHUB_ID = 99999
TEST_INSTALLATION_ID = 123456
TEST_SESSION_SECRET = "test-session-secret-for-tests-12345"


def make_auth_cookies(
    user_id: int = TEST_USER_ID,
    github_login: str = TEST_USER_LOGIN,
    secret: str = TEST_SESSION_SECRET,
) -> dict[str, str]:
    """Mint a session_jwt cookie for test callers."""
    import jwt

    token = jwt.encode(
        {"user_id": user_id, "github_login": github_login, "exp": 9999999999},
        secret,
        algorithm="HS256",
    )
    return {"session_jwt": token}


def create_test_auth_env(session: Session):
    """Seed test user, installation, and user_installation link."""
    from backend.db.models import Installation, User, UserInstallation

    user = session.query(User).filter_by(id=TEST_USER_ID).first()
    if not user:
        user = User(
            id=TEST_USER_ID,
            github_user_id=TEST_USER_GITHUB_ID,
            github_login=TEST_USER_LOGIN,
        )
        session.add(user)
        session.flush()

    inst = session.query(Installation).filter_by(id=TEST_INSTALLATION_ID).first()
    if not inst:
        inst = Installation(
            id=TEST_INSTALLATION_ID,
            account_login="owner",
            account_type="User",
            app_slug="codeguardian",
            target_type="selected",
        )
        session.add(inst)
        session.flush()

    link = session.query(UserInstallation).filter_by(
        user_id=user.id,
        installation_id=inst.id,
    ).first()
    if not link:
        link = UserInstallation(
            user_id=user.id,
            installation_id=inst.id,
            role="admin",
        )
        session.add(link)
        session.flush()
    session.commit()
    return user, inst


@pytest.fixture(autouse=True)
def _setup_test_db():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(_test_engine)
    yield
    Base.metadata.drop_all(_test_engine)


@pytest.fixture()
def client(monkeypatch) -> TestClient:
    """Return a TestClient bound to the FastAPI app with DB overridden."""
    from unittest.mock import patch

    from backend.db.database import get_db
    from backend.main import app

    app.dependency_overrides[get_db] = _get_test_db

    # Fake the external GitHub boundary, not the authorization decision. Dedicated
    # authorization tests exercise denial, refresh, revocation and encryption.
    def github_response(token, path, *, params=None):
        if path.startswith("/user/installations/"):
            return {"repositories": [
                {"id": i, "name": name.split("/")[1], "full_name": name, "default_branch": "master"}
                for i, name in enumerate(["owner/repo", "other/repo", "devuser/httpx"])
            ]}
        if path.startswith("/repos/"):
            return {"permissions": {"push": True}}
        return {"role": "admin", "state": "active"}
    monkeypatch.setattr("backend.services.authorization.user_token", lambda user: "fake-user-token")
    monkeypatch.setattr("backend.services.authorization.github_json", github_response)

    with patch("backend.db.database.get_sessionmaker", return_value=_TestSessionLocal):
        yield TestClient(app)

    app.dependency_overrides.clear()
