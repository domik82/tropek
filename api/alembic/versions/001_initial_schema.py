"""Initial schema: assets, slo_definitions, evaluations, annotations, sli_values hypertable.

Revision ID: 001
Revises:
Create Date: 2026-03-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all Phase 1 tables and the TimescaleDB hypertable."""
    op.create_table(
        "assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, unique=True, nullable=False),
        sa.Column("tags", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "slo_definitions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("slo_yaml", sa.Text, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("author", sa.Text, nullable=True),
        sa.Column("meta", JSONB, nullable=False, server_default="{}"),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("name", "version", name="uq_slo_name_version"),
    )
    op.create_index("idx_slo_definitions_name", "slo_definitions", ["name"])
    op.create_index(
        "idx_slo_definitions_latest", "slo_definitions", ["name", sa.text("version DESC")]
    )

    op.create_table(
        "evaluations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("asset_snapshot", JSONB, nullable=False, server_default="{}"),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result", sa.Text, nullable=True),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("slo_yaml", sa.Text, nullable=True),
        sa.Column("slo_name", sa.Text, nullable=True),
        sa.Column("slo_version", sa.Integer, nullable=True),
        sa.Column("indicator_results", JSONB, nullable=False, server_default="[]"),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("ingestion_mode", sa.Text, nullable=False),
        sa.Column("adapter_used", sa.Text, nullable=True),
        sa.Column("invalidated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("invalidation_note", sa.Text, nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("job_stats", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','completed','failed','partial')",
            name="ck_evaluations_status",
        ),
    )
    op.create_index("idx_evaluations_name", "evaluations", ["name"])
    op.create_index("idx_evaluations_result", "evaluations", ["result"])
    op.create_index("idx_evaluations_start", "evaluations", ["start_time"])
    op.create_index("idx_evaluations_status", "evaluations", ["status"])
    op.create_index("idx_evaluations_slo", "evaluations", ["slo_name", "slo_version"])
    op.execute(
        "CREATE INDEX idx_evaluations_stuck ON evaluations(status, started_at) "
        "WHERE status = 'running'"
    )

    op.create_table(
        "evaluation_annotations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "evaluation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("author", sa.Text, nullable=True),
        sa.Column("category", sa.Text, nullable=True),
        sa.Column("meta", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("idx_annotations_evaluation", "evaluation_annotations", ["evaluation_id"])

    # sli_values: regular table first, then converted to TimescaleDB hypertable
    op.create_table(
        "sli_values",
        sa.Column("eval_id", UUID(as_uuid=True), sa.ForeignKey("evaluations.id"), nullable=False),
        sa.Column("eval_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric_name", sa.Text, nullable=False),
        sa.Column("aggregation", sa.Text, nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("asset_name", sa.Text, nullable=True),
        sa.Column("test_name", sa.Text, nullable=True),
        sa.Column("os_tag", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint("eval_id", "eval_start", "metric_name", "aggregation"),
    )
    op.create_index(
        "idx_sli_values_lookup", "sli_values", ["test_name", "metric_name", "eval_start"]
    )
    # Convert to TimescaleDB hypertable — requires TimescaleDB extension installed
    op.execute("SELECT create_hypertable('sli_values', 'eval_start', if_not_exists => TRUE)")


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("sli_values")
    op.drop_table("evaluation_annotations")
    op.drop_table("evaluations")
    op.drop_table("slo_definitions")
    op.drop_table("assets")
