"""add review_agent_runs, completed_at, and durable autofix outcome fields

Session 6 (dashboard). Per-agent outcomes previously existed only in LangGraph
state and were discarded when a run finished, which made honest agent status
unreportable after the fact. The auto-fix applied/skipped detail had the same
problem: it was returned once by the create endpoint and never stored.

All added columns are nullable and the new table is additive, so existing rows are
untouched.

Revision ID: c3d9e1f2a7b8
Revises: b7f2a1e3d456
Create Date: 2026-07-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d9e1f2a7b8'
down_revision: Union[str, Sequence[str], None] = 'b7f2a1e3d456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Terminal-state timestamp. Nullable: pre-existing rows have no value, and a
    # crashed run legitimately never gets one.
    op.add_column(
        'reviews',
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Durable auto-fix outcome detail.
    op.add_column(
        'reviews',
        sa.Column('autofix_applied_count', sa.Integer(), nullable=True),
    )
    op.add_column(
        'reviews',
        sa.Column('autofix_skipped_fixes', sa.Text(), nullable=True),
    )

    # Per-agent run records.
    op.create_table(
        'review_agent_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('review_id', sa.Integer(), nullable=False),
        sa.Column('agent', sa.String(length=32), nullable=False),
        sa.Column('outcome', sa.String(length=16), nullable=False),
        sa.Column('finding_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['review_id'], ['reviews.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('review_id', 'agent', name='uq_agent_run_per_review'),
    )
    op.create_index(
        'ix_review_agent_runs_review_id', 'review_agent_runs', ['review_id']
    )
    op.create_index('ix_review_agent_runs_agent', 'review_agent_runs', ['agent'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_review_agent_runs_agent', table_name='review_agent_runs')
    op.drop_index('ix_review_agent_runs_review_id', table_name='review_agent_runs')
    op.drop_table('review_agent_runs')
    op.drop_column('reviews', 'autofix_skipped_fixes')
    op.drop_column('reviews', 'autofix_applied_count')
    op.drop_column('reviews', 'completed_at')
