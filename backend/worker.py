"""Single-host durable queue. Run separately: python -m backend.worker.

Each attempt runs in a disposable process with a hard deadline. A PostgreSQL
session advisory lock is owned by that process until it exits, preventing another
worker from recovering or running work while the previous execution is alive.
"""
import logging
import multiprocessing
import time
import os
import signal
import subprocess
import threading
from datetime import datetime, timezone
from sqlalchemy import text
from backend.config import get_settings

logger = logging.getLogger(__name__)
LOCK_ID = 73194201


def heartbeat(stop, review_id=None):
    from backend.db.database import get_sessionmaker
    from backend.db.models import WorkerHeartbeat, Review
    while not stop.is_set():
        try:
            with get_sessionmaker()() as db:
                now = datetime.now(timezone.utc)
                db.merge(WorkerHeartbeat(id=1, updated_at=now))
                if review_id:
                    db.query(Review).filter_by(id=review_id, status="running").update({"heartbeat_at": now})
                db.commit()
        except Exception:
            logger.exception("Worker heartbeat failed.")
        stop.wait(15)


def terminate_attempt(process):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=15)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.join(10)
    if process.is_alive():
        process.kill()
        process.join(5)


def run_next(did_review=None):
    # Spawned workers do not inherit the parent's logging configuration.
    logging.basicConfig(level=logging.INFO)
    if os.name != "nt" and multiprocessing.current_process().name != "MainProcess":
        os.setsid()
    from backend.db.database import get_engine, get_sessionmaker
    from backend.db.models import Review
    from backend.services.review_service import run_review, deliver_report
    engine = get_engine()
    with engine.connect() as lock_connection:
        if engine.dialect.name != "postgresql":
            raise RuntimeError("The durable worker requires PostgreSQL.")
        if not lock_connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_ID}).scalar():
            return
        try:
            with get_sessionmaker()() as db:
                from backend.db.models import WorkerHeartbeat
                db.merge(WorkerHeartbeat(id=1, updated_at=datetime.now(timezone.utc)))
                db.commit()
                # Lock ownership proves no earlier review process is still executing.
                for old in db.query(Review).filter_by(status="running").all():
                    old.status = "pending" if old.attempt < get_settings().max_review_attempts else "failed"
                    old.summary = "Previous worker stopped before completing the review."
                    if old.status == "failed":
                        old.completed_at = datetime.now(timezone.utc)
                db.commit()
                pending = db.query(Review).filter_by(status="pending", requested_by=None).order_by(Review.id.desc()).all()
                latest = set()
                for queued in pending:
                    key = (queued.installation_id, queued.repo_full_name, queued.pr_number)
                    if key in latest:
                        queued.status = "skipped"
                        queued.completed_at = datetime.now(timezone.utc)
                        queued.summary = "Superseded by a newer queued review of this PR."
                    latest.add(key)
                db.commit()
                review = db.query(Review).filter_by(status="pending").order_by(Review.id).first()
                if review:
                    if did_review is not None:
                        did_review.set()
                    stop = threading.Event()
                    pulse = threading.Thread(target=heartbeat, args=(stop, review.id), daemon=True)
                    pulse.start()
                    try:
                        run_review(db, review.id, installation_id=review.installation_id)
                    finally:
                        stop.set()
                        pulse.join(10)
                else:
                    review = db.query(Review).filter(Review.delivery_status.in_(["pending", "failed"]), Review.delivery_attempts < 3).order_by(Review.id).first()
                    if review:
                        deliver_report(db, review)
        finally:
            lock_connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_ID})


def main():
    logging.basicConfig(level=logging.INFO)
    ctx = multiprocessing.get_context("spawn")
    settings = get_settings()
    while True:
        did_review = ctx.Event()
        process = ctx.Process(target=run_next, args=(did_review,))
        process.start()
        try:
            process.join(settings.review_timeout_seconds)
            if process.is_alive():
                logger.error("Review deadline reached; terminating worker attempt.")
                terminate_attempt(process)
        except KeyboardInterrupt:
            terminate_attempt(process)
            return
        # Child processes have independent in-memory token windows. Let the prior
        # review's provider window expire before starting another one.
        time.sleep(max(settings.worker_poll_seconds, 60 if did_review.is_set() else 0))


if __name__ == "__main__":
    main()
