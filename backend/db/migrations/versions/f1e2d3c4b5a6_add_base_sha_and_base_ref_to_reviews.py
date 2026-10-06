"""add base_sha and base_ref to reviews

Revision ID: f1e2d3c4b5a6
Revises: 21e2df33e83d
Create Date: 2026-09-29 17:36:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1e2d3c4b5a6'
down_revision: Union[str, Sequence[str], None] = '21e2df33e83d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("reviews", sa.Column("base_sha", sa.String(length=64), nullable=True))
    op.add_column("reviews", sa.Column("base_ref", sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("reviews", "base_ref")
    op.drop_column("reviews", "base_sha")
