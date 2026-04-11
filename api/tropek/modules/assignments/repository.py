"""Repository for slo_assignments and slo_group_assignments."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tropek.db.models import SLOAssignment, SLOGroupAssignment


@dataclass
class ResolvedAssignment:
    """One resolved (slo_definition_id, data_source_id) pair after precedence dedup."""

    slo_name: str
    slo_definition_id: uuid.UUID
    data_source_id: uuid.UUID
    comparison_rules: list[dict[str, Any]] | None
    source: str  # 'direct_asset' | 'direct_group' | 'template_asset' | 'template_group'


class AssignmentRepository:
    """CRUD and resolution logic for slo_assignments and slo_group_assignments."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # SLOAssignment CRUD
    # ------------------------------------------------------------------

    async def create_slo_assignment(
        self,
        *,
        asset_id: uuid.UUID | None,
        asset_group_id: uuid.UUID | None,
        slo_definition_id: uuid.UUID,
        slo_name: str,
        data_source_id: uuid.UUID,
        comparison_rules: list[dict[str, Any]] | None = None,
    ) -> SLOAssignment:
        """Insert a new SLO assignment. Exactly one of asset_id/asset_group_id must be set."""
        row = SLOAssignment(
            id=uuid.uuid4(),
            asset_id=asset_id,
            asset_group_id=asset_group_id,
            slo_definition_id=slo_definition_id,
            slo_name=slo_name,
            data_source_id=data_source_id,
            comparison_rules=comparison_rules,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_slo_assignments_for_asset(self, asset_id: uuid.UUID) -> list[SLOAssignment]:
        """Return all direct-asset SLO assignments ordered by slo_name."""
        result = await self._session.execute(
            select(SLOAssignment)
            .options(selectinload(SLOAssignment.slo_definition), selectinload(SLOAssignment.data_source))
            .where(SLOAssignment.asset_id == asset_id)
            .order_by(SLOAssignment.slo_name)
        )
        return list(result.scalars().all())

    async def list_slo_assignments_for_group(self, asset_group_id: uuid.UUID) -> list[SLOAssignment]:
        """Return all direct-group SLO assignments ordered by slo_name."""
        result = await self._session.execute(
            select(SLOAssignment)
            .options(selectinload(SLOAssignment.slo_definition), selectinload(SLOAssignment.data_source))
            .where(SLOAssignment.asset_group_id == asset_group_id)
            .order_by(SLOAssignment.slo_name)
        )
        return list(result.scalars().all())

    async def get_slo_assignment(self, assignment_id: uuid.UUID) -> SLOAssignment | None:
        """Return a specific SLO assignment by primary key, or None."""
        result = await self._session.execute(select(SLOAssignment).where(SLOAssignment.id == assignment_id))
        return result.scalar_one_or_none()

    async def upgrade_slo_assignment(
        self,
        assignment_id: uuid.UUID,
        new_slo_definition_id: uuid.UUID,
    ) -> SLOAssignment | None:
        """Update slo_definition_id in-place (version upgrade). slo_name stays the same."""
        row = await self.get_slo_assignment(assignment_id)
        if row is None:
            return None
        row.slo_definition_id = new_slo_definition_id
        await self._session.flush()
        return row

    async def delete_slo_assignment(self, assignment_id: uuid.UUID) -> None:
        """Hard-delete an SLO assignment by ID."""
        await self._session.execute(delete(SLOAssignment).where(SLOAssignment.id == assignment_id))

    # ------------------------------------------------------------------
    # SLOGroupAssignment CRUD
    # ------------------------------------------------------------------

    async def create_group_assignment(
        self,
        *,
        asset_id: uuid.UUID | None,
        asset_group_id: uuid.UUID | None,
        slo_group_id: uuid.UUID,
        data_source_id: uuid.UUID,
    ) -> SLOGroupAssignment:
        """Insert a new SLO group assignment."""
        row = SLOGroupAssignment(
            id=uuid.uuid4(),
            asset_id=asset_id,
            asset_group_id=asset_group_id,
            slo_group_id=slo_group_id,
            data_source_id=data_source_id,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_group_assignments_for_asset(self, asset_id: uuid.UUID) -> list[SLOGroupAssignment]:
        """Return all group assignments for an asset."""
        result = await self._session.execute(
            select(SLOGroupAssignment)
            .options(selectinload(SLOGroupAssignment.slo_group), selectinload(SLOGroupAssignment.data_source))
            .where(SLOGroupAssignment.asset_id == asset_id)
        )
        return list(result.scalars().all())

    async def list_group_assignments_for_group(self, asset_group_id: uuid.UUID) -> list[SLOGroupAssignment]:
        """Return all group assignments for an asset group."""
        result = await self._session.execute(
            select(SLOGroupAssignment)
            .options(selectinload(SLOGroupAssignment.slo_group), selectinload(SLOGroupAssignment.data_source))
            .where(SLOGroupAssignment.asset_group_id == asset_group_id)
        )
        return list(result.scalars().all())

    async def get_group_assignment(self, assignment_id: uuid.UUID) -> SLOGroupAssignment | None:
        """Return a group assignment by ID, or None."""
        result = await self._session.execute(select(SLOGroupAssignment).where(SLOGroupAssignment.id == assignment_id))
        return result.scalar_one_or_none()

    async def delete_group_assignment(self, assignment_id: uuid.UUID) -> None:
        """Hard-delete a group assignment by ID."""
        await self._session.execute(delete(SLOGroupAssignment).where(SLOGroupAssignment.id == assignment_id))

    # ------------------------------------------------------------------
    # Evaluation resolution
    # ------------------------------------------------------------------

    async def resolve_for_asset(
        self,
        asset_id: uuid.UUID,
        group_ids: list[uuid.UUID],
    ) -> list[ResolvedAssignment]:
        """Return the winning (slo_definition_id, data_source_id) per SLO concept.

        Priority: direct_asset > direct_group > template_asset > template_group.
        """
        sql = text("""
WITH all_assignments AS (
    SELECT sa.slo_definition_id, sa.data_source_id, sa.comparison_rules,
           'direct_asset'::text AS source, sd.name AS slo_name
    FROM slo_assignments sa
    JOIN slo_definitions sd ON sd.id = sa.slo_definition_id
    WHERE sa.asset_id = :asset_id

    UNION ALL

    SELECT sa.slo_definition_id, sa.data_source_id, sa.comparison_rules,
           'direct_group'::text AS source, sd.name AS slo_name
    FROM slo_assignments sa
    JOIN slo_definitions sd ON sd.id = sa.slo_definition_id
    WHERE sa.asset_group_id = ANY(:group_ids)

    UNION ALL

    SELECT sd.id AS slo_definition_id, sga.data_source_id, NULL AS comparison_rules,
           'template_asset'::text AS source, sd.name AS slo_name
    FROM slo_group_assignments sga
    JOIN slo_groups sg ON sg.id = sga.slo_group_id AND sg.active = true
    JOIN slo_definitions sd ON sd.generated_by_group_id = sg.id AND sd.active = true
    WHERE sga.asset_id = :asset_id

    UNION ALL

    SELECT sd.id AS slo_definition_id, sga.data_source_id, NULL AS comparison_rules,
           'template_group'::text AS source, sd.name AS slo_name
    FROM slo_group_assignments sga
    JOIN slo_groups sg ON sg.id = sga.slo_group_id AND sg.active = true
    JOIN slo_definitions sd ON sd.generated_by_group_id = sg.id AND sd.active = true
    WHERE sga.asset_group_id = ANY(:group_ids)
)
SELECT DISTINCT ON (slo_name)
    slo_definition_id, data_source_id, comparison_rules, slo_name, source
FROM all_assignments
ORDER BY slo_name,
    CASE source
        WHEN 'direct_asset'   THEN 4
        WHEN 'direct_group'   THEN 3
        WHEN 'template_asset' THEN 2
        WHEN 'template_group' THEN 1
    END DESC
        """)
        result = await self._session.execute(
            sql,
            {'asset_id': asset_id, 'group_ids': list(group_ids) if group_ids else []},
        )
        rows = result.mappings().all()
        return [
            ResolvedAssignment(
                slo_name=row['slo_name'],
                slo_definition_id=row['slo_definition_id'],
                data_source_id=row['data_source_id'],
                comparison_rules=row['comparison_rules'],
                source=row['source'],
            )
            for row in rows
        ]

    async def find_for_asset(
        self,
        asset_id: uuid.UUID,
        group_ids: list[uuid.UUID],
        slo_name: str,
    ) -> ResolvedAssignment | None:
        """Return the winning assignment for a specific SLO name, or None."""
        resolved = await self.resolve_for_asset(asset_id, group_ids)
        for r in resolved:
            if r.slo_name == slo_name:
                return r
        return None
