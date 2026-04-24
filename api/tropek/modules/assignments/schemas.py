"""Pydantic schemas for SLO assignments and group assignments."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from tropek.modules.assets.comparison_rules import ComparisonRule
from tropek.modules.common.schemas import SafeStr, StrictInput


class SLOAssignmentUpsert(StrictInput):
    """Request body for PUT-upserting an SLO assignment at /{parent}/slo-definitions/{id}."""

    data_source_name: SafeStr
    comparison_rules: list[ComparisonRule] | None = None


class SLOAssignmentRead(BaseModel):
    """Response schema for an SLO assignment."""

    id: uuid.UUID
    asset_id: uuid.UUID | None
    asset_group_id: uuid.UUID | None
    slo_definition_id: uuid.UUID
    slo_name: str
    slo_version: int
    data_source_id: uuid.UUID
    data_source_name: str
    comparison_rules: list[dict[str, Any]] | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SLOAssignmentUpgrade(StrictInput):
    """Request body for upgrading an SLO assignment to a new definition version."""

    new_slo_definition_id: uuid.UUID


class SLOGroupAssignmentUpsert(StrictInput):
    """Request body for PUT-upserting an SLO group assignment at /{parent}/slo-groups/{name}."""

    data_source_name: SafeStr


class SLOGroupAssignmentRead(BaseModel):
    """Response schema for an SLO group assignment."""

    id: uuid.UUID
    asset_id: uuid.UUID | None
    asset_group_id: uuid.UUID | None
    slo_group_id: uuid.UUID
    slo_group_name: str
    data_source_id: uuid.UUID
    data_source_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
