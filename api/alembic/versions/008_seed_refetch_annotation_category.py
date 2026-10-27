"""seed the refetch annotation category.

Data-only migration. Run-level refetch notes use the system annotation category
``refetch``; it is seeded like the ``re-evaluation`` category in revision 002.

Revision ID: 008
Revises: 007
Create Date: 2026-10-19 10:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '008'
down_revision: str | Sequence[str] | None = '007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # ON CONFLICT DO NOTHING so re-running this migration is idempotent.
    op.execute("""
        INSERT INTO annotation_categories (id, name, label, color, show_on_graph, is_system) VALUES
            (gen_random_uuid(), 'refetch', 'Refetch', 'gray', false, true)
        ON CONFLICT (name) DO NOTHING
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # evaluation_annotations.category_id is a foreign key without ON DELETE, so the notes go first.
    op.execute("""
        DELETE FROM evaluation_annotations
        WHERE category_id IN (SELECT id FROM annotation_categories WHERE name = 'refetch')
    """)
    op.execute("DELETE FROM annotation_categories WHERE name = 'refetch'")
