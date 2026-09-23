"""ORM models (SQLAlchemy 2.0 declarative).

Minimal schema for Session 1, extended in Session 5 with auto-fix gate fields and
the partial unique index for concurrent-review prevention, in Session 6 with
per-agent run records plus the auto-fix outcome detail the dashboard needs, and
in Session 8 with GitHub App installation/user tables and the reviews →
installations FK for multi-tenant scoping.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Review(Base):
    """A single review run triggered for a GitHub pull request."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_full_name: Mapped[str] = mapped_column(String(255), index=True)
    pr_number: Mapped[int] = mapped_column(Integer, index=True)
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_fork: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_utcnow
    )
    # Set when the run reaches a terminal state. Nullable because every row created
    # before Session 6 predates the column, and because a crashed run never gets one.
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Auto-fix gate fields
    autofix_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    autofix_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    autofix_approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    autofix_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Auto-fix outcome detail. The create-autofix response reported these once and
    # then lost them; the dashboard needs them to survive a page refresh, because
    # "which fixes were rejected at apply time, and why" is the evidence that the
    # anti-hallucination validation actually did something.
    autofix_applied_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    autofix_skipped_fixes: Mapped[str | None] = mapped_column(Text, nullable=True)
    """JSON array of ``{"target": ..., "reason": ...}`` objects."""

    # GitHub App installation that triggered this review.  Nullable because
    # reviews created before Session 8 predate installations (legacy PAT era).
    installation_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("installations.id"), nullable=True, index=True
    )

    installation: Mapped["Installation | None"] = relationship(
        back_populates="reviews",
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="review",
        cascade="all, delete-orphan",
    )
    agent_runs: Mapped[list["ReviewAgentRun"]] = relationship(
        back_populates="review",
        cascade="all, delete-orphan",
    )


class Finding(Base):
    """A single issue surfaced by one of the specialist agents during a review."""

    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[int] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE"), index=True
    )
    agent: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(512))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fix_data: Mapped[str | None] = mapped_column(Text, nullable=True)

    review: Mapped["Review"] = relationship(back_populates="findings")


class ReviewAgentRun(Base):
    """How one specialist agent fared during one review.

    Before Session 6 this lived only in LangGraph state and was discarded once the
    run finished, so nothing downstream could tell "ran and found nothing" apart
    from "could not run". A zero finding count is ambiguous on its own; ``outcome``
    is what disambiguates it, and it has to be persisted to be reportable.
    """

    __tablename__ = "review_agent_runs"
    __table_args__ = (
        UniqueConstraint("review_id", "agent", name="uq_agent_run_per_review"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[int] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE"), index=True
    )
    agent: Mapped[str] = mapped_column(String(32), index=True)
    outcome: Mapped[str] = mapped_column(String(16))
    """An :class:`backend.agents.state.AgentOutcome` value: ok | degraded | failed."""
    finding_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    """JSON array of the agent's own notes, including transparency notes such as
    how many fabricated findings were dropped."""
    scanner_statuses: Mapped[str | None] = mapped_column(Text, nullable=True)
    """JSON array of per-scanner outcomes (Security Agent only): which of Semgrep,
    Bandit, and Gitleaks ran and which failed. Needed so a re-rendered report can
    reproduce the posted comment exactly, and so the dashboard can say *which*
    scanner failed rather than only that the agent degraded."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_utcnow
    )

    review: Mapped["Review"] = relationship(back_populates="agent_runs")


# --------------------------------------------------------------------------- #
# GitHub App multi-tenant models (Session 8)
# --------------------------------------------------------------------------- #


class Installation(Base):
    """A GitHub App installation on a user account or organisation.

    ``id`` is **GitHub's** installation ID (e.g. 161715271), not an
    auto-increment — the webhook payload carries it directly, and using it as
    the PK avoids an extra mapping layer.
    """

    __tablename__ = "installations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    account_login: Mapped[str] = mapped_column(String(255), index=True)
    account_type: Mapped[str] = mapped_column(String(32), default="User")
    app_slug: Mapped[str] = mapped_column(String(255), default="")
    target_type: Mapped[str] = mapped_column(String(32), default="selected")
    """``selected`` or ``all`` — how the installer scoped repo access."""
    permissions: Mapped[str | None] = mapped_column(Text, nullable=True)
    """JSON snapshot of the granted permissions dict."""
    suspended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    uninstalled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_utcnow,
        onupdate=_utcnow,
    )

    reviews: Mapped[list["Review"]] = relationship(back_populates="installation")
    user_links: Mapped[list["UserInstallation"]] = relationship(
        back_populates="installation",
        cascade="all, delete-orphan",
    )


class User(Base):
    """A dashboard user identified via GitHub OAuth.

    OAuth tokens are used only during the login callback to identify the user
    and discover their installations.  They are NOT stored — only the GitHub
    user ID, login, avatar URL, and timestamps are persisted.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    github_user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    github_login: Mapped[str] = mapped_column(String(255), index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_utcnow
    )
    last_login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_utcnow,
    )

    installation_links: Mapped[list["UserInstallation"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserInstallation(Base):
    """Many-to-many link between users and installations.

    A user can have multiple installations (personal + org), and an
    installation can be visible to multiple users (org members).
    Refreshed on every OAuth login via ``GET /user/installations``.
    """

    __tablename__ = "user_installations"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "installation_id", name="uq_user_installation"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    installation_id: Mapped[int] = mapped_column(
        ForeignKey("installations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(32), default="member")
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_utcnow
    )

    user: Mapped["User"] = relationship(back_populates="installation_links")
    installation: Mapped["Installation"] = relationship(
        back_populates="user_links",
    )
