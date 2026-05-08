"""Smoke test every TropekClient route against a live instance.

Assumes bootstrap manifests and seed_evaluations have already been applied.
Creates ephemeral resources (prefixed 'smoke-') and cleans them up.

Usage: uv run --directory clients/python python ../../dev_setup/stages/smoke_test_routes.py <api_url>
"""

from __future__ import annotations

import contextlib
import sys
import time
import traceback
from typing import Any

from tropek_client import TropekClient
from tropek_client.exceptions import TropekAPIError
from tropek_client.models import (
    AddMemberRequest,
    AddSubgroupRequest,
    AnnotationCategoryCreate,
    AnnotationCategoryUpdate,
    AnnotationCreate,
    AnnotationHide,
    AnnotationUpdate,
    AssetCreate,
    AssetGroupCreate,
    AssetGroupUpdate,
    AssetScope,
    AssetTypeCreate,
    AssetTypeUpdate,
    AssetUpdate,
    DataSourceCreate,
    DataSourceUpdate,
    InvalidateRequest,
    MetaSnapshotCreate,
    MetaValueInput,
    OverrideStatusRequest,
    PinBaselineRequest,
    ReEvaluateFromBaselineRequest,
    ReEvaluateFromDateRequest,
    ReEvaluateFromEvaluationRequest,
    SLIDefinitionCreate,
    SLOAssignmentUpsert,
    SLODefinitionCreate,
    SLOGroupAssignmentUpsert,
    SLOGroupCreate,
    SLOGroupUpdate,
    SLOObjectiveIn,
    SloSelector,
    SLOValidateRequest,
)

TERMINAL_STATUSES = {'completed', 'failed', 'partial'}

passed: list[str] = []
failed: list[tuple[str, str]] = []
skipped: list[tuple[str, str]] = []


def run(label: str, fn: Any) -> Any:
    """Run a test function, track pass/fail, return result or None."""
    try:
        result = fn()
        passed.append(label)
        print(f'  PASS  {label}')
        return result
    except Exception as exc:  # noqa: BLE001
        failed.append((label, str(exc)))
        print(f'  FAIL  {label}: {exc}')
        traceback.print_exc()
        return None


def skip(label: str, reason: str) -> None:
    """Record a skipped test."""
    skipped.append((label, reason))
    print(f'  SKIP  {label}: {reason}')


def poll_eval(client: TropekClient, eval_id: str, timeout: int = 30) -> Any:
    """Poll until evaluation reaches terminal status."""
    for _ in range(timeout):
        evaluation = client.evaluations.get(eval_id)
        if evaluation.status in TERMINAL_STATUSES:
            return evaluation
        time.sleep(1)
    raise TimeoutError(f'evaluation {eval_id} did not complete in {timeout}s')


# ---------------------------------------------------------------------------
# Test groups
# ---------------------------------------------------------------------------


def test_health(client: TropekClient) -> None:
    """Health endpoint."""
    print('\n--- health ---')
    result = run('health', lambda: client.health())
    assert result is not None


def test_asset_types(client: TropekClient) -> None:
    """asset_types: list, create, set_default, rename, delete."""
    print('\n--- asset_types ---')
    run('asset_types.list', lambda: client.asset_types.list())
    run('asset_types.create', lambda: client.asset_types.create(AssetTypeCreate(name='smoke-type')))
    run('asset_types.set_default', lambda: client.asset_types.set_default('smoke-type'))
    run(
        'asset_types.rename',
        lambda: client.asset_types.rename('smoke-type', AssetTypeUpdate(name='smoke-type-renamed')),
    )
    run('asset_types.delete', lambda: client.asset_types.delete('smoke-type-renamed'))


def test_assets(client: TropekClient) -> None:
    """assets: list, create, get, update, delete, tag_keys, tag_values."""
    print('\n--- assets ---')
    run('assets.list', lambda: client.assets.list())
    run(
        'assets.create',
        lambda: client.assets.create(AssetCreate(name='smoke-asset', type_name='vm', tags={'smoke': 'true'})),
    )
    run('assets.get', lambda: client.assets.get('smoke-asset'))
    run('assets.update', lambda: client.assets.update('smoke-asset', AssetUpdate(display_name='Smoke Asset Updated')))
    run('assets.tag_keys', lambda: client.assets.tag_keys())
    run('assets.tag_values', lambda: client.assets.tag_values('smoke'))
    run('assets.delete', lambda: client.assets.delete('smoke-asset'))


def test_asset_groups(client: TropekClient) -> None:
    """asset_groups: list, tree, create, get, update, add/remove member/subgroup."""
    print('\n--- asset_groups ---')
    run('asset_groups.list', lambda: client.asset_groups.list())
    run('asset_groups.tree', lambda: client.asset_groups.tree())

    client.assets.create(AssetCreate(name='smoke-grp-asset', type_name='vm'))
    run(
        'asset_groups.create',
        lambda: client.asset_groups.create(AssetGroupCreate(name='smoke-group', display_name='Smoke Group')),
    )
    run('asset_groups.get', lambda: client.asset_groups.get('smoke-group'))
    run(
        'asset_groups.update',
        lambda: client.asset_groups.update('smoke-group', AssetGroupUpdate(display_name='Smoke Group Updated')),
    )

    asset = client.assets.get('smoke-grp-asset')
    run(
        'asset_groups.add_member',
        lambda: client.asset_groups.add_member('smoke-group', AddMemberRequest(asset_id=str(asset.id))),
    )
    run('asset_groups.remove_member', lambda: client.asset_groups.remove_member('smoke-group', str(asset.id)))

    run('asset_groups.create(child)', lambda: client.asset_groups.create(AssetGroupCreate(name='smoke-child-group')))
    child = client.asset_groups.get('smoke-child-group')
    run(
        'asset_groups.add_subgroup',
        lambda: client.asset_groups.add_subgroup('smoke-group', AddSubgroupRequest(child_group_id=str(child.id))),
    )
    run('asset_groups.remove_subgroup', lambda: client.asset_groups.remove_subgroup('smoke-group', str(child.id)))

    # cleanup (asset_groups has no delete method — leave groups as-is)
    with contextlib.suppress(TropekAPIError):
        client.assets.delete('smoke-grp-asset')


def test_datasources(client: TropekClient) -> None:
    """datasources: list, create, get, update, delete, tag_keys, tag_values."""
    print('\n--- datasources ---')
    run('datasources.list', lambda: client.datasources.list())
    run('datasources.list(adapter_type)', lambda: client.datasources.list(adapter_type='mock'))
    run(
        'datasources.create',
        lambda: client.datasources.create(
            DataSourceCreate(name='smoke-ds', adapter_type='mock', adapter_url='http://mock:8081')
        ),
    )
    run('datasources.get', lambda: client.datasources.get('smoke-ds'))
    run(
        'datasources.update',
        lambda: client.datasources.update('smoke-ds', DataSourceUpdate(display_name='Smoke DS Updated')),
    )
    run('datasources.tag_keys', lambda: client.datasources.tag_keys())
    run('datasources.tag_values', lambda: client.datasources.tag_values('env'))
    run('datasources.delete', lambda: client.datasources.delete('smoke-ds'))


def test_slis(client: TropekClient) -> None:
    """slis: list, create, get, versions, new_version, delete, tag_keys, tag_values."""
    print('\n--- slis ---')
    run('slis.list', lambda: client.slis.list())
    run(
        'slis.create',
        lambda: client.slis.create(
            SLIDefinitionCreate(
                name='smoke-sli',
                adapter_type='mock',
                indicators={'p95': 'mock_query(p95)'},
                tags={'smoke': 'true'},
            )
        ),
    )
    run('slis.get', lambda: client.slis.get('smoke-sli'))
    run('slis.versions', lambda: client.slis.versions('smoke-sli'))
    run('slis.new_version', lambda: client.slis.new_version('smoke-sli', indicators={'p99': 'mock_query(p99)'}))
    run('slis.tag_keys', lambda: client.slis.tag_keys())
    run('slis.tag_values', lambda: client.slis.tag_values('smoke'))
    run('slis.delete', lambda: client.slis.delete('smoke-sli'))


def test_slos(client: TropekClient) -> None:
    """slos: list, create, get, versions, validate, new_version, delete, tag_keys, tag_values."""
    print('\n--- slos ---')
    objectives = [
        SLOObjectiveIn(sli='response_time_p99', pass_threshold=['<600'], warning_threshold=['<800']),
    ]
    run('slos.list', lambda: client.slos.list())
    run('slos.validate', lambda: client.slos.validate(SLOValidateRequest(objectives=objectives)))
    run(
        'slos.create',
        lambda: client.slos.create(
            SLODefinitionCreate(
                name='smoke-slo',
                objectives=objectives,
                sli_name='http-service-sli',
                tags={'smoke': 'true'},
            )
        ),
    )
    run('slos.get', lambda: client.slos.get('smoke-slo'))
    run('slos.versions', lambda: client.slos.versions('smoke-slo'))
    run('slos.new_version', lambda: client.slos.new_version('smoke-slo', total_score_pass_threshold=95.0))
    run('slos.tag_keys', lambda: client.slos.tag_keys())
    run('slos.tag_values', lambda: client.slos.tag_values('smoke'))
    run('slos.delete', lambda: client.slos.delete('smoke-slo'))


def test_slo_assignments(client: TropekClient) -> None:
    """slo_assignments: create_for_asset, list_for_asset, list_for_group, delete_for_asset."""
    print('\n--- slo_assignments ---')
    run('slo_assignments.list_for_asset', lambda: client.slo_assignments.list_for_asset('checkout-api'))
    run('slo_assignments.list_for_group', lambda: client.slo_assignments.list_for_group('core-services'))

    slo = client.slos.get('http-availability-slo')
    slo_def_id = str(slo.id)

    client.assets.create(AssetCreate(name='smoke-assign-asset', type_name='vm'))
    run(
        'slo_assignments.create_for_asset',
        lambda: client.slo_assignments.create_for_asset(
            'smoke-assign-asset', slo_def_id, SLOAssignmentUpsert(data_source_name='prometheus-local')
        ),
    )
    run(
        'slo_assignments.delete_for_asset',
        lambda: client.slo_assignments.delete_for_asset('smoke-assign-asset', slo_def_id),
    )
    client.assets.delete('smoke-assign-asset')


def test_slo_groups(client: TropekClient) -> None:
    """slo_groups: list, create, get, update, delete."""
    print('\n--- slo_groups ---')
    run('slo_groups.list', lambda: client.slo_groups.list())

    existing = client.slo_groups.get('app-x-plugins')
    run('slo_groups.get', lambda: existing)

    # Use the same template SLO pattern as bootstrap data
    template_slo = client.slos.get('plugin/$__gen_process_name')
    run(
        'slo_groups.create',
        lambda: client.slo_groups.create(
            SLOGroupCreate(
                name='smoke-slo-group',
                template_slo_name=template_slo.name,
                template_slo_version=template_slo.version,
                gen_variables={'process_name': ['smoke-a', 'smoke-b']},
            )
        ),
    )
    run(
        'slo_groups.update',
        lambda: client.slo_groups.update('smoke-slo-group', SLOGroupUpdate(display_name='Smoke Updated')),
    )

    run('slo_groups.delete', lambda: client.slo_groups.delete('smoke-slo-group'))


def test_slo_group_assignments(client: TropekClient) -> None:
    """slo_group_assignments: create_for_asset, list_for_asset, list_for_group, delete_for_asset."""
    print('\n--- slo_group_assignments ---')
    run('slo_group_assignments.list_for_group', lambda: client.slo_group_assignments.list_for_group('core-services'))

    client.assets.create(AssetCreate(name='smoke-sga-asset', type_name='vm'))
    run(
        'slo_group_assignments.create_for_asset',
        lambda: client.slo_group_assignments.create_for_asset(
            'smoke-sga-asset', 'app-x-plugins', SLOGroupAssignmentUpsert(data_source_name='prometheus-local')
        ),
    )
    run('slo_group_assignments.list_for_asset', lambda: client.slo_group_assignments.list_for_asset('smoke-sga-asset'))
    run(
        'slo_group_assignments.delete_for_asset',
        lambda: client.slo_group_assignments.delete_for_asset('smoke-sga-asset', 'app-x-plugins'),
    )
    client.assets.delete('smoke-sga-asset')


def test_evaluations(client: TropekClient) -> None:
    """evaluations: list, get, trigger, trigger_batch, invalidate, restore, pin, unpin, override, names."""
    print('\n--- evaluations ---')
    run('evaluations.list', lambda: client.evaluations.list())
    run('evaluations.list(filters)', lambda: client.evaluations.list(asset_name='checkout-api', limit=5))

    evals = client.evaluations.list(asset_name='checkout-api')
    if not evals.items:
        skip('evaluations (detail tests)', 'no evaluations found')
        return

    eval_id = str(evals.items[0].id)
    run('evaluations.get', lambda: client.evaluations.get(eval_id))
    run('evaluations.names', lambda: client.evaluations.names(asset_name='checkout-api'))

    # invalidate + restore
    run(
        'evaluations.invalidate',
        lambda: client.evaluations.invalidate(eval_id, InvalidateRequest(invalidation_note='smoke test')),
    )
    run('evaluations.restore', lambda: client.evaluations.restore(eval_id))

    # unpin (if pinned from prior run)
    with contextlib.suppress(TropekAPIError):
        detail = client.evaluations.get(eval_id)
        if detail.baseline_pinned_at:
            client.evaluations.unpin_baseline(eval_id)

    # pin + unpin
    run(
        'evaluations.pin_baseline',
        lambda: client.evaluations.pin_baseline(eval_id, PinBaselineRequest(reason='smoke test', author='smoke')),
    )
    run('evaluations.unpin_baseline', lambda: client.evaluations.unpin_baseline(eval_id))

    # override + restore
    run(
        'evaluations.override_status',
        lambda: client.evaluations.override_status(
            eval_id, OverrideStatusRequest(new_result='fail', reason='smoke test', author='smoke')
        ),
    )
    run('evaluations.restore_override', lambda: client.evaluations.restore_override(eval_id))

    # re-evaluate from date (dry run)
    run(
        'evaluations.re_evaluate_from_date',
        lambda: client.evaluations.re_evaluate_from_date(
            ReEvaluateFromDateRequest(
                scope=AssetScope(asset_name='checkout-api'),
                from_date='2026-03-15T00:00:00Z',
                selector=SloSelector(slo_name='http-availability-slo'),
                dry_run=True,
                pin_strategy='ignore_pin',
            )
        ),
    )

    # re-evaluate from baseline (dry run) — pin first
    client.evaluations.pin_baseline(eval_id, PinBaselineRequest(reason='smoke baseline', author='smoke'))
    run(
        'evaluations.re_evaluate_from_baseline',
        lambda: client.evaluations.re_evaluate_from_baseline(
            ReEvaluateFromBaselineRequest(
                scope=AssetScope(asset_name='checkout-api'),
                selector=SloSelector(slo_name='http-availability-slo'),
                dry_run=True,
            )
        ),
    )
    client.evaluations.unpin_baseline(eval_id)

    # re-evaluate from evaluation (dry run)
    run(
        'evaluations.re_evaluate_from_evaluation',
        lambda: client.evaluations.re_evaluate_from_evaluation(
            eval_id,
            ReEvaluateFromEvaluationRequest(
                scope=AssetScope(asset_name='checkout-api'),
                selector=SloSelector(slo_name='http-availability-slo'),
                dry_run=True,
            ),
        ),
    )


def test_annotations(client: TropekClient) -> None:
    """annotations: list, create, create_for_run, update, hide."""
    print('\n--- annotations ---')
    evals = client.evaluations.list(asset_name='checkout-api')
    if not evals.items:
        skip('annotations', 'no evaluations')
        return

    eval_id = str(evals.items[0].id)
    run_id = str(evals.items[0].evaluation_id)
    categories = client.annotation_categories.list()
    category_id = str(categories[0].id) if categories else None

    ann = run(
        'annotations.create',
        lambda: client.annotations.create(
            eval_id, AnnotationCreate(content='smoke annotation', author='smoke', category_id=category_id)
        ),
    )
    if ann is None:
        return
    ann_id = str(ann.id)
    run('annotations.list', lambda: client.annotations.list(eval_id))
    run(
        'annotations.update',
        lambda: client.annotations.update(eval_id, ann_id, AnnotationUpdate(content='smoke updated')),
    )

    run_ann = run(
        'annotations.create_for_run',
        lambda: client.annotations.create_for_run(
            run_id, AnnotationCreate(content='smoke run annotation', author='smoke', category_id=category_id)
        ),
    )

    run(
        'annotations.hide',
        lambda: client.annotations.hide(eval_id, ann_id, AnnotationHide(reason='smoke cleanup', author='smoke')),
    )
    if run_ann:
        client.annotations.hide(run_id, str(run_ann.id), AnnotationHide(reason='cleanup', author='smoke'))


def test_annotation_categories(client: TropekClient) -> None:
    """annotation_categories: list, create, update, delete."""
    print('\n--- annotation_categories ---')
    run('annotation_categories.list', lambda: client.annotation_categories.list())
    cat = run(
        'annotation_categories.create',
        lambda: client.annotation_categories.create(
            AnnotationCategoryCreate(name='smoke-category', label='Smoke', color='red')
        ),
    )
    if cat is None:
        return
    cat_id = str(cat.id)
    run(
        'annotation_categories.update',
        lambda: client.annotation_categories.update(cat_id, AnnotationCategoryUpdate(color='green')),
    )
    run('annotation_categories.delete', lambda: client.annotation_categories.delete(cat_id))


def test_trend(client: TropekClient) -> None:
    """trend: by_eval, by_asset."""
    print('\n--- trend ---')
    evals = client.evaluations.list(asset_name='checkout-api', slo_name='http-availability-slo')
    if not evals.items:
        skip('trend', 'no evaluations')
        return

    eval_detail = client.evaluations.get(str(evals.items[0].id))
    if not eval_detail.indicator_results:
        skip('trend', 'no indicator results')
        return

    metric = eval_detail.indicator_results[0].metric
    eval_id = str(evals.items[0].id)

    run(
        'trend.by_eval',
        lambda: client.trend.by_eval(eval_id, metric, '2026-03-14T00:00:00Z', to='2026-03-17T00:00:00Z'),
    )
    run(
        'trend.by_asset',
        lambda: client.trend.by_asset(
            'checkout-api', 'http-availability-slo', metric, '2026-03-14T00:00:00Z', to='2026-03-17T00:00:00Z'
        ),
    )


def test_heatmap(client: TropekClient) -> None:
    """heatmap: grouped, flat."""
    print('\n--- heatmap ---')
    run('heatmap.grouped', lambda: client.heatmap.grouped('checkout-api'))
    run('heatmap.flat', lambda: client.heatmap.flat('checkout-api'))
    run('heatmap.grouped(eval_name)', lambda: client.heatmap.grouped('checkout-api', eval_name='load-test'))

    def _assert_change_points_scoped_per_slo() -> None:
        """Verify that SLOs sharing the same metric get independent CP sets.

        laptop-user-01 has 4 Office SLOs (Word/Excel/Outlook/PowerPoint) that
        all evaluate process_cpu_pct, process_memory_mb, process_handles.
        The mock adapter serves per-process_name data with CPs at different
        hours, so the detected change points should differ across SLO groups.
        Before the fix for #15, every SLO received a collapsed CP set keyed
        only by metric_name.
        """
        heatmap = client.heatmap.grouped('laptop-user-01')
        office_slo_names = {group.slo_name for group in heatmap.groups if group.slo_name.startswith('office-')}
        min_office_slos = 2
        assert len(office_slo_names) >= min_office_slos, (
            f'Expected >= {min_office_slos} Office SLO groups, got {len(office_slo_names)}: {office_slo_names}'
        )
        # Collect change points per Office SLO group, then drop groups with none
        change_points_by_slo = {
            group.slo_name: [cell.change_point for cell in group.cells if cell.change_point is not None]
            for group in heatmap.groups
            if group.slo_name in office_slo_names
        }
        change_points_by_slo = {
            slo_name: change_points for slo_name, change_points in change_points_by_slo.items() if change_points
        }
        if len(change_points_by_slo) < min_office_slos:
            return
        # Each SLO should have its own distinct CP set — if they're all
        # identical, the lookup is collapsing across SLOs (the #15 bug).
        per_slo_change_points = list(change_points_by_slo.values())
        all_identical = all(cp_set == per_slo_change_points[0] for cp_set in per_slo_change_points[1:])
        assert not all_identical, (
            f'All {len(per_slo_change_points)} Office SLO groups on laptop-user-01 have '
            f'identical change point sets — CP lookup is likely not scoped '
            f'by slo_name'
        )

    run('heatmap.cp_scoped_per_slo', _assert_change_points_scoped_per_slo)


def test_timeline(client: TropekClient) -> None:
    """timeline: get, summary."""
    print('\n--- timeline ---')
    asset = client.assets.get('checkout-api')
    asset_id = str(asset.id)
    run(
        'timeline.get',
        lambda: client.timeline.get(asset_id, from_='2026-03-14T00:00:00Z', to='2026-03-17T00:00:00Z'),
    )
    run(
        'timeline.summary',
        lambda: client.timeline.summary(asset_id, from_='2026-03-14T00:00:00Z', to='2026-03-17T00:00:00Z'),
    )


def test_configuration(client: TropekClient) -> None:
    """configuration: list, get, update."""
    print('\n--- configuration ---')
    configs = run('configuration.list', lambda: client.configuration.list())
    if not configs:
        skip('configuration (get/update)', 'no configuration entries')
        return

    config_name = configs[0].name
    original_value = configs[0].value
    run('configuration.get', lambda: client.configuration.get(config_name))
    run('configuration.update', lambda: client.configuration.update(config_name, original_value))


def test_meta(client: TropekClient) -> None:
    """meta: create_snapshot, list_snapshots, get_snapshot, delete_snapshot."""
    print('\n--- meta ---')
    asset = client.assets.get('checkout-api')
    asset_id = str(asset.id)
    created = run(
        'meta.create_snapshot',
        lambda: client.meta.create_snapshot(
            asset_id,
            MetaSnapshotCreate(
                source='smoke-test',
                observed_at='2026-03-15T12:00:00Z',
                values=[MetaValueInput(label_path=['version'], value='v1.2.3')],
            ),
        ),
    )
    run(
        'meta.list_snapshots',
        lambda: client.meta.list_snapshots(asset_id),
    )
    snapshot_id = str(created.snapshot_id) if created else None
    if snapshot_id:
        run(
            'meta.get_snapshot',
            lambda: client.meta.get_snapshot(asset_id, snapshot_id),
        )
        run(
            'meta.delete_snapshot',
            lambda: client.meta.delete_snapshot(asset_id, snapshot_id),
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run all smoke tests and print summary."""
    if len(sys.argv) != 2:  # noqa: PLR2004
        print(f'usage: {sys.argv[0]} <api_url>', file=sys.stderr)
        sys.exit(1)

    client = TropekClient(sys.argv[1])

    test_health(client)
    test_asset_types(client)
    test_assets(client)
    test_asset_groups(client)
    test_datasources(client)
    test_slis(client)
    test_slos(client)
    test_slo_assignments(client)
    test_slo_groups(client)
    test_slo_group_assignments(client)
    test_evaluations(client)
    test_annotations(client)
    test_annotation_categories(client)
    test_trend(client)
    test_heatmap(client)
    test_timeline(client)
    test_configuration(client)
    test_meta(client)

    print(f'\n{"=" * 60}')
    print(f'PASSED: {len(passed)}')
    print(f'FAILED: {len(failed)}')
    print(f'SKIPPED: {len(skipped)}')
    if failed:
        print('\nFailures:')
        for label, error in failed:
            print(f'  {label}: {error}')
    if skipped:
        print('\nSkipped:')
        for label, reason in skipped:
            print(f'  {label}: {reason}')
    print(f'{"=" * 60}')

    if failed:
        sys.exit(1)


if __name__ == '__main__':
    main()
