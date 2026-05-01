"""Pydantic parameter models for SLO registry repository methods."""

from __future__ import annotations

import uuid

from pydantic import Field

from tropek.modules.change_points.schemas import ChangePointConfigInput
from tropek.modules.common.schemas import StrictInput


class SLOObjectiveParams(StrictInput):
    """Single objective within an SLO definition."""

    sli: str
    display_name: str | None = None
    weight: int = 1
    key_sli: bool = False
    pass_threshold: list[str] = Field(default_factory=list)
    warning_threshold: list[str] = Field(default_factory=list)
    change_point: ChangePointConfigInput | None = None


class SLOCreateParams(StrictInput):
    """Parameters for SLORepository.create()."""

    name: str
    objectives: list[SLOObjectiveParams]
    total_score_pass_threshold: float = 90.0
    total_score_warning_threshold: float = 75.0
    comparison: dict[str, object] | None = None
    display_name: str | None = None
    notes: str | None = None
    author: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    variables: dict[str, str] = Field(default_factory=dict)
    comparable_from_version: int | None = None
    kind: str = 'standard'
    sli_definition_id: uuid.UUID | None = None
    method_criteria: dict[str, object] | None = None
    generated_by_group_id: uuid.UUID | None = None
