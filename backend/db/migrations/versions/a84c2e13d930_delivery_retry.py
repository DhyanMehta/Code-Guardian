"""Schedule report delivery retries independently of analysis."""

from alembic import op
import sqlalchemy as sa

revision = "a84c2e13d930"
down_revision = "f638a1d2b490"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("reviews", sa.Column("delivery_retry_at", sa.DateTime(timezone=True)))
    op.execute(
        "UPDATE reviews SET delivery_retry_at = CURRENT_TIMESTAMP "
        "WHERE status = 'completed' AND delivery_status = 'failed' AND delivery_attempts < 3"
    )


def downgrade():
    op.drop_column("reviews", "delivery_retry_at")
