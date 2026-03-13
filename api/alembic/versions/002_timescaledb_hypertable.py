"""Timescaledb hypertable.

Convert sli_values to a TimescaleDB hypertable partitioned by eval_start.
This is a manual step — autogenerate cannot know about TimescaleDB-specific DDL.

Revision ID: 002
Revises: 001
Create Date: 2026-03-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | Sequence[str] | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Convert sli_values to a TimescaleDB hypertable."""
    # Ensure the TimescaleDB extension is present before converting.
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
    # create_hypertable partitions sli_values by eval_start (time dimension).
    # if_not_exists => TRUE makes this idempotent — safe to re-run.
    op.execute("SELECT create_hypertable('sli_values', 'eval_start', if_not_exists => TRUE)")


def downgrade() -> None:
    """Revert sli_values from hypertable back to a plain table.

    TimescaleDB has no 'unconvert hypertable' command — the only way back is
    drop + recreate. All data in sli_values is lost on downgrade.
    """
    op.drop_index("idx_sli_values_lookup", table_name="sli_values")
    op.drop_table("sli_values")
    op.create_table(
        "sli_values",
        sa.Column("eval_id", sa.UUID(), nullable=False),
        sa.Column("eval_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric_name", sa.Text(), nullable=False),
        sa.Column("aggregation", sa.Text(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("asset_name", sa.Text(), nullable=True),
        sa.Column("test_name", sa.Text(), nullable=True),
        sa.Column("os_tag", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["eval_id"], ["evaluations.id"]),
        sa.PrimaryKeyConstraint("eval_id", "eval_start", "metric_name", "aggregation"),
    )
    op.create_index(
        "idx_sli_values_lookup",
        "sli_values",
        ["test_name", "metric_name", "eval_start"],
        unique=False,
    )
