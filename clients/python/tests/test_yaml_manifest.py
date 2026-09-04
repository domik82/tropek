from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, call

import pytest
from pydantic import BaseModel
from tropek_client.manifest import (
    ApplyPlan,
    ManifestDocument,
    PlanAction,
    _update,
    _validate_doc_refs,
    dry_run,
    load_manifests,
)
from tropek_client.manifest import (
    apply as do_apply,
)
from tropek_client.models import (
    AssetTypeCreate,
    ComparisonConfigRead,
    DisplayGroupCreate,
    DisplayGroupMemberAdd,
    DisplayGroupRead,
    SLODefinitionRead,
    SLOObjectiveRead,
)
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


def test_slo_display_group_kind_loads_and_sorts_after_slo():
    """SLODisplayGroup is a recognized kind and is sorted after SLO (it references SLO names)."""
    docs = load_manifests(str(MANIFESTS_DIR / 'slo_display_group_order.yaml'))
    kinds = [d.kind for d in docs]
    assert 'SLODisplayGroup' in kinds
    assert kinds.index('SLO') < kinds.index('SLODisplayGroup')


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


def test_meta_snapshot_manifest_loads():
    docs = load_manifests(str(MANIFESTS_DIR / 'meta_snapshot.yaml'))
    meta_docs = [d for d in docs if d.kind == 'MetaSnapshot']
    assert len(meta_docs) == 1
    assert meta_docs[0].metadata['asset'] == 'checkout-api'
    assert len(meta_docs[0].spec['snapshots']) == 1


def test_dry_run_creates_display_group_when_missing():
    """A SLODisplayGroup not yet in Tropek plans as CREATE."""
    client = MagicMock()
    client.display_groups.list.return_value = []

    docs = [
        ManifestDocument(
            api_version='tropek/v1',
            kind='SLODisplayGroup',
            metadata={'name': 'web-tier'},
            spec={'members': ['checkout-api/latency']},
        )
    ]
    plan = dry_run(client, docs)
    assert len(plan.actions) == 1
    assert plan.actions[0].operation == 'CREATE'
    assert plan.actions[0].name == 'web-tier'


def test_dry_run_skips_existing_display_group():
    """An existing SLODisplayGroup always plans as SKIP — member sync is not implemented."""
    client = MagicMock()
    existing = DisplayGroupRead(
        id=uuid.UUID('00000000-0000-0000-0000-000000000001'),
        name='web-tier',
        display_name=None,
        parent_id=None,
        sort_order=0,
        created_at=datetime.now(UTC),
    )
    client.display_groups.list.return_value = [existing]

    docs = [
        ManifestDocument(
            api_version='tropek/v1',
            kind='SLODisplayGroup',
            metadata={'name': 'web-tier'},
            spec={'members': ['checkout-api/latency', 'checkout-api/error-rate']},
        )
    ]
    plan = dry_run(client, docs)
    assert plan.actions[0].operation == 'SKIP'
    assert plan.actions[0].reason == 'already exists, no changes'


def test_apply_creates_display_group_with_members():
    """apply() creates the group, then adds every member in spec order."""
    client = MagicMock()
    client.display_groups.list.return_value = []

    docs = [
        ManifestDocument(
            api_version='tropek/v1',
            kind='SLODisplayGroup',
            metadata={'name': 'web-tier', 'display_name': 'web-tier'},
            spec={'members': ['checkout-api/latency', 'checkout-api/error-rate']},
        )
    ]
    result = do_apply(client, docs)
    assert result.created == 1
    assert result.failed == 0
    client.display_groups.create.assert_called_once_with(
        DisplayGroupCreate(name='web-tier', display_name='web-tier', parent_id=None, sort_order=0)
    )
    assert client.display_groups.add_member.call_args_list == [
        call('web-tier', DisplayGroupMemberAdd(slo_name='checkout-api/latency')),
        call('web-tier', DisplayGroupMemberAdd(slo_name='checkout-api/error-rate')),
    ]


def test_apply_resolves_parent_name_to_parent_id():
    """A child group's `parent_name` is resolved to the parent's id via client-side list() filtering."""
    client = MagicMock()
    parent = DisplayGroupRead(
        id=uuid.UUID('00000000-0000-0000-0000-000000000002'),
        name='platform',
        display_name='Platform',
        parent_id=None,
        sort_order=0,
        created_at=datetime.now(UTC),
    )
    client.display_groups.list.return_value = [parent]

    docs = [
        ManifestDocument(
            api_version='tropek/v1',
            kind='SLODisplayGroup',
            metadata={'name': 'web-tier'},
            spec={'parent_name': 'platform', 'members': []},
        )
    ]
    do_apply(client, docs)
    client.display_groups.create.assert_called_once_with(
        DisplayGroupCreate(name='web-tier', display_name=None, parent_id=parent.id, sort_order=0)
    )


def test_apply_fails_when_parent_display_group_missing():
    """Applying a child before its parent exists is a reported failure, not a silent parent_id=None."""
    client = MagicMock()
    client.display_groups.list.return_value = []

    docs = [
        ManifestDocument(
            api_version='tropek/v1',
            kind='SLODisplayGroup',
            metadata={'name': 'web-tier'},
            spec={'parent_name': 'platform', 'members': []},
        )
    ]
    result = do_apply(client, docs)
    assert result.failed == 1
    assert result.created == 0
    assert "parent 'platform' not found" in result.errors[0].error


def test_update_display_group_is_a_no_op():
    """Mirrors 'AssetGroup': updates never touch an already-existing display group."""
    client = MagicMock()
    doc = ManifestDocument(
        api_version='tropek/v1',
        kind='SLODisplayGroup',
        metadata={'name': 'web-tier'},
        spec={'members': ['checkout-api/latency']},
    )
    _update(client, doc)
    client.display_groups.create.assert_not_called()
    client.display_groups.add_member.assert_not_called()


def test_validate_warns_on_unknown_display_group_member():
    """A SLODisplayGroup member SLO not present in the manifest set is a warning, not an error."""
    docs = [
        ManifestDocument(
            api_version='tropek/v1',
            kind='SLODisplayGroup',
            metadata={'name': 'web-tier'},
            spec={'members': ['checkout-api/latency']},
        )
    ]
    errors = []
    names_by_kind: dict[str, set[str]] = {}
    for doc in docs:
        names_by_kind.setdefault(doc.kind, set()).add(doc.metadata.get('name', ''))
    for doc in docs:
        _validate_doc_refs(doc, names_by_kind, errors)
    assert len(errors) == 1
    assert "SLODisplayGroup 'web-tier'" in errors[0]
    assert "SLO 'checkout-api/latency'" in errors[0]


def test_validate_warns_on_unknown_display_group_parent():
    """A `parent_name` pointing at a SLODisplayGroup not present in the manifest set is a warning."""
    docs = [
        ManifestDocument(
            api_version='tropek/v1',
            kind='SLODisplayGroup',
            metadata={'name': 'web-tier'},
            spec={'parent_name': 'platform', 'members': []},
        )
    ]
    errors = []
    names_by_kind: dict[str, set[str]] = {}
    for doc in docs:
        names_by_kind.setdefault(doc.kind, set()).add(doc.metadata.get('name', ''))
    for doc in docs:
        _validate_doc_refs(doc, names_by_kind, errors)
    assert len(errors) == 1
    assert "parent SLODisplayGroup 'platform'" in errors[0]


def test_validate_no_warning_when_parent_and_members_present():
    """No warning when the referenced parent and member SLO are both in the same manifest set."""
    docs = [
        ManifestDocument(
            api_version='tropek/v1',
            kind='SLODisplayGroup',
            metadata={'name': 'platform'},
            spec={'members': []},
        ),
        ManifestDocument(
            api_version='tropek/v1',
            kind='SLO',
            metadata={'name': 'checkout-api/latency'},
            spec={'objectives': []},
        ),
        ManifestDocument(
            api_version='tropek/v1',
            kind='SLODisplayGroup',
            metadata={'name': 'web-tier'},
            spec={'parent_name': 'platform', 'members': ['checkout-api/latency']},
        ),
    ]
    errors = []
    names_by_kind: dict[str, set[str]] = {}
    for doc in docs:
        names_by_kind.setdefault(doc.kind, set()).add(doc.metadata.get('name', ''))
    for doc in docs:
        _validate_doc_refs(doc, names_by_kind, errors)
    assert errors == []


def _slo_read(**overrides: object) -> SLODefinitionRead:
    """Build an SLODefinitionRead matching the manifest doc built by _slo_doc(), for diff tests."""
    defaults = {
        'id': uuid.UUID('00000000-0000-0000-0000-000000000010'),
        'name': 'checkout-api/latency',
        'display_name': None,
        'version': 1,
        'comparable_from_version': 1,
        'active': True,
        'objectives': [
            SLOObjectiveRead(
                sli='latency.mean',
                display_name='latency',
                pass_threshold=['<=500'],
                warning_threshold=[],
                weight=1,
                key_sli=False,
                sort_order=0,
                change_point=None,
            )
        ],
        'total_score_pass_threshold': 90.0,
        'total_score_warning_threshold': 75.0,
        'comparison': ComparisonConfigRead(),
        'tags': {},
        'variables': {},
        'kind': 'standard',
        'created_at': datetime.now(UTC),
    }
    return SLODefinitionRead.model_validate(defaults | overrides)


def _slo_doc(**spec_overrides: object) -> ManifestDocument:
    """Build the manifest doc shape the pipeline actually emits: omitted keys, no read-only fields."""
    spec = {
        'objectives': [
            {
                'sli': 'latency.mean',
                'display_name': 'latency',
                'pass_threshold': ['<=500'],
                'warning_threshold': [],
                'weight': 1,
                'change_point': {'enabled': True},
            }
        ],
        'sli_name': 'latency',
    }
    return ManifestDocument(
        api_version='tropek/v1',
        kind='SLO',
        metadata={'name': 'checkout-api/latency'},
        spec=spec | spec_overrides,
    )


def test_an_unchanged_slo_plans_as_skip_not_a_new_version():
    """The bug this fixes: an identical manifest re-applied minted a new SLO version every time.

    The manifest omits key_sli/sort_order and sends change_point as an input-shaped override, while
    the API read fills key_sli, adds sort_order, and returns change_point resolved-or-null. Comparing
    the two representations raw is always unequal.
    """
    client = MagicMock()
    client.slos.get.return_value = _slo_read()
    plan = dry_run(client, [_slo_doc()])
    assert plan.actions[0].operation == 'SKIP', f'expected SKIP, got {plan.actions[0]}'
    assert plan.actions[0].reason == 'already exists, no changes'


def test_a_manifest_omitting_total_score_matches_the_api_defaults():
    """`.get('pass_threshold')` returned None against the API's 90.0 — the create path's own default."""
    client = MagicMock()
    client.slos.get.return_value = _slo_read()
    plan = dry_run(client, [_slo_doc()])
    assert plan.actions[0].operation == 'SKIP'


def test_a_manifest_omitting_comparison_matches_a_default_comparison_read():
    """`{} != ComparisonConfigRead(...)` compared a dict to a model, which is never equal."""
    client = MagicMock()
    client.slos.get.return_value = _slo_read(comparison=ComparisonConfigRead())
    plan = dry_run(client, [_slo_doc()])
    assert plan.actions[0].operation == 'SKIP'


def test_a_genuinely_changed_threshold_still_plans_as_update():
    """The fix must not blunt the diff: a real objective change is still detected."""
    client = MagicMock()
    client.slos.get.return_value = _slo_read()
    changed = _slo_doc(
        objectives=[
            {
                'sli': 'latency.mean',
                'display_name': 'latency',
                'pass_threshold': ['<=250'],
                'warning_threshold': [],
                'weight': 1,
            }
        ]
    )
    plan = dry_run(client, [changed])
    assert plan.actions[0].operation == 'UPDATE'


def test_a_genuinely_changed_total_score_still_plans_as_update():
    client = MagicMock()
    client.slos.get.return_value = _slo_read()
    plan = dry_run(client, [_slo_doc(total_score={'pass_threshold': 99.0, 'warning_threshold': 75.0})])
    assert plan.actions[0].operation == 'UPDATE'


def test_an_added_objective_still_plans_as_update():
    """Count changes matter even when every shared field is identical."""
    client = MagicMock()
    client.slos.get.return_value = _slo_read()
    two = _slo_doc(
        objectives=[
            {'sli': 'latency.mean', 'display_name': 'latency', 'pass_threshold': ['<=500'], 'weight': 1},
            {'sli': 'error_rate.mean', 'display_name': 'error-rate', 'pass_threshold': ['<=1'], 'weight': 1},
        ]
    )
    plan = dry_run(client, [two])
    assert plan.actions[0].operation == 'UPDATE'


def test_a_change_point_edit_is_not_detected_while_the_read_path_returns_null():
    """Known limitation, pinned deliberately: SLOObjectiveRead.change_point is structurally always
    None (schema field `change_point` vs ORM attribute `change_point_config`), so there is nothing to
    compare a manifest's change_point block against. Comparing it anyway would make every SLO differ.
    Revisit when the read path is fixed — this test should then be inverted to expect UPDATE.
    """
    client = MagicMock()
    client.slos.get.return_value = _slo_read()
    changed = _slo_doc(
        objectives=[
            {
                'sli': 'latency.mean',
                'display_name': 'latency',
                'pass_threshold': ['<=500'],
                'warning_threshold': [],
                'weight': 1,
                'change_point': {'enabled': False},
            }
        ]
    )
    plan = dry_run(client, [changed])
    assert plan.actions[0].operation == 'SKIP'
