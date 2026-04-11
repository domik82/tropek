"""Pure regeneration engine — computes what changes when a group is updated.

No I/O. Fully unit-testable.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from tropek.modules.slo_groups.generator import GeneratedSLOSpec


class OldSLOState(Protocol):
    """Structural protocol for an existing generated SLO's state."""

    name: str
    comparable_from_version: int


@dataclass
class UpdateAction:
    """One SLO to regenerate with a new version."""

    spec: GeneratedSLOSpec
    comparable_from_version: int | None  # None = preserve existing value


@dataclass
class RegenerationPlan:
    """What to do when a group is updated."""

    to_create: list[GeneratedSLOSpec]
    to_update: list[UpdateAction]
    to_deactivate: list[str]  # SLO names to deactivate


def _indicators_changed(
    old_indicators: dict[str, Any],
    new_indicators: dict[str, Any],
) -> bool:
    """Check if existing SLI indicators were modified or removed.

    Adding NEW indicators does NOT count as a change — baselines for
    existing indicators remain valid. Only modifications to existing
    indicator queries or removals break baseline comparability.
    """
    # Existing indicators removed → breaking change
    if not set(old_indicators.keys()).issubset(set(new_indicators.keys())):
        return True
    # Existing indicator queries modified → breaking change
    return any(str(old_indicators[k]) != str(new_indicators[k]) for k in old_indicators if k in new_indicators)


def plan_regeneration(
    old_generated: Sequence[OldSLOState],
    new_specs: list[GeneratedSLOSpec],
    old_sli_indicators: dict[str, Any],
    new_sli_indicators: dict[str, Any],
    template_variables_changed: bool,
) -> RegenerationPlan:
    """Compute the regeneration plan for a group update.

    Matches old→new by generated SLO name. Determines comparable_from_version
    per the rules:
      - Criteria-only change → preserve
      - SLI version bump, queries unchanged → preserve
      - SLI version bump, queries changed → set to new version (None passed, router sets)
      - Template variables changed → set to new version
    """
    old_by_name = {s.name: s for s in old_generated}
    new_by_name = {s.name: s for s in new_specs}

    old_names = set(old_by_name.keys())
    new_names = set(new_by_name.keys())

    to_create = [new_by_name[n] for n in sorted(new_names - old_names)]
    to_deactivate = sorted(old_names - new_names)

    # Determine comparable_from_version for updated SLOs
    queries_changed = _indicators_changed(old_sli_indicators, new_sli_indicators)
    break_baseline = queries_changed or template_variables_changed

    to_update: list[UpdateAction] = []
    for name in sorted(old_names & new_names):
        old_slo = old_by_name[name]
        new_spec = new_by_name[name]
        if break_baseline:
            # comparable_from_version = None signals "set to new generated version"
            # The router will set it to the actual new version number after creation
            to_update.append(UpdateAction(spec=new_spec, comparable_from_version=None))
        else:
            # Preserve existing comparable_from_version
            to_update.append(
                UpdateAction(
                    spec=new_spec,
                    comparable_from_version=old_slo.comparable_from_version,
                )
            )

    return RegenerationPlan(
        to_create=to_create,
        to_update=to_update,
        to_deactivate=to_deactivate,
    )
