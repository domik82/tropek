"""Asset type models for TROPEK API."""

from uuid import UUID

from pydantic import BaseModel


class AssetTypeCreate(BaseModel):
    """Asset type creation request."""

    name: str
    is_default: bool | None = False


class AssetTypeRead(BaseModel):
    """Asset type response."""

    id: UUID
    name: str
    is_default: bool
    asset_count: int | None = 0


class AssetTypeUpdate(BaseModel):
    """Asset type update request."""

    name: str | None = None
