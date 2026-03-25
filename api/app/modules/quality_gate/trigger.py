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
    DataSourceReader,
    SLIReader,
    SLOBindingReader,
    SLOLinkReader,
    SLOReader,
)


@dataclass
class TriggerContext:
    """All resolved references needed to run an evaluation job."""

    asset_id: uuid.UUID
    asset_name: str
    asset_tags: dict[str, Any]
    asset_variables: dict[str, Any]
    slo_name: str
    slo_version: int
    sli_name: str
    sli_version: int
    data_source_name: str
    adapter_url: str
    adapter_type: str
    indicators: dict[str, str]


@dataclass
class ResolvedBinding:
    """One resolved (slo_name, data_source_name) pair for evaluation."""

    slo_name: str
    data_source_name: str
    source: str  # "direct_asset", "direct_group", "template_asset", "template_group"


_PRECEDENCE = {"direct_asset": 4, "direct_group": 3, "template_asset": 2, "template_group": 1}


def _precedence(source: str) -> int:
    return _PRECEDENCE.get(source, 0)


async def resolve_single_trigger(
    *,
    asset_name: str,
    slo_name: str,
    asset_repo: AssetReader,
    slo_link_repo: SLOLinkReader,
    sli_repo: SLIReader,
    slo_repo: SLOReader,
    ds_repo: DataSourceReader,
    binding_repo: SLOBindingReader | None = None,
) -> TriggerContext:
    """Resolve all references for a single asset evaluation.

    Resolution order:
      1. Legacy asset_slo_links table (backward compat)
      2. New slo_bindings table (direct asset or via group membership)

    Raises domain exceptions if any reference is missing.
    """
    asset = await asset_repo.get_by_name(asset_name)
    if asset is None:
        msg = f"asset '{asset_name}' not found"
        raise AssetNotFoundError(msg)

    # Try legacy SLO link first
    links = await slo_link_repo.list_by_asset(asset.id)
    link = next((lnk for lnk in links if lnk.slo_name == slo_name), None)

    # Fall back to new SLO binding (direct or via group membership)
    binding = None
    if link is None and binding_repo is not None:
        binding = await binding_repo.find_for_asset(asset.id, slo_name)

    if link is None and binding is None:
        msg = f"no slo link or binding for asset '{asset_name}' with slo '{slo_name}'"
        raise SLONotConfiguredError(msg)

    slo_def = await slo_repo.get_latest(slo_name)
    if slo_def is None:
        msg = f"slo definition '{slo_name}' not found"
        raise SLONotConfiguredError(msg)

    # Resolve SLI: SLO definition first, then legacy link fallback
    sli_name = slo_def.sli_name or (link.sli_name if link else None)
    if sli_name is None:
        msg = f"no sli_name on slo '{slo_name}' and no legacy link with sli reference"
        raise SLONotConfiguredError(msg)

    sli_version = slo_def.sli_version
    if sli_version is not None:
        sli_def = await sli_repo.get_version(sli_name, sli_version)
    else:
        sli_def = await sli_repo.get_latest(sli_name)

    if sli_def is None:
        msg = f"sli definition '{sli_name}' not found"
        raise SLONotConfiguredError(msg)

    # Resolve datasource: from binding or legacy link (one is always non-None here)
    if binding is not None:
        ds_name = binding.data_source_name
    else:
        assert link is not None  # guarded by SLONotConfiguredError above
        ds_name = link.data_source_name
    ds = await ds_repo.get_by_name(ds_name)
    if ds is None:
        msg = f"datasource '{ds_name}' not found"
        raise DataSourceNotFoundError(msg)

    return TriggerContext(
        asset_id=asset.id,
        asset_name=asset.name,
        asset_tags=getattr(asset, "tags", {}),
        asset_variables=getattr(asset, "variables", {}),
        slo_name=slo_def.name,
        slo_version=slo_def.version,
        sli_name=sli_def.name,
        sli_version=sli_def.version,
        data_source_name=ds.name,
        adapter_url=ds.adapter_url,
        adapter_type=ds.adapter_type,
        indicators=sli_def.indicators,
    )


async def resolve_all_bindings_for_asset(
    *,
    asset_id: uuid.UUID,
    group_ids: list[uuid.UUID],
    binding_repo: SLOBindingReader,
) -> list[ResolvedBinding]:
    """Resolve all SLO bindings for an asset (direct + template-sourced).

    Template bindings fan out into real slo_bindings with source='template',
    so this just queries the slo_bindings table and deduplicates by precedence:
    direct_asset > direct_group > template_asset > template_group.
    """
    all_bindings = await binding_repo.list_for_asset_evaluation(asset_id, group_ids)
    seen: dict[str, ResolvedBinding] = {}
    for b in all_bindings:
        if b.source == "template":
            source = "template_asset" if str(b.target_type) == "asset" else "template_group"
        else:
            source = "direct_asset" if str(b.target_type) == "asset" else "direct_group"
        rb = ResolvedBinding(
            slo_name=b.slo_name, data_source_name=b.data_source_name, source=source
        )
        if b.slo_name not in seen or _precedence(source) > _precedence(seen[b.slo_name].source):
            seen[b.slo_name] = rb
    return sorted(seen.values(), key=lambda r: r.slo_name)
