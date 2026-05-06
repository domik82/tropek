"""rename path to label_path on asset_meta_values and asset_meta_closures.

Revision ID: 003
Revises: 002
Create Date: 2026-05-06 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "003"
down_revision: str | Sequence[str] | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_asset_meta_values_snapshot_path", "asset_meta_values", type_="unique")
    op.alter_column("asset_meta_values", "path", new_column_name="label_path")
    op.create_unique_constraint(
        "uq_asset_meta_values_snapshot_label_path", "asset_meta_values", ["snapshot_id", "label_path"]
    )

    op.drop_constraint("uq_asset_meta_closures_snapshot_path", "asset_meta_closures", type_="unique")
    op.alter_column("asset_meta_closures", "path", new_column_name="label_path")
    op.create_unique_constraint(
        "uq_asset_meta_closures_snapshot_label_path", "asset_meta_closures", ["snapshot_id", "label_path"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_asset_meta_closures_snapshot_label_path", "asset_meta_closures", type_="unique")
    op.alter_column("asset_meta_closures", "label_path", new_column_name="path")
    op.create_unique_constraint(
        "uq_asset_meta_closures_snapshot_path", "asset_meta_closures", ["snapshot_id", "path"]
    )

    op.drop_constraint("uq_asset_meta_values_snapshot_label_path", "asset_meta_values", type_="unique")
    op.alter_column("asset_meta_values", "label_path", new_column_name="path")
    op.create_unique_constraint(
        "uq_asset_meta_values_snapshot_path", "asset_meta_values", ["snapshot_id", "path"]
    )
