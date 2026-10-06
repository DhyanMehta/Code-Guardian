"""add standards_content to installations

Revision ID: 21e2df33e83d
Revises: 08efb9630e44
Create Date: 2026-09-29 03:14:01.147364

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '21e2df33e83d'
down_revision: Union[str, Sequence[str], None] = '08efb9630e44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("installations", sa.Column("standards_content", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("installations", "standards_content")
