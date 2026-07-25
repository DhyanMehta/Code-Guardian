"""add autofix fields and partial unique index

Revision ID: b7f2a1e3d456
Revises: ca09c608d315
Create Date: 2026-07-26 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7f2a1e3d456'
down_revision: Union[str, Sequence[str], None] = 'ca09c608d315'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add auto-fix gate columns to reviews
    op.add_column('reviews', sa.Column('is_fork', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('reviews', sa.Column('autofix_status', sa.String(length=32), nullable=True))
    op.add_column('reviews', sa.Column('autofix_branch', sa.String(length=255), nullable=True))
    op.add_column('reviews', sa.Column('autofix_approved_by', sa.String(length=255), nullable=True))
    op.add_column('reviews', sa.Column('autofix_approved_at', sa.DateTime(timezone=True), nullable=True))

    # Add fix_data column to findings
    op.add_column('findings', sa.Column('fix_data', sa.Text(), nullable=True))

    # Partial unique index: only one review in 'running' state per PR
    op.create_index(
        'uq_one_running_review_per_pr',
        'reviews',
        ['repo_full_name', 'pr_number'],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_one_running_review_per_pr', table_name='reviews')
    op.drop_column('findings', 'fix_data')
    op.drop_column('reviews', 'autofix_approved_at')
    op.drop_column('reviews', 'autofix_approved_by')
    op.drop_column('reviews', 'autofix_branch')
    op.drop_column('reviews', 'autofix_status')
    op.drop_column('reviews', 'is_fork')
