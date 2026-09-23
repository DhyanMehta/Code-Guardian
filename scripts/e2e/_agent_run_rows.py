"""Read-only: show which reviews actually have persisted review_agent_runs rows.

Confirms whether the trends endpoint's coverage_complete=True for the legacy
reviews comes from "no rows at all" or from rows with a null outcome.
"""

from __future__ import annotations

from backend.db.database import get_sessionmaker
from backend.db.models import Review, ReviewAgentRun


def main() -> None:
    session = get_sessionmaker()()
    try:
        for review in session.query(Review).order_by(Review.id).all():
            rows = (
                session.query(ReviewAgentRun)
                .filter(ReviewAgentRun.review_id == review.id)
                .order_by(ReviewAgentRun.agent)
                .all()
            )
            pairs = [(row.agent, row.outcome) for row in rows]
            print(f"review {review.id:>3} {review.status:<10} rows={len(rows)} {pairs}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
