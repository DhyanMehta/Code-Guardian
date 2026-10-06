"""add review_mode to installations

Revision ID: adf3640e2779
Revises: d4e5f6a7b8c9
Create Date: 2026-09-29 02:59:47.905540

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'adf3640e2779'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "installations",
        sa.Column(
            "review_mode",
            sa.String(length=16),
            nullable=False,
            server_default="auto",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("installations", "review_mode")
