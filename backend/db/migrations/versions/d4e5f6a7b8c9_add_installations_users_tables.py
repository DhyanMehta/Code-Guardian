"""add installations, users, user_installations tables and reviews.installation_id

Session 8: GitHub App multi-tenant support.  Creates three new tables
(installations, users, user_installations) and adds a nullable FK from reviews
to installations so each review is scoped to the installation that triggered it.
Legacy reviews (pre-Session-8) keep installation_id = NULL.

Revision ID: d4e5f6a7b8c9
Revises: c8a4b6d2e910
Create Date: 2026-09-19 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c8a4b6d2e910"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- installations ---
    op.create_table(
        "installations",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("account_login", sa.String(length=255), nullable=False),
        sa.Column("account_type", sa.String(length=32), server_default="User", nullable=False),
        sa.Column("app_slug", sa.String(length=255), server_default="", nullable=False),
        sa.Column("target_type", sa.String(length=32), server_default="selected", nullable=False),
        sa.Column("permissions", sa.Text(), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uninstalled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_installations_account_login", "installations", ["account_login"])

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("github_user_id", sa.Integer(), nullable=False),
        sa.Column("github_login", sa.String(length=255), nullable=False),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_github_user_id", "users", ["github_user_id"], unique=True)
    op.create_index("ix_users_github_login", "users", ["github_login"])

    # --- user_installations ---
    op.create_table(
        "user_installations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("installation_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), server_default="member", nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["installation_id"], ["installations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "installation_id", name="uq_user_installation"),
    )
    op.create_index("ix_user_installations_user_id", "user_installations", ["user_id"])
    op.create_index("ix_user_installations_installation_id", "user_installations", ["installation_id"])

    # --- reviews.installation_id (nullable FK) ---
    op.add_column(
        "reviews",
        sa.Column("installation_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_reviews_installation_id",
        "reviews",
        "installations",
        ["installation_id"],
        ["id"],
    )
    op.create_index("ix_reviews_installation_id", "reviews", ["installation_id"])


def downgrade() -> None:
    op.drop_index("ix_reviews_installation_id", table_name="reviews")
    op.drop_constraint("fk_reviews_installation_id", "reviews", type_="foreignkey")
    op.drop_column("reviews", "installation_id")

    op.drop_index("ix_user_installations_installation_id", table_name="user_installations")
    op.drop_index("ix_user_installations_user_id", table_name="user_installations")
    op.drop_table("user_installations")

    op.drop_index("ix_users_github_login", table_name="users")
    op.drop_index("ix_users_github_user_id", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_installations_account_login", table_name="installations")
    op.drop_table("installations")
