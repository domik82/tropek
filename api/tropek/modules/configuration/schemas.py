"""Pydantic schemas for the configuration API."""

from __future__ import annotations

from pydantic import BaseModel

from tropek.modules.common.schemas import StrictInput


class ConfigurationRead(BaseModel):
    """Response schema for a configuration entry."""

    name: str
    value: str
    value_type: str
    description: str

    model_config = {'from_attributes': True}


class ConfigurationUpdate(StrictInput):
    """Request body for updating a configuration value."""

    value: str
