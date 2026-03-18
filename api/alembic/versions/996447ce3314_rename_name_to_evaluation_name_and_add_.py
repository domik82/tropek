"""rename name to evaluation_name and add baseline index.

Revision ID: 996447ce3314
Revises: 002
Create Date: 2026-03-18 18:45:32.749567

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "996447ce3314"
down_revision: str | Sequence[str] | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Rename columns (data-preserving, not drop+add)
    op.alter_column("evaluations", "name", new_column_name="evaluation_name")
    op.alter_column("sli_values", "test_name", new_column_name="evaluation_name")

    # Replace old name index with evaluation_name index
    op.drop_index("idx_evaluations_name", table_name="evaluations")
    op.create_index(
        "idx_evaluations_evaluation_name", "evaluations", ["evaluation_name"], unique=False
    )

    # Add composite partial index for baseline lookup
    op.create_index(
        "idx_evaluations_baseline_lookup",
        "evaluations",
        ["asset_id", "slo_name", sa.literal_column("period_start DESC")],
        unique=False,
        postgresql_where=sa.text("status = 'completed' AND invalidated = false"),
    )

    # Replace old sli_values lookup index with evaluation_name
    op.drop_index("idx_sli_values_lookup", table_name="sli_values")
    op.create_index(
        "idx_sli_values_lookup",
        "sli_values",
        ["evaluation_name", "metric_name", "eval_start"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Restore sli_values lookup index
    op.drop_index("idx_sli_values_lookup", table_name="sli_values")
    op.create_index(
        "idx_sli_values_lookup",
        "sli_values",
        ["test_name", "metric_name", "eval_start"],
        unique=False,
    )

    # Remove baseline lookup index
    op.drop_index(
        "idx_evaluations_baseline_lookup",
        table_name="evaluations",
        postgresql_where=sa.text("status = 'completed' AND invalidated = false"),
    )

    # Restore old name index
    op.drop_index("idx_evaluations_evaluation_name", table_name="evaluations")
    op.create_index("idx_evaluations_name", "evaluations", ["name"], unique=False)

    # Rename columns back
    op.alter_column("sli_values", "evaluation_name", new_column_name="test_name")
    op.alter_column("evaluations", "evaluation_name", new_column_name="name")
