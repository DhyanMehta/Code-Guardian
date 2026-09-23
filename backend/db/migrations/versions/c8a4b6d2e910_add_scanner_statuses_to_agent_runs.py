"""add scanner_statuses to review_agent_runs

Without this, a report re-rendered from the database was identical to the posted PR
comment except for the Security row's per-scanner detail — "(semgrep OK, bandit OK,
gitleaks OK)" — because the per-scanner outcomes were discarded with the rest of the
graph state. Verified by diffing the rendered markdown against the real comment body
fetched from GitHub.

Revision ID: c8a4b6d2e910
Revises: c3d9e1f2a7b8
Create Date: 2026-07-27 11:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8a4b6d2e910'
down_revision: Union[str, Sequence[str], None] = 'c3d9e1f2a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'review_agent_runs',
        sa.Column('scanner_statuses', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('review_agent_runs', 'scanner_statuses')
