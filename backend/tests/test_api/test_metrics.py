"""Tests for GET /metrics/trends."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.agents.state import AgentOutcome
from backend.db.models import Finding, Review, ReviewAgentRun
from backend.services.metrics_service import SEVERITY_WEIGHTS
from backend.tests.conftest import (
    TEST_INSTALLATION_ID,
    _TestSessionLocal,
    create_test_auth_env,
    make_auth_cookies,
)


@pytest.fixture(autouse=True)
def _setup_auth(client):
    with _TestSessionLocal() as session:
        create_test_auth_env(session)
    client.cookies.set("session_jwt", make_auth_cookies()["session_jwt"])


def _review(session, *, pr, created, status="completed", **kwargs):
    review = Review(
        installation_id=kwargs.pop("installation_id", TEST_INSTALLATION_ID),
        repo_full_name=kwargs.pop("repo", "owner/repo"),
        pr_number=pr,
        commit_sha="c" * 40,
        status=status,
        created_at=created,
        **kwargs,
    )
    session.add(review)
    session.commit()
    return review


@pytest.fixture()
def seeded_history():
    """Three chronological reviews, the newest with a degraded agent."""
    session = _TestSessionLocal()
    now = datetime.now(timezone.utc)

    oldest = _review(session, pr=1, created=now - timedelta(days=10))
    session.add_all([
        Finding(review_id=oldest.id, agent="security", severity="critical", title="a"),
        Finding(review_id=oldest.id, agent="security", severity="high", title="b"),
    ])

    middle = _review(session, pr=2, created=now - timedelta(days=5),
                     autofix_status="approved")
    session.add(
        Finding(review_id=middle.id, agent="quality", severity="medium", title="c")
    )

    newest = _review(session, pr=3, created=now - timedelta(days=1))
    session.add(
        Finding(review_id=newest.id, agent="security", severity="low", title="d")
    )
    session.add_all([
        ReviewAgentRun(review_id=newest.id, agent="quality",
                       outcome=AgentOutcome.DEGRADED.value, finding_count=0,
                       failure_reason="ChromaDB unreachable"),
        ReviewAgentRun(review_id=newest.id, agent="security",
                       outcome=AgentOutcome.OK.value, finding_count=1),
    ])

    skipped = _review(session, pr=4, created=now - timedelta(hours=1),
                      status="skipped")
    session.commit()

    ids = {
        "oldest": oldest.id, "middle": middle.id,
        "newest": newest.id, "skipped": skipped.id,
    }
    session.close()
    return ids


class TestTrends:
    def test_points_are_chronological_oldest_first(self, client, seeded_history):
        points = client.get("/metrics/trends").json()["points"]

        ids = [p["review_id"] for p in points]
        assert ids == [
            seeded_history["oldest"], seeded_history["middle"],
            seeded_history["newest"], seeded_history["skipped"],
        ]

    def test_per_point_counts_and_weighted_index(self, client, seeded_history):
        points = {p["review_id"]: p for p in client.get("/metrics/trends").json()["points"]}
        oldest = points[seeded_history["oldest"]]

        assert oldest["total_findings"] == 2
        assert oldest["severity_counts"]["critical"] == 1
        assert oldest["severity_counts"]["high"] == 1
        expected = SEVERITY_WEIGHTS["critical"] + SEVERITY_WEIGHTS["high"]
        assert oldest["weighted_index"] == expected

    def test_degraded_agents_marked_so_a_gap_is_not_read_as_progress(
        self, client, seeded_history
    ):
        points = {p["review_id"]: p for p in client.get("/metrics/trends").json()["points"]}

        newest = points[seeded_history["newest"]]
        assert newest["degraded_agents"] == ["quality"]
        assert newest["coverage_complete"] is False

    def test_a_review_with_no_agent_runs_is_unknown_coverage_not_complete(
        self, client, seeded_history
    ):
        """Absence of a recorded gap is not evidence that every agent ran.

        The oldest fixture review has no ``review_agent_runs`` rows at all, which is
        the state of every review created before Session 6. Reporting it as
        ``coverage_complete`` would let the charts draw an unknown baseline as a
        verified one.
        """
        points = {p["review_id"]: p for p in client.get("/metrics/trends").json()["points"]}
        oldest = points[seeded_history["oldest"]]

        assert oldest["degraded_agents"] == []
        assert oldest["coverage_recorded"] is False
        assert oldest["coverage_complete"] is False
        assert sorted(oldest["unrecorded_agents"]) == [
            "documentation", "quality", "security", "test_gap",
        ]

    def test_partially_recorded_review_lists_only_the_missing_agents(
        self, client, seeded_history
    ):
        """The fixture's newest review persisted 2 of 4 agents."""
        points = {p["review_id"]: p for p in client.get("/metrics/trends").json()["points"]}
        newest = points[seeded_history["newest"]]

        assert sorted(newest["unrecorded_agents"]) == ["documentation", "test_gap"]
        assert newest["coverage_recorded"] is False

    def test_fully_recorded_clean_review_is_coverage_complete(self, client):
        """The only state that may be read as a trustworthy clean baseline."""
        session = _TestSessionLocal()
        review = _review(session, pr=9, created=datetime.now(timezone.utc))
        session.add_all([
            ReviewAgentRun(review_id=review.id, agent=agent,
                           outcome=AgentOutcome.OK.value, finding_count=0)
            for agent in ("security", "quality", "test_gap", "documentation")
        ])
        session.commit()
        session.close()

        point = client.get("/metrics/trends").json()["points"][0]

        assert point["degraded_agents"] == []
        assert point["unrecorded_agents"] == []
        assert point["coverage_recorded"] is True
        assert point["coverage_complete"] is True

    def test_unrecognized_outcome_counts_as_unrecorded_not_ok(self, client):
        """An outcome string we do not understand must not be coerced to 'ran cleanly'.

        ``outcome`` is a plain NOT NULL string column, so a value written by a
        different version of the code is storable. ``AgentOutcome.coerce`` falls back
        to OK, which would silently turn an unknown state into a clean one.
        """
        session = _TestSessionLocal()
        review = _review(session, pr=11, created=datetime.now(timezone.utc))
        session.add_all([
            ReviewAgentRun(review_id=review.id, agent=agent,
                           outcome=AgentOutcome.OK.value, finding_count=0)
            for agent in ("security", "quality", "test_gap")
        ])
        session.add(
            ReviewAgentRun(review_id=review.id, agent="documentation",
                           outcome="some_future_state", finding_count=0)
        )
        session.commit()
        session.close()

        point = client.get("/metrics/trends").json()["points"][0]

        assert point["unrecorded_agents"] == ["documentation"]
        assert point["coverage_recorded"] is False
        assert point["coverage_complete"] is False

    def test_totals_disclose_how_much_of_the_series_is_trustworthy(
        self, client, seeded_history
    ):
        totals = client.get("/metrics/trends").json()["totals"]

        # Of the four fixture reviews none has all four agents recorded.
        assert totals["coverage_recorded_reviews"] == 0
        assert totals["coverage_complete_reviews"] == 0
        assert totals["reviews_with_coverage_gap"] == 4

    def test_totals(self, client, seeded_history):
        totals = client.get("/metrics/trends").json()["totals"]

        assert totals["reviews"] == 4
        assert totals["completed"] == 3
        assert totals["skipped"] == 1
        assert totals["failed"] == 0
        assert totals["findings"] == 4
        assert totals["severity_counts"]["critical"] == 1
        assert totals["autofix"]["created"] == 1
        assert totals["autofix"]["approved"] == 1
        assert totals["autofix"]["rejected"] == 0

    def test_weights_are_returned_so_the_ui_can_disclose_them(self, client, seeded_history):
        totals = client.get("/metrics/trends").json()["totals"]
        assert totals["weights_used"] == SEVERITY_WEIGHTS

    def test_range_metadata(self, client, seeded_history):
        body = client.get("/metrics/trends").json()

        assert body["range"]["review_count"] == 4
        assert body["repos"] == ["owner/repo"]
        assert body["range"]["since"] == body["points"][0]["created_at"]
        assert body["range"]["until"] == body["points"][-1]["created_at"]

    def test_limit_keeps_the_most_recent_reviews(self, client, seeded_history):
        points = client.get("/metrics/trends", params={"limit": 2}).json()["points"]

        assert [p["review_id"] for p in points] == [
            seeded_history["newest"], seeded_history["skipped"]
        ]

    def test_days_filter(self, client, seeded_history):
        points = client.get("/metrics/trends", params={"days": 3}).json()["points"]

        assert [p["review_id"] for p in points] == [
            seeded_history["newest"], seeded_history["skipped"]
        ]

    def test_repo_filter_excludes_other_repos(self, client, seeded_history):
        body = client.get("/metrics/trends", params={"repo": "other/repo"}).json()

        assert body["points"] == []
        assert body["totals"]["reviews"] == 0
        assert body["range"]["review_count"] == 0

    def test_empty_database_is_not_an_error(self, client):
        body = client.get("/metrics/trends").json()

        assert body["points"] == []
        assert body["totals"]["findings"] == 0
        assert body["repos"] == []


class TestTrendsAuthAndIsolation:
    def test_trends_401_no_cookie(self, client):
        client.cookies.clear()
        resp = client.get("/metrics/trends")
        assert resp.status_code == 401

    def test_trends_401_garbage_cookie(self, client):
        resp = client.get("/metrics/trends", cookies={"session_jwt": "garbage-token"})
        assert resp.status_code == 401

    def test_trends_403_cross_installation(self, client):
        resp = client.get("/metrics/trends", params={"installation_id": 999999})
        assert resp.status_code == 403
        assert resp.json()["detail"] == "You do not have access to this installation."

    def test_trends_isolation_with_foreign_review_having_findings(self, client, seeded_history):
        # Seed a foreign review under installation_id=999999 with 5 findings
        with _TestSessionLocal() as session:
            foreign = Review(
                installation_id=999999,
                repo_full_name="foreign/repo",
                pr_number=88,
                commit_sha="f" * 40,
                status="completed",
                created_at=datetime.now(timezone.utc),
            )
            session.add(foreign)
            session.commit()
            foreign_id = foreign.id

            for i in range(5):
                session.add(Finding(
                    review_id=foreign_id,
                    agent="security",
                    severity="high",
                    title=f"foreign-finding-{i}",
                ))
            session.commit()

        try:
            # Query /metrics/trends without installation_id parameter as authenticated user
            resp = client.get("/metrics/trends")
            assert resp.status_code == 200
            data = resp.json()

            # Confirm foreign review is absent from points
            point_ids = [p["review_id"] for p in data["points"]]
            assert foreign_id not in point_ids
            assert "foreign/repo" not in data["repos"]

            # Confirm findings count in totals does not include the 5 foreign findings
            # seeded_history has 4 findings, foreign has 5
            assert data["totals"]["findings"] == 4
            assert data["totals"]["reviews"] == 4
        finally:
            with _TestSessionLocal() as session:
                session.query(Finding).filter(Finding.review_id == foreign_id).delete()
                r = session.get(Review, foreign_id)
                if r:
                    session.delete(r)
                session.commit()
