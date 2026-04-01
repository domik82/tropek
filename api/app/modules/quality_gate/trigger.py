"""Evaluation trigger resolution — resolves asset/SLO/SLI/datasource references."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.modules.quality_gate.exceptions import (
    AssetNotFoundError,
    DataSourceNotFoundError,
    SLONotConfiguredError,
)
from app.modules.quality_gate.protocols import (
    AssetReader,
    AssignmentReader,
    DataSourceReader,
    SLIReader,
    SLOReader,
)


@dataclass
class TriggerContext:
    """All resolved references needed to run an evaluation job."""

    asset_id: uuid.UUID
    asset_name: str
    asset_display_name: str | None
    asset_tags: dict[str, Any]
    asset_variables: dict[str, Any]
    slo_name: str
    slo_version: int
    slo_definition_id: uuid.UUID
    sli_name: str
    sli_version: int
    sli_definition_id: uuid.UUID | None
    data_source_name: str
    adapter_url: str
    adapter_type: str
    indicators: dict[str, str]


async def resolve_single_trigger(
    *,
    asset_name: str,
    slo_name: str,
    asset_repo: AssetReader,
    sli_repo: SLIReader,
    slo_repo: SLOReader,
    ds_repo: DataSourceReader,
    assignment_repo: AssignmentReader,
    group_ids: list[uuid.UUID],
) -> TriggerContext:
    """Resolve all references for a single asset+SLO pair.

    Raises domain exceptions if any reference is missing.
    """
    asset = await asset_repo.get_by_name(asset_name)
    if asset is None:
        msg = f"asset '{asset_name}' not found"
        raise AssetNotFoundError(msg)

    resolved = await assignment_repo.find_for_asset(asset.id, group_ids, slo_name)
    if resolved is None:
        msg = f"no assignment for asset '{asset_name}' with slo '{slo_name}'"
        raise SLONotConfiguredError(msg)

    slo_def = await slo_repo.get_by_id(resolved.slo_definition_id)
    if slo_def is None:
        msg = f"slo definition '{resolved.slo_definition_id}' not found"
        raise SLONotConfiguredError(msg)

    # Load SLI by FK if available, fall back to name-based lookup
    if slo_def.sli_definition_id is not None:
        sli_def = await sli_repo.get_by_id(slo_def.sli_definition_id)
    elif slo_def.sli_name is not None:
        sli_def = (
            await sli_repo.get_version(slo_def.sli_name, slo_def.sli_version)
            if slo_def.sli_version is not None
            else await sli_repo.get_latest(slo_def.sli_name)
        )
    else:
        msg = f"no sli linked to slo '{slo_def.name}'"
        raise SLONotConfiguredError(msg)

    if sli_def is None:
        msg = f"sli definition for slo '{slo_def.name}' not found"
        raise SLONotConfiguredError(msg)

    ds = await ds_repo.get_by_id(resolved.data_source_id)
    if ds is None:
        msg = f"datasource '{resolved.data_source_id}' not found"
        raise DataSourceNotFoundError(msg)

    return TriggerContext(
        asset_id=asset.id,
        asset_name=asset.name,
        asset_display_name=getattr(asset, 'display_name', None),
        asset_tags=getattr(asset, 'tags', {}),
        asset_variables=getattr(asset, 'variables', {}),
        slo_name=slo_def.name,
        slo_version=slo_def.version,
        slo_definition_id=slo_def.id,
        sli_name=sli_def.name,
        sli_version=sli_def.version,
        sli_definition_id=sli_def.id,
        data_source_name=ds.name,
        adapter_url=ds.adapter_url,
        adapter_type=ds.adapter_type,
        indicators=sli_def.indicators,
    )


async def resolve_all_slos_for_asset(
    *,
    asset_id: uuid.UUID,
    assignment_repo: AssignmentReader,
    group_ids: list[uuid.UUID],
) -> list[str]:
    """Collect all SLO names assigned to an asset (direct + via groups)."""
    resolved = await assignment_repo.resolve_for_asset(asset_id, group_ids)
    return sorted(r.slo_name for r in resolved)
