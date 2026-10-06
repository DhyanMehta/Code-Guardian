"""Regression checks for authorization, evidence, queueing and safe fixes."""
import ast
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.agents._diff_utils import parse_diff_hunks
from backend.agents._validation import safe_workspace_path, find_function, validate_drafted_test
from backend.agents.quality_agent import QualityAgent
from backend.agents.security_agent import SecurityAgent
from backend.agents.state import AgentOutcome, SecurityAgentResult
from backend.db.models import Installation, Review, User
from backend.services import authorization
from backend.services.review_service import create_review, run_review, deliver_report
from backend.tests.conftest import _TestSessionLocal, create_test_auth_env, make_auth_cookies
from backend.tests.test_api.test_webhooks import _sign
from backend.tools.results import RawFinding, Severity


@pytest.mark.parametrize("docstring, expected", [
    ("Calculate delay.\n\nArgs:\n    attempt (int): Attempt index.\n\nReturns:\n    float: Delay in seconds.\n\nRaises:\n    ValueError: Invalid attempt.", {"attempt"}),
    ("Calculate delay.\n\nParameters\n----------\nx, y : int\n    Inputs.\nReturns\n-------\nfloat : result\n    Delay.", {"x", "y"}),
    ("Compute.\n:param int attempt: Attempt index.\n:param **kwargs: Options.\n:returns: Delay.", {"attempt", "kwargs"}),
])
def test_docstring_parameters_exclude_return_types(docstring, expected):
    from backend.agents._validation import extract_documented_params
    assert extract_documented_params(docstring) == expected


def test_constructor_draft_calls_class_instead_of_dunder_init(tmp_path):
    from backend.agents.test_gap_agent import TestGapAgent
    (tmp_path / "app.py").write_text("class Config:\n    def __init__(self, value):\n        self.value = value\n")
    code = "from app import Config\n\ndef test_config():\n    assert Config(1).value == 1\n"
    gap = SimpleNamespace(function=SimpleNamespace(name="__init__", class_name="Config", file_path="app.py"))
    draft = TestGapAgent()._validate_drafted_test(json.dumps({"test_code": code}), gap, str(tmp_path))
    assert draft is not None
    assert draft.target_function == "Config.__init__"
    assert not validate_drafted_test("Config.__init__", "app.py", "def test_other():\n    Other(1)\n", str(tmp_path))[0]


def test_encrypted_credentials_and_invalid_key(monkeypatch):
    token = authorization.encrypt_token("synthetic-github-token")
    assert "synthetic-github-token" not in token
    assert authorization.decrypt_token(token) == "synthetic-github-token"
    with pytest.raises(HTTPException) as error:
        authorization.decrypt_token("corrupt")
    assert error.value.status_code == 503


def test_expired_credentials_refresh_and_persist(monkeypatch):
    settings = authorization.get_settings()
    monkeypatch.setattr(settings, "github_app_client_id", "test-client")
    monkeypatch.setattr(settings, "github_app_client_secret", "test-secret")
    with _TestSessionLocal() as db:
        user = User(github_user_id=77, github_login="refresh")
        authorization.store_tokens(user, {"access_token": "old", "refresh_token": "refresh", "expires_in": -100})
        db.add(user)
        db.commit()
        response = MagicMock()
        response.json.return_value = {"access_token": "new", "refresh_token": "rotated", "expires_in": 3600}
        with patch.object(authorization.httpx, "Client") as client:
            client.return_value.__enter__.return_value.post.return_value = response
            assert authorization.user_token(user) == "new"
        db.refresh(user)
        assert authorization.decrypt_token(user.refresh_token_enc) == "rotated"


def test_repo_read_and_write_are_separate(monkeypatch):
    with _TestSessionLocal() as db:
        user, inst = create_test_auth_env(db)
        monkeypatch.setattr(authorization, "user_token", lambda _: "synthetic")
        monkeypatch.setattr(authorization, "accessible_repos", lambda *_: [{"full_name": "owner/repo"}])
        monkeypatch.setattr(authorization, "github_json", lambda *_: {"permissions": {"pull": True}})
        authorization.require_repo(user, inst.id, "owner/repo")
        with pytest.raises(HTTPException) as error:
            authorization.require_repo(user, inst.id, "owner/repo", write=True)
        assert error.value.status_code == 403
        with pytest.raises(HTTPException):
            authorization.require_repo(user, inst.id, "owner/private")


def test_github_pagination_and_organization_role(monkeypatch):
    calls = []
    def response(token, path, *, params=None):
        calls.append(params["page"])
        return {"repositories": [{"full_name": str(i)} for i in range(100 if params["page"] == 1 else 1)]}
    monkeypatch.setattr(authorization, "github_json", response)
    assert len(authorization.github_pages("synthetic", "/user/installations/1/repositories", "repositories")) == 101
    assert calls == [1, 2]
    monkeypatch.setattr(authorization, "github_json", lambda *_: {"state": "active", "role": "member"})
    assert not authorization.is_manager("t", "user", "org", "Organization")
    assert not authorization.is_manager("t", "collaborator", "owner", "User")


def test_logout_revokes_old_cookie(client):
    with _TestSessionLocal() as db:
        create_test_auth_env(db)
    cookies = make_auth_cookies()
    assert client.get("/auth/me", cookies=cookies).status_code == 200
    assert client.post("/auth/logout", cookies=cookies).status_code == 200
    assert client.get("/auth/me", cookies=cookies).status_code == 401


@pytest.mark.parametrize("method", ["PATCH", "DELETE"])
def test_cors_supports_frontend_mutations(client, method):
    response = client.options("/installations/1/standards", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": method})
    assert response.status_code == 200
    assert method in response.headers["access-control-allow-methods"]


def test_cross_origin_mutation_denied(client):
    assert client.post("/auth/logout", headers={"Origin": "https://untrusted.invalid"}).status_code == 403
    assert client.post("/auth/logout", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403


@pytest.mark.parametrize("bad", [[], {"repository": []}, {"pull_request": {"head": []}}, {"installation": {"id": "bad"}}])
def test_invalid_signed_webhook_is_400(client, bad):
    body = json.dumps(bad).encode()
    assert client.post("/webhooks/github", content=body, headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": _sign(body)}).status_code == 400


def test_delivery_dedup_and_null_fork_repository(client):
    body = json.dumps({"action": "opened", "repository": {"full_name": "owner/repo"}, "pull_request": {"number": 1, "head": {"sha": "abc123", "repo": None}}, "installation": {"id": 700}}).encode()
    headers = {"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": _sign(body), "X-GitHub-Delivery": "delivery-unique"}
    first = client.post("/webhooks/github", content=body, headers=headers)
    second = client.post("/webhooks/github", content=body, headers=headers)
    assert first.status_code == second.status_code == 202
    assert first.json()["review_id"] == second.json()["review_id"]
    with _TestSessionLocal() as db:
        assert db.query(Review).count() == 1
        assert db.query(Review).one().status == "pending"


def test_token_failure_finishes_review():
    with _TestSessionLocal() as db:
        review = create_review(db, repo_full_name="owner/repo", pr_number=1, head_sha="abc", installation_id=1)
        with patch("backend.tools.github_app.get_installation_token", side_effect=RuntimeError("unavailable")):
            run_review(db, review.id)
        db.refresh(review)
        assert review.status == "failed"
        assert review.completed_at and review.started_at


def test_delivery_failure_preserves_completed_analysis():
    with _TestSessionLocal() as db:
        review = create_review(db, repo_full_name="owner/repo", pr_number=1, head_sha="abc")
        review.status = "completed"
        review.report_markdown = "immutable report"
        db.commit()
        with patch("backend.services.review_service._post_pr_comment", side_effect=RuntimeError("network")):
            deliver_report(db, review)
        assert review.status == "completed"
        assert review.delivery_status == "failed"
        assert review.report_markdown == "immutable report"
        with patch("backend.services.review_service._post_pr_comment"):
            deliver_report(db, review)
        assert review.delivery_status == "posted"
        assert review.delivery_attempts == 2


def test_exact_changed_lines_exclude_context():
    diff = '--- a/a.py\n+++ b/a.py\n@@ -1,3 +1,3 @@\n def unchanged():\n-    return 1\n+    return 2\n def other():\n'
    assert parse_diff_hunks(diff) == {"a.py": [(2, 2)]}


def test_omitted_security_triage_is_visible():
    raw = RawFinding("bandit", "B101", "assert", Severity.LOW, "a.py", 1)
    llm = MagicMock()
    llm.complete.return_value = '{"findings": []}'
    result = SecurityAgentResult(raw_findings=[raw])
    SecurityAgent(llm_client=llm)._triage(result)
    assert result.outcome is AgentOutcome.DEGRADED
    assert result.raw_findings == [raw]
    assert not result.triaged_findings


def test_safe_paths_and_qualified_function_identity(tmp_path):
    with pytest.raises(ValueError):
        safe_workspace_path(str(tmp_path), "../outside.py")
    tree = ast.parse("class A:\n def run(self): pass\nclass B:\n def run(self): pass\n")
    assert find_function(tree, "run") is None
    assert find_function(tree, "B.run").lineno == 4
    (tmp_path / "a.py").write_text("def target(): return 1\n")
    valid, _ = validate_drafted_test("target", "a.py", "# target()\ndef test_x(): pass", str(tmp_path))
    assert not valid
    valid, _ = validate_drafted_test("target", "a.py", "def broken(: target()", str(tmp_path))
    assert not valid


def test_measurable_quality_rule_uses_cited_limit(tmp_path):
    path = tmp_path / "a.py"
    path.write_text('def f(a, b, *, c, d):\n    """Some documentation."""\n    return a + b\n')
    kind, _ = QualityAgent._verify_supported_rule({"rule_violated": "Parameter count"}, "Functions accept 2 or fewer positional parameters.", "f", str(path))
    assert kind == "contradicted"
    kind, text = QualityAgent._verify_supported_rule({"rule_violated": "Parameter count"}, "Functions accept 1 or fewer positional parameters.", "f", str(path))
    assert kind == "verified" and "2 positional" in text
    kind, _ = QualityAgent._verify_supported_rule({"rule_violated": "Design"}, "Prefer a clear design.", "f", str(path))
    assert kind == "advisory"


def test_invalid_replacement_preserves_active_standards(tmp_path):
    from backend.rag.ingest import ingest_custom, NoSourceDocumentsError
    from backend.rag.retriever import retrieve
    ingest_custom("## Tenant rule\nAlways validate the X-Tenant-Id header before processing requests.", 1, persist_dir=str(tmp_path), collection_name="immutable_version_one")
    with pytest.raises(NoSourceDocumentsError):
        ingest_custom("tiny", 1, persist_dir=str(tmp_path), collection_name="immutable_version_two")
    result = retrieve("validate tenant header", persist_dir=str(tmp_path), collection_name="immutable_version_one")
    assert result.has_context
    missing = retrieve("validate tenant header", persist_dir=str(tmp_path), collection_name="missing_explicit_version")
    assert not missing.has_context and missing.error


def test_large_diff_batches_keep_all_added_lines_and_offsets():
    from backend.agents._diff_utils import bounded_diff_batches
    added = [f"+value_{i} = {i}\n" for i in range(1000)]
    diff = "--- a/a.py\n+++ b/a.py\n@@ -0,0 +1,1000 @@\n" + "".join(added)
    batches = bounded_diff_batches(diff, 1000)
    assert len(batches) > 1
    assert all(len(batch) <= 1000 for batch in batches)
    seen = [line + "\n" for batch in batches for line in batch.splitlines() if line.startswith("+") and not line.startswith("+++")]
    assert seen == added
    ranges = [r for batch in batches for r in parse_diff_hunks(batch)["a.py"]]
    assert ranges[0][0] == 1 and ranges[-1][1] == 1000
    assert sum(end - start + 1 for start, end in ranges) == 1000


def test_token_reservations_reconcile_exact_attempt(monkeypatch):
    from backend.tools.llm_client import TokenBucketLimiter, LLMRateLimitError
    limiter = TokenBucketLimiter(tpm_limit=1000, safety_margin=1)
    with patch("backend.tools.llm_client.time.monotonic", side_effect=[1, 1, 1, 1.1, 1.1, 1.1]):
        limiter.acquire(100, reservation_id="one")
        limiter.acquire(100, reservation_id="two")
    limiter.reconcile("two", 100, 40)
    assert limiter._history == [(1, 100), (1.1, 40)]
    with pytest.raises(LLMRateLimitError):
        limiter.acquire(1001)


def test_one_line_docstring_fix_does_not_corrupt_code(tmp_path):
    from backend.services.autofix_service import _insert_docstring
    path = tmp_path / "a.py"
    source = "def f(): return 7\n"
    path.write_text(source)
    assert not _insert_docstring(str(path), "f", "Return seven.")
    assert path.read_text() == source
    ast.parse(path.read_text())


def test_interrupted_autofix_push_is_reconciled_without_reapplying():
    from backend.services.autofix_service import create_autofix
    with _TestSessionLocal() as db:
        user, inst = create_test_auth_env(db)
        review = create_review(db, repo_full_name="owner/repo", pr_number=1, head_sha="old", installation_id=inst.id)
        review.status = "completed"
        review.autofix_status = "failed"
        review.autofix_branch = "codeguardian/autofix/1"
        review.autofix_commit_sha = "prepared"
        review.autofix_applied_fixes = json.dumps([{"target_function": "f", "target_file": "a.py", "fix_type": "docstring"}])
        db.commit()
        with patch.object(authorization, "require_repo"), patch.object(authorization, "user_github") as github, patch("backend.services.autofix_service._apply_fixes_and_push") as apply:
            github.return_value.get_repo.return_value.get_branch.return_value.commit.sha = "prepared"
            result = create_autofix(db, review.id, user=user)
            apply.assert_not_called()
        assert review.autofix_status == "pending_approval"
        assert len(result.applied_fixes) == 1


def test_git_credentials_are_only_in_child_environment():
    from backend.tools.git_auth import git_auth, git_environment
    with git_auth("synthetic"):
        env = git_environment()
        assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
        assert env["GIT_CONFIG_VALUE_0"].startswith("Authorization: Basic ")
    assert git_environment().get("GIT_CONFIG_VALUE_0") != env["GIT_CONFIG_VALUE_0"]
