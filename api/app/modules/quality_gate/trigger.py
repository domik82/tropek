"""Evaluation trigger resolution — resolves asset/SLO/SLI/datasource references."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any


@dataclass
class TriggerContext:
    """All resolved references needed to run an evaluation job."""

    asset_id: uuid.UUID
    asset_name: str
    asset_labels: dict[str, Any]
    slo_name: str
    slo_version: int
    sli_name: str
    sli_version: int
    data_source_name: str
    adapter_url: str
    adapter_type: str
    indicators: dict[str, str]


async def resolve_single_trigger(
    *,
    asset_name: str,
    slo_name: str,
    asset_repo: Any,
    slo_link_repo: Any,
    sli_repo: Any,
    slo_repo: Any,
    ds_repo: Any,
) -> TriggerContext:
    """Resolve all references for a single asset evaluation.

    Raises ValueError with descriptive message if any reference is missing.
    """
    asset = await asset_repo.get_by_name(asset_name)
    if asset is None:
        msg = f"asset '{asset_name}' not found"
        raise ValueError(msg)

    # Find the SLO link for this asset + slo_name
    links = await slo_link_repo.list_by_asset(asset.id)
    link = next((lnk for lnk in links if lnk.slo_name == slo_name), None)
    if link is None:
        msg = f"no slo link for asset '{asset_name}' with slo '{slo_name}'"
        raise ValueError(msg)

    sli_def = await sli_repo.get_latest(link.sli_name)
    if sli_def is None:
        msg = f"sli definition '{link.sli_name}' not found"
        raise ValueError(msg)

    slo_def = await slo_repo.get_latest(link.slo_name)
    if slo_def is None:
        msg = f"slo definition '{link.slo_name}' not found"
        raise ValueError(msg)

    ds = await ds_repo.get_by_name(link.data_source_name)
    if ds is None:
        msg = f"datasource '{link.data_source_name}' not found"
        raise ValueError(msg)

    return TriggerContext(
        asset_id=asset.id,
        asset_name=asset.name,
        asset_labels=getattr(asset, "labels", {}),
        slo_name=slo_def.name,
        slo_version=slo_def.version,
        sli_name=sli_def.name,
        sli_version=sli_def.version,
        data_source_name=ds.name,
        adapter_url=ds.adapter_url,
        adapter_type=ds.adapter_type,
        indicators=sli_def.indicators,
    )
