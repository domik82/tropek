"""SLO group, display group, and assignment models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class SLOGroupCreate(BaseModel):
    """Input model for creating an SLO group."""

    name: str
    display_name: str | None = None
    template_slo_name: str
    template_slo_version: int
    gen_variables: dict[str, Any]
    tags: dict[str, str] | None = None
    author: str | None = None


class SLOGroupRead(BaseModel):
    """Read model for an SLO group."""

    id: UUID
    name: str
    display_name: str | None = None
    template_slo_name: str
    template_slo_version: int
    template_slo_definition_id: UUID
    gen_variables: dict[str, list[str]]
    tags: dict[str, Any]
    author: str | None = None
    version: int
    active: bool
    created_at: datetime
    updated_at: datetime
    generated_slo_count: int


class SLOGroupUpdate(BaseModel):
    """Input model for updating an SLO group."""

    template_slo_name: str | None = None
    template_slo_version: int | None = None
    gen_variables: dict[str, Any] | None = None
    display_name: str | None = None
    tags: dict[str, str] | None = None
    author: str | None = None


class SLOGroupAssignmentRead(BaseModel):
    """Read model for an SLO group assignment."""

    id: UUID
    asset_id: UUID | None = None
    asset_group_id: UUID | None = None
    slo_group_id: UUID
    slo_group_name: str
    data_source_id: UUID
    data_source_name: str
    created_at: datetime


class SLOGroupAssignmentUpsert(BaseModel):
    """Input model for upserting an SLO group assignment."""

    data_source_name: str


class ExtractRequest(BaseModel):
    """Input model for extracting an SLO from a group."""

    slo_name: str
    new_name: str


class DisplayGroupCreate(BaseModel):
    """Input model for creating a display group."""

    name: str
    display_name: str | None = None
    parent_id: UUID | None = None
    sort_order: int = 0


class DisplayGroupRead(BaseModel):
    """Read model for a display group."""

    id: UUID
    name: str
    display_name: str | None = None
    parent_id: UUID | None = None
    sort_order: int
    created_at: datetime


class DisplayGroupMemberAdd(BaseModel):
    """Input model for adding a member to a display group."""

    slo_name: str
