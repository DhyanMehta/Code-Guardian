"""A recorder with independent, serialized sessions for parallel graph nodes."""
from threading import Lock
from sqlalchemy.orm import Session
from backend.db.models import ReviewProgress

def recorder(bind, review_id: int, attempt: int):
    lock = Lock()
    def record(stage: str, status: str, agent: str | None = None):
        with lock, Session(bind=bind) as session:
            session.add(ReviewProgress(review_id=review_id, attempt=attempt,
                stage=stage, status=status, agent=agent))
            session.commit()
    return record
