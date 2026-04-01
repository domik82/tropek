"""Pydantic parameter models for SLO registry repository methods."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class SLOObjectiveParams(BaseModel):
    """Single objective within an SLO definition."""

    sli: str
    display_name: str | None = None
    weight: int = 1
    key_sli: bool = False
    pass_threshold: list[str] = Field(default_factory=list)
    warning_threshold: list[str] = Field(default_factory=list)


class SLOCreateParams(BaseModel):
    """Parameters for SLORepository.create()."""

    name: str
    objectives: list[SLOObjectiveParams]
    total_score_pass_threshold: float = 90.0
    total_score_warning_threshold: float = 75.0
    comparison: dict[str, object] | None = None
    display_name: str | None = None
    notes: str | None = None
    author: str | None = None
    tags: dict[str, object] = Field(default_factory=dict)
    variables: dict[str, object] = Field(default_factory=dict)
    comparable_from_version: int | None = None
    kind: str = 'standard'
    sli_name: str | None = None
    sli_version: int | None = None
    sli_definition_id: uuid.UUID | None = None
    method_criteria: dict[str, object] | None = None
    generated_by_group_id: uuid.UUID | None = None
