"""add slo_evaluations evaluation_id index.

The grouped-heatmap read path eager-loads children with
`SELECT ... FROM slo_evaluations WHERE evaluation_id IN (:ids)` (a `selectin`
load off `EvaluationRun.slo_evaluations`). Without an index leading with
`evaluation_id` this plans as a sequential scan over the whole table, so a cold
heatmap read costs O(total rows) rather than O(rows in the requested window).

Built with a plain `CREATE INDEX`, which holds a write lock on `slo_evaluations`
for the duration of the build. On a deployment large enough for that lock to
matter, build it out-of-band with `CREATE INDEX CONCURRENTLY` first, then stamp
this revision.

Revision ID: 007
Revises: 006
Create Date: 2026-07-09 16:01:25.170144

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: str | Sequence[str] | None = '006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index('idx_slo_evaluations_evaluation_id', 'slo_evaluations', ['evaluation_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_slo_evaluations_evaluation_id', table_name='slo_evaluations')
