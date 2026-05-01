"""SLO registry repository — versioned CRUD for slo_definitions table."""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tropek.cache.redis_cache import RedisCache
from tropek.db.models import ChangePointConfig, SLODefinition
from tropek.db.models import SLOObjective as SLOObjectiveORM
from tropek.modules.change_points.schemas import ChangePointConfigInput
from tropek.modules.common.tag_mixin import TagQueryMixin
from tropek.modules.configuration.repository import ConfigurationRepository
from tropek.modules.slo_registry.params import SLOCreateParams


class SLORepository(TagQueryMixin):
    """Data access layer for versioned SLO definitions."""

    _tag_model = SLODefinition

    def __init__(self, session: AsyncSession, cache: RedisCache | None = None) -> None:
        self._session = session
        self._cache = cache

    async def create(self, params: SLOCreateParams) -> SLODefinition:
        """Insert a new version of a named SLO.

        Version is auto-incremented using SELECT ... FOR UPDATE to prevent races.

        Args:
            params: SLO creation parameters including name, objectives, scoring thresholds,
                comparison config, metadata, and optional SLI binding.

        Returns:
            The newly created SLODefinition with its assigned version.
        """
        result = await self._session.execute(
            select(SLODefinition.version)
            .where(SLODefinition.name == params.name)
            .order_by(SLODefinition.version.desc())
            .limit(1)
            .with_for_update()
        )
        max_version = result.scalar_one_or_none()
        next_version = (max_version or 0) + 1

        if params.comparable_from_version is not None:
            resolved_cfv = params.comparable_from_version
        elif max_version is not None:
            resolved_cfv = max_version
        else:
            resolved_cfv = 1

        slo = SLODefinition(
            id=uuid.uuid4(),
            name=params.name,
            version=next_version,
            comparable_from_version=resolved_cfv,
            total_score_pass_threshold=params.total_score_pass_threshold,
            total_score_warning_threshold=params.total_score_warning_threshold,
            comparison=params.comparison or {},
            display_name=params.display_name,
            notes=params.notes,
            author=params.author,
            tags=params.tags,
            variables=params.variables,
            kind=params.kind,
            sli_definition_id=params.sli_definition_id,
            method_criteria=params.method_criteria,
            generated_by_group_id=params.generated_by_group_id,
            active=True,
        )
        self._session.add(slo)
        await self._session.flush()

        previous_cp_configs: dict[str, ChangePointConfig] = {}
        if max_version is not None:
            previous_version = await self.get_version(params.name, max_version)
            if previous_version:
                for prev_obj in previous_version.objectives:
                    if prev_obj.change_point_config:
                        previous_cp_configs[prev_obj.sli] = prev_obj.change_point_config

        config_repo = ConfigurationRepository(self._session)
        system_defaults = await config_repo.get_change_point_defaults()

        for i, obj in enumerate(params.objectives):
            orm_obj = SLOObjectiveORM(
                id=uuid.uuid4(),
                slo_definition_id=slo.id,
                sli=obj.sli,
                display_name=obj.display_name or '',
                weight=obj.weight,
                key_sli=obj.key_sli,
                sort_order=i,
                pass_threshold=obj.pass_threshold,
                warning_threshold=obj.warning_threshold,
            )
            self._session.add(orm_obj)
            self._attach_change_point_config(
                orm_obj,
                cp_input=obj.change_point,
                previous_config=previous_cp_configs.get(obj.sli),
                system_defaults=system_defaults,
            )

        await self._session.flush()
        # Eagerly load objectives and sli_definition so callers can access them
        await self._session.refresh(slo, ['objectives', 'sli_definition'])
        if self._cache:
            await self._cache.invalidate(f'slo:{params.name}:latest')
        return slo

    def _attach_change_point_config(
        self,
        orm_obj: SLOObjectiveORM,
        cp_input: ChangePointConfigInput | None,
        previous_config: ChangePointConfig | None,
        system_defaults: dict[str, Any],
    ) -> None:
        """Insert a ChangePointConfig row for an objective if warranted.

        Priority: explicit input from the request > copy-forward from the previous version >
        no row (system defaults apply at query time).

        Args:
            orm_obj: The freshly created SLOObjective ORM instance.
            cp_input: Explicit change-point settings from the create request, or None.
            previous_config: Existing config from the previous SLO version for this SLI, or None.
            system_defaults: System-level default values from the configuration table.
        """
        if cp_input is not None:
            self._session.add(ChangePointConfig(
                slo_objective_id=orm_obj.id,
                enabled=cp_input.enabled if cp_input.enabled is not None
                    else bool(system_defaults.get('enabled', True)),
                higher_is_better=cp_input.higher_is_better
                    if cp_input.higher_is_better is not None
                    else bool(system_defaults.get('higher_is_better', False)),
                window_size=cp_input.window_size if cp_input.window_size is not None
                    else int(system_defaults.get('window_size', 30)),
                max_pvalue=cp_input.max_pvalue if cp_input.max_pvalue is not None
                    else float(system_defaults.get('max_pvalue', 0.001)),
                min_magnitude=cp_input.min_magnitude if cp_input.min_magnitude is not None
                    else float(system_defaults.get('min_magnitude', 0.0)),
                min_sample_size=cp_input.min_sample_size
                    if cp_input.min_sample_size is not None
                    else int(system_defaults.get('min_sample_size', 10)),
            ))
        elif previous_config is not None:
            self._session.add(ChangePointConfig(
                slo_objective_id=orm_obj.id,
                enabled=previous_config.enabled,
                higher_is_better=previous_config.higher_is_better,
                window_size=previous_config.window_size,
                max_pvalue=previous_config.max_pvalue,
                min_magnitude=previous_config.min_magnitude,
                min_sample_size=previous_config.min_sample_size,
            ))

    async def get_latest(self, name: str) -> SLODefinition | None:
        """Return the highest version of a named SLO, or None if not found or deleted.

        Args:
            name: Stable external SLO identifier.

        Returns:
            Latest active SLODefinition, or None.
        """
        result = await self._session.execute(
            select(SLODefinition)
            .options(selectinload(SLODefinition.sli_definition))
            .where(SLODefinition.name == name, SLODefinition.active == True)  # noqa: E712
            .order_by(SLODefinition.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, slo_id: uuid.UUID) -> SLODefinition | None:
        """Return a specific SLO definition by primary key, or None."""
        result = await self._session.execute(
            select(SLODefinition).options(selectinload(SLODefinition.sli_definition)).where(SLODefinition.id == slo_id)
        )
        return result.scalar_one_or_none()

    async def get_version(self, name: str, version: int) -> SLODefinition | None:
        """Return a specific version of a named SLO.

        Args:
            name: Stable external SLO identifier.
            version: Integer version number.

        Returns:
            Matching SLODefinition, or None.
        """
        result = await self._session.execute(
            select(SLODefinition)
            .options(selectinload(SLODefinition.sli_definition))
            .where(
                SLODefinition.name == name,
                SLODefinition.version == version,
            )
        )
        return result.scalar_one_or_none()

    async def list_versions(self, name: str) -> list[SLODefinition]:
        """Return all versions of a named SLO, newest first.

        Args:
            name: Stable external SLO identifier.

        Returns:
            All SLODefinition rows for this name, ordered by version descending.
        """
        result = await self._session.execute(
            select(SLODefinition)
            .options(selectinload(SLODefinition.sli_definition))
            .where(SLODefinition.name == name)
            .order_by(SLODefinition.version.desc())
        )
        return list(result.scalars().all())

    async def list_by_group_id(self, group_id: uuid.UUID) -> list[SLODefinition]:
        """Return all active SLOs generated by a specific group."""
        result = await self._session.execute(
            select(SLODefinition)
            .options(selectinload(SLODefinition.sli_definition))
            .where(SLODefinition.generated_by_group_id == group_id, SLODefinition.active == True)  # noqa: E712
            .order_by(SLODefinition.name)
        )
        return list(result.scalars().all())

    async def list_all(
        self,
        *,
        tag_key: str | None = None,
        tag_val: str | None = None,
        kind: str | None = None,
    ) -> list[SLODefinition]:
        """Return the latest active version of every named SLO.

        Uses DISTINCT ON (name) ORDER BY name, version DESC — PostgreSQL-specific.

        Args:
            tag_key: Tag key to filter by (requires tag_val).
            tag_val: Tag value to filter by (requires tag_key).
            kind: Optional SLO kind filter (e.g. "standard" or "template").

        Returns:
            One SLODefinition per active SLO name, the highest version of each.
        """
        # DISTINCT ON (name) with ORDER BY name, version DESC — PostgreSQL-specific
        base_filter = SLODefinition.active == True  # noqa: E712
        if kind is not None:
            base_filter = base_filter & (SLODefinition.kind == kind)
        subq = (
            select(SLODefinition.name, SLODefinition.version)
            .where(base_filter)
            .distinct(SLODefinition.name)
            .order_by(SLODefinition.name, SLODefinition.version.desc())
        ).subquery()

        q = (
            select(SLODefinition)
            .options(selectinload(SLODefinition.sli_definition))
            .join(
                subq,
                (SLODefinition.name == subq.c.name) & (SLODefinition.version == subq.c.version),
            )
        )
        if tag_key and tag_val:
            q = q.where(SLODefinition.tags[tag_key].as_string() == tag_val)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def deactivate(self, name: str) -> int:
        """Mark all versions of a named SLO as inactive.

        Evaluations that used this SLO retain their `slo_name`/`slo_version` snapshots.

        Args:
            name: Stable external SLO identifier.

        Returns:
            Number of rows affected (versions deactivated).
        """
        cursor = cast(
            'CursorResult[Any]',
            await self._session.execute(update(SLODefinition).where(SLODefinition.name == name).values(active=False)),
        )
        return cursor.rowcount
