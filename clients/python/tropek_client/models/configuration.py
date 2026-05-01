"""Configuration entry models."""

from pydantic import BaseModel


class ConfigurationRead(BaseModel):
    """Read model for a configuration entry."""

    name: str
    value: str
    value_type: str
    description: str


class ConfigurationUpdate(BaseModel):
    """Input model for updating a configuration entry."""

    value: str
