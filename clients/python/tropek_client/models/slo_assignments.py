"""SLO assignment models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from tropek_client.models.slos import ComparisonRule


class SLOAssignmentRead(BaseModel):
    """Read model for an SLO assignment."""

    id: UUID
    asset_id: UUID | None = None
    asset_group_id: UUID | None = None
    slo_definition_id: UUID
    slo_name: str
    slo_version: int
    data_source_id: UUID
    data_source_name: str
    comparison_rules: list[dict[str, Any]] | None = None
    created_at: datetime


class SLOAssignmentUpsert(BaseModel):
    """Input model for upserting an SLO assignment."""

    data_source_name: str
    comparison_rules: list[ComparisonRule] | None = None


class SLOAssignmentUpgrade(BaseModel):
    """Input model for upgrading an SLO assignment to a newer version."""

    new_slo_definition_id: UUID
