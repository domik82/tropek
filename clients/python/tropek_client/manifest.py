"""YAML manifest loader and desired-state reconciler."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from tropek_client.client import TropekClient
from tropek_client.exceptions import TropekNotFoundError
from tropek_client.models import SLIDefinitionCreate, SLODefinitionCreate


class ResourceKind(StrEnum):
    """Supported manifest resource kinds."""

    SLI_DEFINITION = "SLIDefinition"
    SLO_DEFINITION = "SLODefinition"


@dataclass
class ManifestResource:
    """A single resource parsed from a YAML manifest."""

    kind: ResourceKind
    name: str
    spec: dict[str, Any]


class ActionType(StrEnum):
    """Reconciler action types."""

    CREATE = "create"
    UPDATE = "update"
    SKIP = "skip"


@dataclass
class ReconcileAction:
    """A pending reconcile action."""

    action: ActionType
    kind: ResourceKind
    name: str
    reason: str = ""


@dataclass
class ReconcileResult:
    """Result of a reconcile operation."""

    actions: list[ReconcileAction] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True if no errors occurred."""
        return len(self.errors) == 0


def load_manifest(path: Path | str) -> list[ManifestResource]:
    """Load and parse a YAML manifest file.

    The manifest is a YAML file with one or more documents separated by ---.
    Each document must have `kind` and `metadata.name` fields.

    Example::

        kind: SLIDefinition
        metadata:
          name: my-sli
        spec:
          indicators:
            cpu: avg(cpu_usage)
    """
    path = Path(path)
    content = path.read_text(encoding="utf-8")
    documents = list(yaml.safe_load_all(content))
    resources: list[ManifestResource] = []

    for doc in documents:
        if not doc:
            continue
        kind_str = doc.get("kind")
        if kind_str is None:
            raise ValueError(f"manifest document missing 'kind' field: {doc}")
        try:
            kind = ResourceKind(kind_str)
        except ValueError:
            raise ValueError(f"unknown resource kind: {kind_str!r}") from None
        name = doc.get("metadata", {}).get("name")
        if not name:
            raise ValueError(f"manifest document missing 'metadata.name': {doc}")
        spec = doc.get("spec", {})
        resources.append(ManifestResource(kind=kind, name=name, spec=spec))

    return resources


def plan(
    client: TropekClient,
    resources: list[ManifestResource],
) -> ReconcileResult:
    """Compute reconcile actions without applying them (dry-run).

    Compares desired state (manifest) against current API state.
    Returns CREATE for new resources, UPDATE for changed ones, SKIP for identical.
    """
    result = ReconcileResult()

    for resource in resources:
        try:
            if resource.kind == ResourceKind.SLI_DEFINITION:
                existing = client.sli.get(resource.name)
                # Compare indicators (simplified: always UPDATE if exists)
                if existing.indicators == resource.spec.get("indicators", {}):
                    result.actions.append(
                        ReconcileAction(
                            action=ActionType.SKIP,
                            kind=resource.kind,
                            name=resource.name,
                            reason="no changes detected",
                        )
                    )
                else:
                    result.actions.append(
                        ReconcileAction(
                            action=ActionType.UPDATE,
                            kind=resource.kind,
                            name=resource.name,
                            reason="indicators changed",
                        )
                    )
            elif resource.kind == ResourceKind.SLO_DEFINITION:
                existing_slo = client.slo.get(resource.name)
                if existing_slo.slo_yaml == resource.spec.get("slo_yaml", ""):
                    result.actions.append(
                        ReconcileAction(
                            action=ActionType.SKIP,
                            kind=resource.kind,
                            name=resource.name,
                            reason="no changes detected",
                        )
                    )
                else:
                    result.actions.append(
                        ReconcileAction(
                            action=ActionType.UPDATE,
                            kind=resource.kind,
                            name=resource.name,
                            reason="slo_yaml changed",
                        )
                    )
        except TropekNotFoundError:
            result.actions.append(
                ReconcileAction(
                    action=ActionType.CREATE,
                    kind=resource.kind,
                    name=resource.name,
                    reason="resource does not exist",
                )
            )
        except Exception as e:
            result.errors.append(f"could not check {resource.kind.value}/{resource.name}: {e}")

    return result


def apply(
    client: TropekClient,
    resources: list[ManifestResource],
    *,
    dry_run: bool = False,
) -> ReconcileResult:
    """Apply manifest resources to the TROPEK API.

    If dry_run=True, compute actions without applying them.
    CREATE actions call the appropriate create endpoint.
    UPDATE actions call create (which creates a new version — TROPEK is immutable/versioned).
    SKIP actions do nothing.
    """
    planned = plan(client, resources)
    if dry_run:
        return planned

    result = ReconcileResult(actions=planned.actions[:])

    for action in planned.actions:
        if action.action == ActionType.SKIP:
            continue
        try:
            resource = next(r for r in resources if r.name == action.name and r.kind == action.kind)
            if resource.kind == ResourceKind.SLI_DEFINITION:
                payload = SLIDefinitionCreate(
                    name=resource.name,
                    **resource.spec,
                )
                client.sli.create(payload)
            elif resource.kind == ResourceKind.SLO_DEFINITION:
                payload_slo = SLODefinitionCreate(
                    name=resource.name,
                    **resource.spec,
                )
                client.slo.create(payload_slo)
        except Exception as e:
            result.errors.append(f"could not apply {action.kind.value}/{action.name}: {e}")

    return result
