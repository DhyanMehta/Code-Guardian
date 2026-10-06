"""add standards fields to installations

Revision ID: 08efb9630e44
Revises: adf3640e2779
Create Date: 2026-09-29 03:04:38.303850

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '08efb9630e44'
down_revision: Union[str, Sequence[str], None] = 'adf3640e2779'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("installations", sa.Column("standards_filename", sa.String(length=255), nullable=True))
    op.add_column("installations", sa.Column("standards_uploaded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("installations", sa.Column("standards_chunks", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("installations", "standards_chunks")
    op.drop_column("installations", "standards_uploaded_at")
    op.drop_column("installations", "standards_filename")
