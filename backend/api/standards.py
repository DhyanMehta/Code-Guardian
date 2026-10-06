"""Coding Standards API (dashboard-facing).

Allows users to manage installation-level coding standards:
- ``POST /installations/{id}/standards``: Upload custom standards (.md, max 512 KB, admin only).
- ``GET /installations/{id}/standards``: Check standards status (member or admin).
- ``DELETE /installations/{id}/standards``: Reset to default standards (admin only).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.api.auth import get_current_user
from backend.api.installations import _verify_user_installation_access
from backend.db.database import get_db
from backend.db.models import User
from backend.rag.ingest import IngestError, delete_custom, ingest_custom, new_collection_name
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/installations", tags=["standards"])

MAX_STANDARDS_SIZE_BYTES = 512 * 1024  # 512 KB


@router.post("/{installation_id}/standards")
async def upload_installation_standards(
    installation_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Upload custom coding standards for an installation (.md only, max 512 KB). Requires admin role."""
    inst = _verify_user_installation_access(
        current_user, installation_id, db, required_role="admin"
    )

    filename = file.filename or ""
    if not filename.lower().endswith(".md"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Markdown (.md) files are supported for coding standards.",
        )

    content_bytes = await file.read(MAX_STANDARDS_SIZE_BYTES + 1)
    if len(content_bytes) > MAX_STANDARDS_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed limit of {MAX_STANDARDS_SIZE_BYTES // 1024} KB.",
        )

    try:
        content_str = content_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded file must be valid UTF-8 text: {exc}",
        ) from exc

    try:
        version = new_collection_name(installation_id)
        chunk_count = await run_in_threadpool(ingest_custom,
            content_str, installation_id, filename=filename, collection_name=version
        )
    except IngestError as exc:
        logger.warning(
            "Failed to ingest custom standards for installation %d: %s",
            installation_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process coding standards document: {exc}",
        ) from exc

    inst.standards_filename = filename
    inst.standards_uploaded_at = datetime.now(timezone.utc)
    inst.standards_chunks = chunk_count
    inst.standards_content = content_str
    inst.standards_version = version
    db.commit()
    db.refresh(inst)

    logger.info(
        "User %s uploaded custom standards '%s' (%d chunks) for installation %d.",
        current_user.github_login,
        filename,
        chunk_count,
        installation_id,
    )

    return {
        "installation_id": inst.id,
        "filename": inst.standards_filename,
        "chunks": inst.standards_chunks,
        "version": inst.standards_version,
        "uploaded_at": inst.standards_uploaded_at.isoformat() if inst.standards_uploaded_at else None,
    }


@router.get("/{installation_id}/standards")
def get_installation_standards(
    installation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get coding standards configuration for an installation."""
    inst = _verify_user_installation_access(current_user, installation_id, db)
    has_custom = inst.standards_chunks is not None and inst.standards_chunks > 0

    return {
        "installation_id": inst.id,
        "has_custom_standards": has_custom,
        "version": inst.standards_version,
        "filename": inst.standards_filename,
        "chunks": inst.standards_chunks,
        "uploaded_at": inst.standards_uploaded_at.isoformat() if inst.standards_uploaded_at else None,
    }


@router.delete("/{installation_id}/standards")
def delete_installation_standards(
    installation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Delete custom coding standards for an installation, reverting to default. Requires admin role."""
    inst = _verify_user_installation_access(
        current_user, installation_id, db, required_role="admin"
    )

    # Retain immutable collections referenced by earlier or running reviews.

    inst.standards_filename = None
    inst.standards_uploaded_at = None
    inst.standards_chunks = None
    inst.standards_content = None
    inst.standards_version = None
    db.commit()
    db.refresh(inst)

    logger.info(
        "User %s deleted custom standards for installation %d, reverting to default.",
        current_user.github_login,
        installation_id,
    )

    return {
        "status": "deleted",
        "installation_id": inst.id,
    }
