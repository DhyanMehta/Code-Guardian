"""Shared review policy, applied atomically to all administered installations."""
import hashlib
import json
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.api.auth import get_current_user
from backend.db.database import get_db
from backend.db.models import Installation, User, UserInstallation
from backend.services.authorization import require_manager

router = APIRouter(prefix="/profile", tags=["profile"])

def managed(db, user, lock=False):
    query = db.query(Installation).join(UserInstallation).filter(
        UserInstallation.user_id == user.id, UserInstallation.role == "admin",
        Installation.uninstalled_at.is_(None), Installation.suspended_at.is_(None))
    if lock:
        query = query.with_for_update(of=Installation)
    return query.order_by(Installation.id).populate_existing().all()

def payload(rows):
    items = [{"id": i.id, "account_login": i.account_login, "review_mode": i.review_mode} for i in rows]
    modes = {i.review_mode for i in rows}
    return {"installations": items, "review_mode": next(iter(modes)) if len(modes) == 1 else "mixed" if modes else None,
        "version": hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()}

@router.get("/review-mode")
def get_review_mode(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return payload(managed(db, current_user))

class ModeUpdate(BaseModel):
    review_mode: Literal["auto", "manual"]
    version: str

@router.patch("/review-mode")
def update_review_mode(body: ModeUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = managed(db, current_user)
    if not rows:
        raise HTTPException(403, "No active administered installations.")
    # Credential refresh can commit; complete all remote authorization before
    # locking or mutating policy rows so the batch cannot partially commit.
    for row in rows:
        require_manager(current_user, row)
    rows = managed(db, current_user, lock=True)
    if payload(rows)["version"] != body.version:
        raise HTTPException(409, "Installation scope or review mode changed. Refresh before applying again.")
    for row in rows:
        row.review_mode = body.review_mode
    db.commit()
    return payload(rows)
