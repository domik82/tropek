"""Domain model redesign — rename columns, add new tables.

Revision ID: 003
Revises: 002
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- evaluations: rename window columns ---
    op.alter_column("evaluations", "start_time", new_column_name="period_start")
    op.alter_column("evaluations", "end_time", new_column_name="period_end")

    # --- evaluations: new provenance columns ---
    op.add_column("evaluations", sa.Column("sli_name", sa.Text(), nullable=True))
    op.add_column("evaluations", sa.Column("sli_version", sa.Integer(), nullable=True))
    op.add_column("evaluations", sa.Column("data_source_name", sa.Text(), nullable=True))

    # --- evaluations: update existing index that used start_time ---
    op.drop_index("idx_evaluations_start", table_name="evaluations")
    op.create_index("idx_evaluations_start", "evaluations", ["period_start"])

    # --- evaluation_annotations: add updated_at ---
    op.add_column(
        "evaluation_annotations",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- slo_definitions: add display_name ---
    op.add_column("slo_definitions", sa.Column("display_name", sa.Text(), nullable=True))

    # --- assets: add display_name ---
    op.add_column("assets", sa.Column("display_name", sa.Text(), nullable=True))

    # --- data_sources ---
    op.create_table(
        "data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), unique=True, nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("adapter_type", sa.Text(), nullable=False),
        sa.Column("adapter_url", sa.Text(), nullable=False),
        sa.Column("labels", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_data_sources_name", "data_sources", ["name"])

    # --- sli_definitions ---
    op.create_table(
        "sli_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("indicators", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_sli_name_version"),
    )
    op.create_index("idx_sli_definitions_name", "sli_definitions", ["name"])
    op.create_index("idx_sli_definitions_latest", "sli_definitions", ["name", sa.text("version DESC")])

    # --- asset_groups ---
    op.create_table(
        "asset_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), unique=True, nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- asset_group_members ---
    op.create_table(
        "asset_group_members",
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset_groups.id", ondelete="CASCADE"), nullable=False, primary_key=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, primary_key=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.create_index("idx_asset_group_members_group", "asset_group_members", ["group_id"])
    op.create_index("idx_asset_group_members_asset", "asset_group_members", ["asset_id"])

    # --- asset_group_links ---
    op.create_table(
        "asset_group_links",
        sa.Column("parent_group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset_groups.id", ondelete="CASCADE"), nullable=False, primary_key=True),
        sa.Column("child_group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset_groups.id", ondelete="CASCADE"), nullable=False, primary_key=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.create_index("idx_asset_group_links_parent", "asset_group_links", ["parent_group_id"])

    # --- asset_slo_links ---
    op.create_table(
        "asset_slo_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("link_name", sa.Text(), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slo_name", sa.Text(), nullable=False),
        sa.Column("sli_name", sa.Text(), nullable=False),
        sa.Column("data_source_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("asset_id", "link_name", name="uq_asset_slo_link_name"),
    )
    op.create_index("idx_asset_slo_links_asset", "asset_slo_links", ["asset_id"])

    # --- asset_group_slo_links ---
    op.create_table(
        "asset_group_slo_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("link_name", sa.Text(), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slo_name", sa.Text(), nullable=False),
        sa.Column("sli_name", sa.Text(), nullable=False),
        sa.Column("data_source_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("group_id", "link_name", name="uq_asset_group_slo_link_name"),
    )
    op.create_index("idx_asset_group_slo_links_group", "asset_group_slo_links", ["group_id"])

    # --- evaluation_batches ---
    op.create_table(
        "evaluation_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("trigger_params", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("evaluation_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_evaluation_batches_status", "evaluation_batches", ["status"])


def downgrade() -> None:
    op.drop_table("evaluation_batches")
    op.drop_table("asset_group_slo_links")
    op.drop_table("asset_slo_links")
    op.drop_table("asset_group_links")
    op.drop_table("asset_group_members")
    op.drop_table("asset_groups")
    op.drop_table("sli_definitions")
    op.drop_table("data_sources")
    op.drop_column("assets", "display_name")
    op.drop_column("slo_definitions", "display_name")
    op.drop_column("evaluation_annotations", "updated_at")
    op.drop_index("idx_evaluations_start", table_name="evaluations")
    op.create_index("idx_evaluations_start", "evaluations", ["start_time"])
    op.drop_column("evaluations", "data_source_name")
    op.drop_column("evaluations", "sli_version")
    op.drop_column("evaluations", "sli_name")
    op.alter_column("evaluations", "period_end", new_column_name="end_time")
    op.alter_column("evaluations", "period_start", new_column_name="start_time")
