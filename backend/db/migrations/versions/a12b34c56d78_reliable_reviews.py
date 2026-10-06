"""Durable reviews, encrypted OAuth credentials, versioned standards and evidence."""
from alembic import op
import sqlalchemy as sa

revision = "a12b34c56d78"
down_revision = "f1e2d3c4b5a6"
branch_labels = None
depends_on = None

FIELDS = {
    "users": [("access_token_enc", sa.Text()), ("refresh_token_enc", sa.Text()),
              ("token_expires_at", sa.DateTime(timezone=True))],
    "installations": [("standards_version", sa.String(255))],
    "findings": [("evidence", sa.Text())],
    "review_agent_runs": [("raw_findings", sa.Text())],
    "reviews": [("delivery_id", sa.String(255)), ("started_at", sa.DateTime(timezone=True)),
                ("heartbeat_at", sa.DateTime(timezone=True)), ("standards_version", sa.String(255)),
                ("report_markdown", sa.Text()), ("delivery_status", sa.String(32)),
                ("delivery_error", sa.Text()), ("comment_id", sa.String(64)),
                ("requested_by", sa.Integer()), ("autofix_commit_sha", sa.String(64)),
                ("autofix_error", sa.Text()), ("autofix_applied_fixes", sa.Text())],
}

def upgrade():
    op.create_table("worker_heartbeat", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    for table, fields in FIELDS.items():
        for name, kind in fields:
            op.add_column(table, sa.Column(name, kind, nullable=True))
    for table, name in [("users", "session_version"), ("reviews", "attempt"), ("reviews", "delivery_attempts")]:
        op.add_column(table, sa.Column(name, sa.Integer(), nullable=False, server_default="0"))
    op.create_unique_constraint("uq_reviews_delivery_id", "reviews", ["delivery_id"])
    op.create_foreign_key("fk_reviews_requested_by", "reviews", "users", ["requested_by"], ["id"])
    op.execute("UPDATE installations SET standards_version = 'coding_standards_' || CAST(id AS VARCHAR) WHERE standards_chunks > 0")

def downgrade():
    op.drop_table("worker_heartbeat")
    op.drop_constraint("fk_reviews_requested_by", "reviews", type_="foreignkey")
    op.drop_constraint("uq_reviews_delivery_id", "reviews", type_="unique")
    for table, name in [("users", "session_version"), ("reviews", "attempt"), ("reviews", "delivery_attempts")]:
        op.drop_column(table, name)
    for table, fields in reversed(list(FIELDS.items())):
        for name, _ in reversed(fields):
            op.drop_column(table, name)
