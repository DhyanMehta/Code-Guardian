"""Isolated GitHub-boundary regressions for bot-authored durable delivery.

These clients are explicit in-memory fakes, never live GitHub publications.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.models import Base, Installation, Review, User, UserInstallation
from backend.services.review_service import StaleDeliveryError, _post_pr_comment, deliver_report


class FakePullRequest:
    def __init__(self):
        self.head = SimpleNamespace(sha="pinned-head")
        self.comments = []
        self.created_bodies = []
        self.fail_after_create = False

    def get_issue_comments(self):
        return list(self.comments)

    def create_issue_comment(self, body):
        self.created_bodies.append(body)
        comment = SimpleNamespace(
            id=1000 + len(self.comments), body=body,
            user=SimpleNamespace(login="codeguardian[bot]", type="Bot"),
        )
        self.comments.append(comment)
        if self.fail_after_create:
            self.fail_after_create = False
            raise TimeoutError("GitHub response was lost after publication")
        return comment


@pytest.fixture
def publication(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(id=1, github_user_id=101, github_login="reviewer")
        inst = Installation(id=123, account_login="owner", account_type="User", app_slug="codeguardian", target_type="selected")
        db.add_all([user, inst])
        db.flush()
        db.add(UserInstallation(user_id=user.id, installation_id=inst.id, role="admin"))
        review = Review(
            repo_full_name="owner/repo", pr_number=1, commit_sha="pinned-head",
            installation_id=inst.id, requested_by=user.id, status="completed",
            report_markdown="## Saved report", delivery_status="pending",
        )
        db.add(review)
        db.commit()
        pr = FakePullRequest()
        repo = SimpleNamespace(get_pull=Mock(return_value=pr))
        client = SimpleNamespace(get_repo=Mock(return_value=repo))
        app_client = Mock(return_value=client)
        authorize = Mock()
        user_client = Mock(side_effect=AssertionError("User identity must not publish"))
        legacy_client = Mock(side_effect=AssertionError("Legacy PAT must not publish"))
        monkeypatch.setattr("backend.tools.github_app.get_installation_github", app_client)
        monkeypatch.setattr("backend.services.authorization.require_repo", authorize)
        monkeypatch.setattr("backend.services.authorization.user_github", user_client)
        monkeypatch.setattr("github.Github", legacy_client)
        yield SimpleNamespace(
            db=db, user=user, inst=inst, review=review, pr=pr,
            client=client, app_client=app_client, authorize=authorize,
            user_client=user_client, legacy_client=legacy_client,
        )
    engine.dispose()


@pytest.mark.parametrize("manual", [True, False], ids=["manual", "automatic"])
def test_both_review_origins_publish_as_installation_bot(publication, manual):
    p = publication
    p.review.requested_by = p.user.id if manual else None
    p.db.commit()
    _post_pr_comment(p.review, p.review.report_markdown, installation_id=p.inst.id)
    assert len(p.pr.comments) == 1
    assert p.pr.comments[0].user.login == "codeguardian[bot]"
    assert p.review.comment_id == str(p.pr.comments[0].id)
    p.app_client.assert_called_once_with(p.inst.id)
    p.user_client.assert_not_called()
    p.legacy_client.assert_not_called()
    if manual:
        p.authorize.assert_called_once_with(p.user, p.inst.id, "owner/repo", write=True)
    else:
        p.authorize.assert_not_called()


def test_stored_installation_is_used_when_no_override_is_supplied(publication):
    p = publication
    _post_pr_comment(p.review, p.review.report_markdown)
    p.app_client.assert_called_once_with(p.inst.id)
    assert len(p.pr.comments) == 1


@pytest.mark.parametrize("state", ["missing", "uninstalled", "suspended", "mismatched", "missing-requester"])
def test_invalid_publication_context_fails_closed(publication, state):
    p = publication
    explicit = p.inst.id
    if state == "missing":
        p.review.installation_id = None
        explicit = None
    elif state == "uninstalled":
        p.inst.uninstalled_at = datetime.now(timezone.utc)
    elif state == "suspended":
        p.inst.suspended_at = datetime.now(timezone.utc)
    elif state == "mismatched":
        explicit = 999
    else:
        p.review.requested_by = 999
    p.db.commit()
    with pytest.raises(Exception):
        _post_pr_comment(p.review, p.review.report_markdown, installation_id=explicit)
    assert not p.pr.comments
    p.app_client.assert_not_called()
    p.user_client.assert_not_called()
    p.legacy_client.assert_not_called()


def test_requester_losing_write_access_blocks_bot_publication(publication):
    p = publication
    p.authorize.side_effect = HTTPException(403, "Repository write permission revoked")
    with pytest.raises(HTTPException) as failure:
        _post_pr_comment(p.review, p.review.report_markdown, installation_id=p.inst.id)
    assert failure.value.status_code == 403
    assert not p.pr.comments
    p.app_client.assert_not_called()
    p.user_client.assert_not_called()


@pytest.mark.parametrize("manual", [True, False])
def test_unavailable_installation_credentials_never_fall_back(publication, manual):
    p = publication
    p.review.requested_by = p.user.id if manual else None
    p.db.commit()
    p.app_client.side_effect = RuntimeError("Installation credentials unavailable")
    with pytest.raises(RuntimeError, match="Installation credentials unavailable"):
        _post_pr_comment(p.review, p.review.report_markdown, installation_id=p.inst.id)
    assert not p.pr.comments
    p.user_client.assert_not_called()
    p.legacy_client.assert_not_called()


def test_repository_removed_from_installation_cannot_publish(publication):
    p = publication
    p.review.requested_by = None
    p.db.commit()
    p.client.get_repo.side_effect = PermissionError("Repository is not accessible to this installation")
    with pytest.raises(PermissionError):
        _post_pr_comment(p.review, p.review.report_markdown, installation_id=p.inst.id)
    assert not p.pr.comments
    p.user_client.assert_not_called()
    p.legacy_client.assert_not_called()


def test_new_bot_comment_is_not_posted_on_a_changed_head(publication):
    p = publication
    p.review.requested_by = None
    p.db.commit()
    p.pr.head.sha = "new-head"
    with pytest.raises(StaleDeliveryError):
        _post_pr_comment(p.review, p.review.report_markdown, installation_id=p.inst.id)
    assert not p.pr.comments


def test_lost_post_response_reconciles_same_bot_comment_without_duplication(publication):
    p = publication
    p.review.requested_by = None
    p.db.commit()
    p.pr.fail_after_create = True
    deliver_report(p.db, p.review)
    assert p.review.delivery_status == "failed"
    assert p.review.delivery_attempts == 1
    assert len(p.pr.comments) == 1
    # A head move after successful publication must not prevent reconciliation.
    p.pr.head.sha = "new-head"
    deliver_report(p.db, p.review)
    assert p.review.delivery_status == "posted"
    assert p.review.delivery_attempts == 2
    assert p.review.comment_id == str(p.pr.comments[0].id)
    assert len(p.pr.created_bodies) == 1
    assert len(p.pr.comments) == 1


@pytest.mark.parametrize("conflict", ["changed-body", "duplicate-marker", "non-bot-author"])
def test_ambiguous_or_modified_review_marker_never_creates_another_comment(publication, conflict):
    p = publication
    p.review.requested_by = None
    p.db.commit()
    body = f"<!-- codeguardian-review:{p.review.id} -->\n{p.review.report_markdown}"
    existing = SimpleNamespace(id=1234, body=body, user=SimpleNamespace(login="codeguardian[bot]", type="Bot"))
    if conflict == "changed-body":
        existing.body += "\nAn external edit"
    elif conflict == "non-bot-author":
        existing.user = SimpleNamespace(login="reviewer", type="User")
    p.pr.comments.append(existing)
    if conflict == "duplicate-marker":
        p.pr.comments.append(SimpleNamespace(id=1235, body=body, user=existing.user))
    with pytest.raises(Exception):
        _post_pr_comment(p.review, p.review.report_markdown, installation_id=p.inst.id)
    assert not p.pr.created_bodies


def test_posted_delivery_is_a_database_and_github_noop(publication):
    p = publication
    p.review.delivery_status = "posted"
    p.review.delivery_attempts = 1
    p.review.comment_id = "already-posted"
    p.db.commit()
    deliver_report(p.db, p.review)
    assert p.review.delivery_status == "posted"
    assert p.review.delivery_attempts == 1
    assert p.review.comment_id == "already-posted"
    p.app_client.assert_not_called()
    p.user_client.assert_not_called()


@pytest.mark.parametrize("state", ["not-completed", "no-report"])
def test_unpersisted_or_unfinished_report_cannot_be_delivered(publication, state):
    p = publication
    if state == "not-completed":
        p.review.status = "running"
    else:
        p.review.report_markdown = None
    p.db.commit()
    deliver_report(p.db, p.review)
    assert not p.pr.comments
    assert p.review.delivery_attempts == 0
    p.app_client.assert_not_called()
