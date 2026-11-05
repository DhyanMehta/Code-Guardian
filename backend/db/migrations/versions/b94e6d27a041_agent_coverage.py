"""Persist structured agent coverage without backfilling historical claims."""
from alembic import op
import sqlalchemy as sa

revision = "b94e6d27a041"
down_revision = "a84c2e13d930"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("review_agent_runs", sa.Column("coverage", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("review_agent_runs", "coverage")
