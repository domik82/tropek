from __future__ import annotations

from tropek_client.manifest import ManifestDocument, load_manifests


def test_load_single_document(tmp_path):
    f = tmp_path / "test.yaml"
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
    assert docs[0].kind == "AssetType"
    assert docs[0].metadata["name"] == "vm"
    assert docs[0].spec["is_default"] is True


def test_load_multi_document(tmp_path):
    f = tmp_path / "test.yaml"
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
    assert docs[0].kind == "AssetType"
    assert docs[1].kind == "Asset"


def test_load_directory(tmp_path):
    (tmp_path / "a.yaml").write_text("""
api_version: tropek/v1
kind: AssetType
metadata:
  name: vm
spec:
  is_default: true
""")
    (tmp_path / "b.yaml").write_text("""
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
    f = tmp_path / "test.yaml"
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
    assert kinds.index("AssetType") < kinds.index("Asset")


def test_rejects_missing_api_version(tmp_path):
    f = tmp_path / "test.yaml"
    f.write_text("""
kind: AssetType
metadata:
  name: vm
spec:
  is_default: true
""")
    import pytest

    with pytest.raises(ValueError, match="api_version"):
        load_manifests(str(f))


def test_validate_cross_references(tmp_path):
    """Cross-reference warnings are returned for missing refs within manifest."""
    from tropek_client.manifest import validate_manifests

    f = tmp_path / "test.yaml"
    f.write_text("""
api_version: tropek/v1
kind: AssetSLOLink
metadata:
  name: my-link
spec:
  asset_name: vm-01
  slo_name: missing-slo
  sli_name: missing-sli
  data_source_name: missing-ds
""")
    errors = validate_manifests(str(f))
    assert len(errors) == 3
    assert all("WARNING" in e for e in errors)


def test_dry_run_creates_plan():
    """dry_run produces CREATE actions for missing entities."""
    from unittest.mock import MagicMock

    from tropek_client.manifest import dry_run

    client = MagicMock()
    client.asset_types.list.return_value = []  # no existing types

    docs = [
        ManifestDocument(
            api_version="tropek/v1",
            kind="AssetType",
            metadata={"name": "vm"},
            spec={"is_default": True},
        )
    ]
    plan = dry_run(client, docs)
    assert len(plan.actions) == 1
    assert plan.actions[0].operation == "CREATE"
    assert plan.actions[0].name == "vm"


def test_apply_creates_entity():
    """apply calls create on the client for CREATE actions."""
    from unittest.mock import MagicMock

    from tropek_client.manifest import apply as do_apply

    client = MagicMock()
    client.asset_types.list.return_value = []  # triggers CREATE

    docs = [
        ManifestDocument(
            api_version="tropek/v1",
            kind="AssetType",
            metadata={"name": "vm"},
            spec={"is_default": True},
        )
    ]
    result = do_apply(client, docs)
    assert result.created == 1
    assert result.failed == 0
    client.asset_types.create.assert_called_once_with("vm", is_default=True)
