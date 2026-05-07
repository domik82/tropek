"""add found_by_evaluation_id to change_points.

Revision ID: 005
Revises: 004
Create Date: 2026-05-07 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '005'
down_revision: str | Sequence[str] | None = '004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'change_points',
        sa.Column('found_by_evaluation_id', sa.UUID(), sa.ForeignKey('evaluations.id', ondelete='SET NULL'), nullable=True),
    )
    op.execute(
        """
        UPDATE change_points
        SET found_by_evaluation_id = evaluation_run_id
        WHERE found_by_evaluation_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column('change_points', 'found_by_evaluation_id')
