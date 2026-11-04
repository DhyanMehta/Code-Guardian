"""Persist completed agent outputs for review recovery."""
import sqlalchemy as sa
from alembic import op

revision = "f638a1d2b490"
down_revision = "e23f45a67b89"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "review_agent_checkpoints",
        sa.Column("review_id", sa.Integer(), sa.ForeignKey("reviews.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("fingerprint", sa.String(64), primary_key=True),
        sa.Column("agent", sa.String(32), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False),
    )


def downgrade():
    op.drop_table("review_agent_checkpoints")
