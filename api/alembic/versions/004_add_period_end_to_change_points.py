"""add period_end column to change_points.

Revision ID: 004
Revises: 003
Create Date: 2026-05-07 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '004'
down_revision: str | Sequence[str] | None = '003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'change_points',
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE change_points cp
        SET period_end = e.period_end
        FROM evaluations e
        WHERE cp.evaluation_run_id = e.id
          AND cp.period_end IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column('change_points', 'period_end')
