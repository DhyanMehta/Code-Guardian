"""Persist actual review execution progress."""
from alembic import op
import sqlalchemy as sa

revision = "e23f45a67b89"
down_revision = "a12b34c56d78"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("review_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("review_id", sa.Integer(), sa.ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("agent", sa.String(32), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_review_progress_review_id", "review_progress", ["review_id"])

def downgrade():
    op.drop_table("review_progress")
