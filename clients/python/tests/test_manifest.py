"""Tests for manifest loading and reconciliation logic."""

from __future__ import annotations

import textwrap
from datetime import UTC
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from tropek_client.exceptions import TropekNotFoundError
from tropek_client.manifest import (
    ActionType,
    ResourceKind,
    load_manifest,
    plan,
)
from tropek_client.models import SLIDefinition


def test_load_manifest_single_resource(tmp_path: Path):
    manifest = tmp_path / "test.yaml"
    manifest.write_text(
        textwrap.dedent("""
            kind: SLIDefinition
            metadata:
              name: test-sli
            spec:
              indicators:
                cpu: avg(cpu_usage)
        """)
    )
    resources = load_manifest(manifest)
    assert len(resources) == 1
    assert resources[0].kind == ResourceKind.SLI_DEFINITION
    assert resources[0].name == "test-sli"
    assert resources[0].spec["indicators"] == {"cpu": "avg(cpu_usage)"}


def test_load_manifest_multi_document(tmp_path: Path):
    manifest = tmp_path / "multi.yaml"
    manifest.write_text(
        textwrap.dedent("""
            kind: SLIDefinition
            metadata:
              name: sli-one
            spec:
              indicators:
                cpu: avg(cpu)
            ---
            kind: SLODefinition
            metadata:
              name: slo-one
            spec:
              slo_yaml: "spec_version: '1.0'"
        """)
    )
    resources = load_manifest(manifest)
    assert len(resources) == 2
    assert resources[0].kind == ResourceKind.SLI_DEFINITION
    assert resources[1].kind == ResourceKind.SLO_DEFINITION


def test_load_manifest_missing_kind(tmp_path: Path):
    manifest = tmp_path / "bad.yaml"
    manifest.write_text("metadata:\n  name: foo\n")
    with pytest.raises(ValueError, match="missing 'kind'"):
        load_manifest(manifest)


def test_load_manifest_unknown_kind(tmp_path: Path):
    manifest = tmp_path / "bad.yaml"
    manifest.write_text("kind: UnknownKind\nmetadata:\n  name: foo\n")
    with pytest.raises(ValueError, match="unknown resource kind"):
        load_manifest(manifest)


def test_plan_creates_for_new_resource():
    """Plan should return CREATE for a resource that doesn't exist yet."""
    mock_client = MagicMock()
    mock_client.sli.get.side_effect = TropekNotFoundError(404, "not found")

    from tropek_client.manifest import ManifestResource

    resources = [
        ManifestResource(
            kind=ResourceKind.SLI_DEFINITION,
            name="new-sli",
            spec={"indicators": {"cpu": "avg(cpu)"}},
        )
    ]
    result = plan(mock_client, resources)
    assert result.success
    assert len(result.actions) == 1
    assert result.actions[0].action == ActionType.CREATE
    assert result.actions[0].name == "new-sli"


def test_plan_skips_unchanged_resource():
    """Plan should return SKIP for a resource with identical state."""
    from datetime import datetime

    mock_client = MagicMock()
    existing_sli = SLIDefinition(
        id="test-id",
        name="existing-sli",
        version=1,
        indicators={"cpu": "avg(cpu)"},
        active=True,
        created_at=datetime.now(tz=UTC),
    )
    mock_client.sli.get.return_value = existing_sli

    from tropek_client.manifest import ManifestResource

    resources = [
        ManifestResource(
            kind=ResourceKind.SLI_DEFINITION,
            name="existing-sli",
            spec={"indicators": {"cpu": "avg(cpu)"}},
        )
    ]
    result = plan(mock_client, resources)
    assert result.success
    assert result.actions[0].action == ActionType.SKIP


def test_plan_updates_changed_resource():
    """Plan should return UPDATE for a resource with changed indicators."""
    from datetime import datetime

    mock_client = MagicMock()
    existing_sli = SLIDefinition(
        id="test-id",
        name="existing-sli",
        version=1,
        indicators={"cpu": "old_query()"},
        active=True,
        created_at=datetime.now(tz=UTC),
    )
    mock_client.sli.get.return_value = existing_sli

    from tropek_client.manifest import ManifestResource

    resources = [
        ManifestResource(
            kind=ResourceKind.SLI_DEFINITION,
            name="existing-sli",
            spec={"indicators": {"cpu": "new_query()"}},
        )
    ]
    result = plan(mock_client, resources)
    assert result.success
    assert result.actions[0].action == ActionType.UPDATE
