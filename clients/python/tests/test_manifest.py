from __future__ import annotations

from pathlib import Path
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


def test_load_single_document(tmp_path):
    f = tmp_path / 'test.yaml'
    f.write_text("""
api_version: tropek/v1
kind: AssetType
metadata:
  name: vm
spec:
  is_default: true
""")
    docs = load_manifests(str(f))
    assert len(docs) == 1
    assert docs[0].kind == 'AssetType'
    assert docs[0].metadata['name'] == 'vm'
    assert docs[0].spec['is_default'] is True


def test_load_multi_document(tmp_path):
    f = tmp_path / 'test.yaml'
    f.write_text("""
api_version: tropek/v1
kind: AssetType
metadata:
  name: vm
spec:
  is_default: true
---
api_version: tropek/v1
kind: Asset
metadata:
  name: vm-01
spec:
  type_name: vm
""")
    docs = load_manifests(str(f))
    assert len(docs) == 2
    assert docs[0].kind == 'AssetType'
    assert docs[1].kind == 'Asset'


def test_load_directory(tmp_path):
    (tmp_path / 'a.yaml').write_text("""
api_version: tropek/v1
kind: AssetType
metadata:
  name: vm
spec:
  is_default: true
""")
    (tmp_path / 'b.yaml').write_text("""
api_version: tropek/v1
kind: Asset
metadata:
  name: vm-01
spec:
  type_name: vm
""")
    docs = load_manifests(str(tmp_path))
    assert len(docs) == 2


def test_topological_sort(tmp_path):
    f = tmp_path / 'test.yaml'
    f.write_text("""
api_version: tropek/v1
kind: Asset
metadata:
  name: vm-01
spec:
  type_name: vm
---
api_version: tropek/v1
kind: AssetType
metadata:
  name: vm
spec:
  is_default: true
""")
    docs = load_manifests(str(f))
    kinds = [d.kind for d in docs]
    assert kinds.index('AssetType') < kinds.index('Asset')


def test_rejects_missing_api_version(tmp_path):
    f = tmp_path / 'test.yaml'
    f.write_text("""
kind: AssetType
metadata:
  name: vm
spec:
  is_default: true
""")
    with pytest.raises(ValueError, match='api_version'):
        load_manifests(str(f))


def test_unknown_kind_raises(tmp_path: Path) -> None:
    """AssetSLOLink and AssetGroupSLOLink are no longer valid kinds."""
    f = tmp_path / 'bad.yaml'
    f.write_text("""
api_version: tropek/v1
kind: AssetSLOLink
metadata:
  name: my-link
spec:
  asset_name: my-asset
  slo_name: my-slo
  sli_name: my-sli
  data_source_name: my-ds
""")
    with pytest.raises(ValueError, match='unknown kind'):
        load_manifests(str(tmp_path))


def test_dry_run_creates_plan():
    """dry_run produces CREATE actions for missing entities."""
    client = MagicMock()
    client.asset_types.list.return_value = []  # no existing types

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
    client.asset_types.list.return_value = []  # triggers CREATE

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
    client.asset_types.create.assert_called_once_with('vm', is_default=True)


def test_apply_plan_is_pydantic_model() -> None:
    plan = ApplyPlan()
    assert isinstance(plan, BaseModel)
    plan.actions.append(PlanAction(operation='CREATE', kind='Asset', name='vm-01', reason='reason'))
    assert len(plan.actions) == 1
