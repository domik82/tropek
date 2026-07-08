"""change point transition and nullable pct.

Revision ID: 005
Revises: 004
Create Date: 2026-07-08 09:35:26.582376

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: str | Sequence[str] | None = '004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('change_points', sa.Column('transition', sa.Text(), nullable=True))
    op.alter_column(
        'change_points',
        'change_relative_pct',
        existing_type=sa.DOUBLE_PRECISION(precision=53),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'change_points',
        'change_relative_pct',
        existing_type=sa.DOUBLE_PRECISION(precision=53),
        nullable=False,
    )
    op.drop_column('change_points', 'transition')
