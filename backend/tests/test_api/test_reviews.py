"""Tests for the dashboard-facing reviews API.

Covers the Session 6 additions: the list envelope with severity/agent counts, the
pre-ranked detail payload, persisted agent-run reporting, and the report endpoint's
fidelity to the comment that was actually posted.
"""

from __future__ import annotations

import json

import pytest

from backend.agents.state import AgentOutcome
from backend.db.models import Finding, Review, ReviewAgentRun
from backend.tests.conftest import _TestSessionLocal


@pytest.fixture()
def seeded():
    """Two reviews: one with all agents OK, one where Quality could not run."""
    session = _TestSessionLocal()

    healthy = Review(
        repo_full_name="owner/repo",
        pr_number=1,
        commit_sha="a" * 40,
        status="completed",
        summary="4 findings.",
        is_fork=False,
        autofix_status="approved",
        autofix_branch="codeguardian/autofix/1",
        autofix_approved_by="DhyanMehta",
        autofix_applied_count=3,
        autofix_skipped_fixes=json.dumps([
            {"target": "pkg/app.py:process_data",
             "reason": "Import references non-existent module 'pkg'"}
        ]),
    )
    session.add(healthy)
    session.commit()

    session.add_all([
        Finding(review_id=healthy.id, agent="documentation", severity="low",
                title="Docstring incomplete: build_report", detail="",
                file_path="pkg/app.py", line=148),
        Finding(review_id=healthy.id, agent="security", severity="critical",
                title="hardcoded-key", detail="", file_path="pkg/app.py", line=11),
        Finding(review_id=healthy.id, agent="test_gap", severity="high",
                title="Untested: process_data", detail="",
                file_path="pkg/app.py", line=32,
                fix_data=json.dumps({"target_function": "process_data"})),
        Finding(review_id=healthy.id, agent="security", severity="high",
                title="sql-injection", detail="", file_path="pkg/app.py", line=21),
    ])
    session.add_all([
        ReviewAgentRun(review_id=healthy.id, agent="security",
                       outcome=AgentOutcome.OK.value, finding_count=2),
        ReviewAgentRun(review_id=healthy.id, agent="quality",
                       outcome=AgentOutcome.OK.value, finding_count=0),
        ReviewAgentRun(review_id=healthy.id, agent="test_gap",
                       outcome=AgentOutcome.OK.value, finding_count=1),
        ReviewAgentRun(review_id=healthy.id, agent="documentation",
                       outcome=AgentOutcome.OK.value, finding_count=1),
    ])

    degraded = Review(
        repo_full_name="owner/repo",
        pr_number=2,
        commit_sha="b" * 40,
        status="completed",
        summary="1 finding. 3/4 agents succeeded.",
    )
    session.add(degraded)
    session.commit()
    session.add(
        Finding(review_id=degraded.id, agent="security", severity="medium",
                title="B608", detail="", file_path="pkg/app.py", line=21)
    )
    session.add_all([
        ReviewAgentRun(review_id=degraded.id, agent="security",
                       outcome=AgentOutcome.OK.value, finding_count=1),
        ReviewAgentRun(
            review_id=degraded.id, agent="quality",
            outcome=AgentOutcome.DEGRADED.value, finding_count=0,
            failure_reason="No coding-standards context retrieved: collection missing",
            notes=json.dumps(["No relevant coding-standards passages retrieved."]),
        ),
        ReviewAgentRun(review_id=degraded.id, agent="test_gap",
                       outcome=AgentOutcome.OK.value, finding_count=0),
        ReviewAgentRun(review_id=degraded.id, agent="documentation",
                       outcome=AgentOutcome.OK.value, finding_count=0),
    ])
    session.commit()

    ids = {"healthy": healthy.id, "degraded": degraded.id}
    session.close()
    return ids


class TestListReviews:
    def test_returns_envelope_with_total(self, client, seeded):
        body = client.get("/reviews").json()

        assert set(body) == {"items", "total", "limit", "offset"}
        assert body["total"] == 2
        assert len(body["items"]) == 2

    def test_severity_counts_are_complete_and_sum_to_finding_count(self, client, seeded):
        items = {i["id"]: i for i in client.get("/reviews").json()["items"]}
        healthy = items[seeded["healthy"]]

        # Every severity key is present so the client never has to key-check.
        assert set(healthy["severity_counts"]) == {
            "critical", "high", "medium", "low", "info", "unknown"
        }
        assert healthy["severity_counts"]["critical"] == 1
        assert healthy["severity_counts"]["high"] == 2
        assert healthy["severity_counts"]["low"] == 1
        assert sum(healthy["severity_counts"].values()) == healthy["finding_count"] == 4

    def test_agent_counts_present_for_all_four_agents(self, client, seeded):
        items = {i["id"]: i for i in client.get("/reviews").json()["items"]}
        healthy = items[seeded["healthy"]]

        assert set(healthy["agent_counts"]) == {
            "security", "quality", "test_gap", "documentation"
        }
        assert healthy["agent_counts"]["security"] == 2
        assert healthy["agent_counts"]["quality"] == 0

    def test_list_exposes_autofix_and_degraded_agents(self, client, seeded):
        items = {i["id"]: i for i in client.get("/reviews").json()["items"]}

        assert items[seeded["healthy"]]["autofix_status"] == "approved"
        assert items[seeded["healthy"]]["degraded_agents"] == []
        assert items[seeded["degraded"]]["degraded_agents"] == ["quality"]

    def test_fixable_count(self, client, seeded):
        items = {i["id"]: i for i in client.get("/reviews").json()["items"]}
        assert items[seeded["healthy"]]["fixable_count"] == 1

    def test_pagination_and_repo_filter(self, client, seeded):
        body = client.get("/reviews", params={"limit": 1, "offset": 0}).json()
        assert body["total"] == 2
        assert len(body["items"]) == 1
        assert body["limit"] == 1

        none_match = client.get("/reviews", params={"repo": "other/repo"}).json()
        assert none_match["total"] == 0
        assert none_match["items"] == []


class TestReviewDetail:
    def test_findings_are_pre_ranked_by_severity_then_agent(self, client, seeded):
        body = client.get(f"/reviews/{seeded['healthy']}").json()
        ranked = body["findings"]

        assert [f["rank"] for f in ranked] == [1, 2, 3, 4]
        # critical first; then the two highs ordered security before test_gap
        # (report_builder's agent priority); then low.
        assert [f["severity"] for f in ranked] == ["critical", "high", "high", "low"]
        assert ranked[1]["agent"] == "security"
        assert ranked[2]["agent"] == "test_gap"

    def test_grouped_findings_carry_the_same_ranks(self, client, seeded):
        body = client.get(f"/reviews/{seeded['healthy']}").json()

        flat = {f["id"]: f["rank"] for f in body["findings"]}
        for items in body["findings_by_agent"].values():
            for finding in items:
                assert finding["rank"] == flat[finding["id"]]

    def test_detail_reports_persisted_agent_runs(self, client, seeded):
        body = client.get(f"/reviews/{seeded['degraded']}").json()
        runs = {r["agent"]: r for r in body["agent_runs"]}

        assert runs["quality"]["outcome"] == "degraded"
        assert runs["quality"]["recorded"] is True
        assert "collection missing" in runs["quality"]["failure_reason"]
        assert runs["quality"]["notes"]
        assert runs["security"]["outcome"] == "ok"
        # All four agents always appear, even the ones with no findings.
        assert set(runs) == {"security", "quality", "test_gap", "documentation"}

    def test_unrecorded_agent_runs_are_not_reported_as_ok(self, client):
        """A pre-Session-6 review has no agent-run rows; that is not 'fine'."""
        session = _TestSessionLocal()
        legacy = Review(repo_full_name="owner/repo", pr_number=9, status="completed")
        session.add(legacy)
        session.commit()
        legacy_id = legacy.id
        session.close()

        body = client.get(f"/reviews/{legacy_id}").json()

        for run in body["agent_runs"]:
            assert run["outcome"] is None
            assert run["recorded"] is False

    def test_autofix_detail_includes_persisted_skipped_fixes(self, client, seeded):
        body = client.get(f"/reviews/{seeded['healthy']}").json()

        assert body["autofix"]["status"] == "approved"
        assert body["autofix"]["applied_count"] == 3
        assert len(body["autofix"]["skipped_fixes"]) == 1
        assert "non-existent module" in body["autofix"]["skipped_fixes"][0]["reason"]

    def test_fixable_flag_and_count(self, client, seeded):
        body = client.get(f"/reviews/{seeded['healthy']}").json()

        assert body["fixable_count"] == 1
        fixable = [f for f in body["findings"] if f["fixable"]]
        assert len(fixable) == 1
        assert fixable[0]["fix_data"]["target_function"] == "process_data"

    def test_missing_review_returns_404(self, client):
        assert client.get("/reviews/4242").status_code == 404


class TestReviewReport:
    def test_report_shows_degraded_agent_not_a_clean_run(self, client, seeded):
        """Regression: statuses used to be rebuilt from which agents had findings.

        That dropped zero-finding agents entirely and defaulted the rest to OK, so a
        review where Quality could not run rendered as fully successful.
        """
        body = client.get(f"/reviews/{seeded['degraded']}/report").json()
        md = body["markdown"]

        quality_row = next(l for l in md.splitlines() if l.startswith("| Quality "))
        assert "\u26a0" in quality_row          # warning sign
        assert "\u2705" not in quality_row      # never a check mark
        assert "could not run" in quality_row
        assert "3/4 agents succeeded" in md
        assert "Incomplete review" in md

    def test_report_lists_every_agent_including_zero_finding_ones(self, client, seeded):
        md = client.get(f"/reviews/{seeded['healthy']}/report").json()["markdown"]

        for label in ("| Security ", "| Quality ", "| Test Gap ", "| Documentation "):
            assert label in md, f"{label!r} missing from Agent Status table"

    def test_report_numbering_matches_detail_ranks(self, client, seeded):
        detail = client.get(f"/reviews/{seeded['healthy']}").json()
        md = client.get(f"/reviews/{seeded['healthy']}/report").json()["markdown"]

        # The first ranked finding is row 1 in the comment's findings table.
        first = detail["findings"][0]
        assert f"| 1 | {first['agent'].replace('_', ' ').title()} |" in md

    def test_report_conflicts_while_running(self, client):
        session = _TestSessionLocal()
        running = Review(repo_full_name="owner/repo", pr_number=7, status="running")
        session.add(running)
        session.commit()
        running_id = running.id
        session.close()

        response = client.get(f"/reviews/{running_id}/report")
        assert response.status_code == 409
        assert "still in 'running' state" in response.json()["detail"]

    def test_report_for_a_skipped_review_does_not_say_to_come_back_later(self, client):
        """A skipped review is terminal: no report is coming, ever.

        The original message said the review was "still in 'skipped' state", which
        told the dashboard to render "not ready yet" for a review that will never
        produce a report.
        """
        session = _TestSessionLocal()
        skipped = Review(repo_full_name="owner/repo", pr_number=8, status="skipped")
        session.add(skipped)
        session.commit()
        skipped_id = skipped.id
        session.close()

        response = client.get(f"/reviews/{skipped_id}/report")

        assert response.status_code == 409
        detail = response.json()["detail"]
        assert "was skipped" in detail
        assert "still in" not in detail

    def test_report_missing_review_returns_404(self, client):
        assert client.get("/reviews/4242/report").status_code == 404


class TestScannerStatusFidelity:
    """The Security row's per-scanner detail must survive into a re-rendered report.

    Without persisted scanner statuses, a report rebuilt from the database matched
    the posted comment everywhere except "(semgrep OK, bandit OK, gitleaks OK)".
    """

    @pytest.fixture()
    def review_with_scanners(self):
        session = _TestSessionLocal()
        review = Review(
            repo_full_name="owner/repo",
            pr_number=11,
            commit_sha="d" * 40,
            status="completed",
            summary="1 finding.",
        )
        session.add(review)
        session.commit()
        session.add(
            Finding(review_id=review.id, agent="security", severity="high",
                    title="sql-injection", detail="", file_path="pkg/app.py", line=21)
        )
        session.add_all([
            ReviewAgentRun(
                review_id=review.id, agent="security",
                outcome=AgentOutcome.OK.value, finding_count=1,
                scanner_statuses=json.dumps([
                    {"scanner": "semgrep", "ok": True, "finding_count": 1,
                     "error": None, "error_type": None},
                    {"scanner": "bandit", "ok": True, "finding_count": 0,
                     "error": None, "error_type": None},
                    {"scanner": "gitleaks", "ok": False, "finding_count": 0,
                     "error": "boom", "error_type": "ScannerTimeoutError"},
                ]),
            ),
            ReviewAgentRun(review_id=review.id, agent="quality",
                           outcome=AgentOutcome.OK.value, finding_count=0),
            ReviewAgentRun(review_id=review.id, agent="test_gap",
                           outcome=AgentOutcome.OK.value, finding_count=0),
            ReviewAgentRun(review_id=review.id, agent="documentation",
                           outcome=AgentOutcome.OK.value, finding_count=0),
        ])
        session.commit()
        review_id = review.id
        session.close()
        return review_id

    def test_detail_exposes_scanner_statuses_and_rendered_info(
        self, client, review_with_scanners
    ):
        body = client.get(f"/reviews/{review_with_scanners}").json()
        security = next(r for r in body["agent_runs"] if r["agent"] == "security")

        assert len(security["scanner_statuses"]) == 3
        assert security["scanner_info"] == (
            "semgrep OK, bandit OK, gitleaks failed (ScannerTimeoutError)"
        )

    def test_report_reproduces_the_scanner_detail(self, client, review_with_scanners):
        md = client.get(f"/reviews/{review_with_scanners}/report").json()["markdown"]

        security_row = next(l for l in md.splitlines() if l.startswith("| Security "))
        assert "semgrep OK" in security_row
        assert "bandit OK" in security_row
        assert "gitleaks failed (ScannerTimeoutError)" in security_row

    def test_agents_without_scanners_have_no_scanner_info(
        self, client, review_with_scanners
    ):
        body = client.get(f"/reviews/{review_with_scanners}").json()
        quality = next(r for r in body["agent_runs"] if r["agent"] == "quality")

        assert quality["scanner_statuses"] == []
        assert quality["scanner_info"] is None
