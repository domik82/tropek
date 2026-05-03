from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel
from tropek_client.manifest import (
    ApplyPlan,
    ManifestDocument,
    PlanAction,
    dry_run,
    load_manifests,
)
from tropek_client.manifest import (
    apply as do_apply,
)
from tropek_client.models import AssetTypeCreate
from tropek_client.models.pagination import PagedResponse

from .conftest import TESTS_DIR

MANIFESTS_DIR = TESTS_DIR / 'fixtures' / 'manifests'


def test_load_single_document():
    docs = load_manifests(str(MANIFESTS_DIR / 'single_document.yaml'))
    assert len(docs) == 1
    assert docs[0].kind == 'AssetType'
    assert docs[0].metadata['name'] == 'vm'
    assert docs[0].spec['is_default'] is True


def test_load_multi_document():
    docs = load_manifests(str(MANIFESTS_DIR / 'multi_document.yaml'))
    assert len(docs) == 2
    assert docs[0].kind == 'AssetType'
    assert docs[1].kind == 'Asset'


def test_load_directory():
    docs = load_manifests(str(MANIFESTS_DIR / 'directory'))
    assert len(docs) == 2


def test_topological_sort():
    docs = load_manifests(str(MANIFESTS_DIR / 'unsorted_dependencies.yaml'))
    kinds = [d.kind for d in docs]
    assert kinds.index('AssetType') < kinds.index('Asset')


def test_rejects_missing_api_version():
    with pytest.raises(ValueError, match='api_version'):
        load_manifests(str(MANIFESTS_DIR / 'missing_api_version.yaml'))


def test_unknown_kind_raises():
    """AssetSLOLink and AssetGroupSLOLink are no longer valid kinds."""
    with pytest.raises(ValueError, match='unknown kind'):
        load_manifests(str(MANIFESTS_DIR / 'unknown_kind.yaml'))


def test_dry_run_creates_plan():
    """dry_run produces CREATE actions for missing entities."""
    client = MagicMock()
    client.asset_types.list.return_value = PagedResponse(items=[], total=0)

    docs = [
        ManifestDocument(
            api_version='tropek/v1',
            kind='AssetType',
            metadata={'name': 'vm'},
            spec={'is_default': True},
        )
    ]
    plan = dry_run(client, docs)
    assert len(plan.actions) == 1
    assert plan.actions[0].operation == 'CREATE'
    assert plan.actions[0].name == 'vm'


def test_apply_creates_entity():
    """apply calls create on the client for CREATE actions."""
    client = MagicMock()
    client.asset_types.list.return_value = PagedResponse(items=[], total=0)

    docs = [
        ManifestDocument(
            api_version='tropek/v1',
            kind='AssetType',
            metadata={'name': 'vm'},
            spec={'is_default': True},
        )
    ]
    result = do_apply(client, docs)
    assert result.created == 1
    assert result.failed == 0
    client.asset_types.create.assert_called_once_with(AssetTypeCreate(name='vm', is_default=True))


def test_apply_plan_is_pydantic_model():
    plan = ApplyPlan()
    assert isinstance(plan, BaseModel)
    plan.actions.append(PlanAction(operation='CREATE', kind='Asset', name='vm-01', reason='reason'))
    assert len(plan.actions) == 1
