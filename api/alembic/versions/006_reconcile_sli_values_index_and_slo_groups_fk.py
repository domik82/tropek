"""reconcile sli_values index and slo_groups fk.

Reconciles two pre-existing drift items between models.py and the migration
history that predate this branch:

- `sli_values_eval_start_idx` is a default index TimescaleDB's
  `create_hypertable()` (migration 002) auto-creates on the partitioning
  column. It has no representation in the SQLAlchemy model (it's a raw-SQL
  side effect), and an earlier migration explicitly dropped it in favor of
  `idx_sli_values_lookup`; that explicit drop was lost when the migration
  history was squashed into 001. This migration re-drops it.
- `fk_slo_groups_template_slo_definition_id` was declared in models.py (and
  inline in 001's `op.create_table(...)` args) with `use_alter=True` to break
  a circular FK dependency, but Alembic's `CreateTable` DDL compiler silently
  omits `use_alter` constraints from inline table DDL — they must be emitted
  via a separate `op.create_foreign_key(...)` call, which 001 never had. As a
  result the constraint was never actually created in any deployed database.
  This migration adds it explicitly.

  Note: on a deployed database containing orphaned `template_slo_definition_id`
  values (rows referencing a `slo_definitions.id` that no longer exists), this
  `create_foreign_key` step will fail. That's acceptable for alpha and is
  documented here deliberately rather than adding cleanup logic.

Revision ID: 006
Revises: 005
Create Date: 2026-07-08 10:31:57.923796

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: str | Sequence[str] | None = '005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f('sli_values_eval_start_idx'), table_name='sli_values')
    op.create_foreign_key(
        'fk_slo_groups_template_slo_definition_id',
        'slo_groups',
        'slo_definitions',
        ['template_slo_definition_id'],
        ['id'],
        use_alter=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_slo_groups_template_slo_definition_id', 'slo_groups', type_='foreignkey')
    # Best-effort reconstruction of TimescaleDB's create_hypertable auto-index (migration 002) —
    # there is no authoritative prior migration defining this index to restore verbatim.
    op.create_index(op.f('sli_values_eval_start_idx'), 'sli_values', [sa.literal_column('eval_start DESC')], unique=False)
