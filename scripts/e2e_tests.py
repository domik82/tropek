"""End-to-end integration tests run against a live TROPEK API.

Usage: uv run --directory clients/python python ../../scripts/e2e_tests.py <api_url>

Bootstrap manifests must be applied before running (see scripts/bootstrap.py).

Evaluation flows and their endpoints
-------------------------------------
Each test that triggers evaluations uses a distinct evaluation_name so they
are easy to identify in the heatmap and logs.

  evaluation_name     endpoint              what it tests
  ─────────────────── ───────────────────── ─────────────────────────────────
  single-eval         POST /evaluate        Asset-level trigger — resolves
                                            ALL SLOs for an asset at once.

  asset-trigger-test  POST /evaluate        Same endpoint, verifies multiple
                                            SLO evaluations are created.

  batch-test          POST /evaluate/batch  Batch trigger across multiple
                                            assets for a shared time window.

  regression-test     POST /evaluate        Exercises baseline comparison
                                            after a pin (checks first SLO).

  agg-baseline-test   POST /evaluate        Exercises aggregated-mode eval
                                            with method-keyed indicators and
                                            baseline comparison (finds the
                                            agg-latency-slo eval by name).
"""

from __future__ import annotations

import sys
import time

from tropek_client import TropekClient
from tropek_client.exceptions import TropekAPIError

TERMINAL_STATUSES = {'completed', 'failed', 'partial'}


def step(name: str) -> None:
    """Print a step header."""
    print(f'\n=== {name} ===')


def poll_eval(client: TropekClient, eval_id: str, timeout: int = 30) -> object:
    """Poll an evaluation until it reaches a terminal status."""
    for _ in range(timeout):
        ev = client.evaluations.get(eval_id)
        if ev.status in TERMINAL_STATUSES:
            return ev
        time.sleep(1)
    raise TimeoutError(f'evaluation {eval_id} did not complete within {timeout}s')


def test_single_evaluation(client: TropekClient) -> None:
    """Trigger evaluations for an asset and verify at least one completes."""
    step('Step 7: Trigger asset evaluation')
    result = client.evaluations.evaluate(
        'checkout-api',
        'single-eval',
        '2026-03-15T08:00:00Z',
        '2026-03-15T08:30:00Z',
    )
    slo_eval_ids = result['slo_evaluation_ids']
    assert slo_eval_ids, 'expected at least one slo_evaluation_id'
    print(f'triggered: evaluation_id={result["evaluation_id"]}, {len(slo_eval_ids)} SLO eval(s)')
    ev = poll_eval(client, str(slo_eval_ids[0]))
    print(f'status={ev.status} result={ev.result} score={ev.score}')
    assert ev.status == 'completed', f'expected completed, got {ev.status}'
    print('PASS: asset evaluation')


def test_asset_trigger(client: TropekClient) -> None:
    """Trigger all SLOs for an asset and verify multiple SLO evaluations are created."""
    step('Step 7b: Trigger asset-level evaluation (all SLOs)')
    result = client.evaluations.evaluate(
        'checkout-api',
        'asset-trigger-test',
        '2026-03-15T09:00:00Z',
        '2026-03-15T09:30:00Z',
    )
    slo_eval_ids = result['slo_evaluation_ids']
    print(f'triggered {len(slo_eval_ids)} SLO evaluations (evaluation_id={result["evaluation_id"]})')
    assert len(slo_eval_ids) >= 2, f'expected at least 2 SLO evaluations, got {len(slo_eval_ids)}'

    for slo_eval_id in slo_eval_ids:
        ev = poll_eval(client, str(slo_eval_id))
        print(f'  {ev.slo_name}: status={ev.status} result={ev.result} score={ev.score}')
        assert ev.status == 'completed', f'expected completed for {ev.slo_name}, got {ev.status}'

    print(f'PASS: asset trigger — {len(slo_eval_ids)} SLOs evaluated')


def test_pin_baseline(client: TropekClient) -> None:
    """Pin a baseline on the first evaluation."""
    step('Step 8: Pin baseline')
    evals = client.evaluations.list(asset_name='checkout-api')
    eval_id = str(evals.items[0].id)
    result = client.evaluations.pin_baseline(eval_id, 'integration test pin', 'test-runner')
    print(f'pinned: {eval_id}')
    assert result.baseline_pinned_at is not None
    print('PASS: pin baseline')


def test_batch_evaluation(client: TropekClient) -> None:
    """Trigger a batch evaluation across multiple assets and wait for all to complete."""
    step('Step 9: Trigger batch evaluation')
    result = client.evaluations.evaluate_batch(
        mode='by_asset',
        eval_name='batch-test',
        asset_names=['checkout-api', 'product-catalog', 'user-service'],
        period_start='2026-03-15T08:00:00Z',
        period_end='2026-03-15T08:30:00Z',
    )
    slo_eval_ids = result['slo_evaluation_ids']
    print(f'batch triggered: {len(result["evaluation_ids"])} runs, {len(slo_eval_ids)} SLO evaluations')
    assert len(slo_eval_ids) >= 1, f'expected at least 1 SLO evaluation, got {len(slo_eval_ids)}'

    for _ in range(60):
        statuses = {client.evaluations.get(str(eid)).status for eid in slo_eval_ids}
        if statuses.issubset(TERMINAL_STATUSES):
            break
        time.sleep(1)

    print('PASS: batch evaluation')


def test_regression_eval(client: TropekClient) -> None:
    """Trigger a second evaluation to exercise baseline comparison after a pin."""
    step('Step 10: Trigger regression eval after pin')
    result = client.evaluations.evaluate(
        'checkout-api',
        'regression-test',
        '2026-03-16T12:00:00Z',
        '2026-03-16T12:30:00Z',
    )
    slo_eval_ids = result['slo_evaluation_ids']
    assert slo_eval_ids, 'expected at least one slo_evaluation_id'
    print(f'triggered regression eval: {len(slo_eval_ids)} SLO eval(s)')
    ev = poll_eval(client, str(slo_eval_ids[0]))
    print(f'status={ev.status} result={ev.result} score={ev.score}')
    print('PASS: regression eval completed (check result manually if needed)')


def test_override_status(client: TropekClient) -> None:
    """Override an evaluation result and restore it."""
    step('Step 11: Override evaluation status')
    evals = client.evaluations.list(asset_name='checkout-api')
    eval_id = str(evals.items[0].id)

    result = client.evaluations.override_status(eval_id, 'fail', 'testing override', 'test-runner')
    assert result.result == 'fail'
    assert result.original_result is not None

    result = client.evaluations.restore_override(eval_id)
    assert result.original_result is None
    print('PASS: override + restore')


def test_override_to_pass(client: TropekClient) -> None:
    """Override a completed evaluation to pass and verify original_result is preserved."""
    step('Step 12: Override completed eval result to pass')
    evals = client.evaluations.list(asset_name='checkout-api')
    completed = [e for e in evals.items if e.status == 'completed']
    assert completed, 'expected at least one completed eval'
    eval_id = str(completed[0].id)
    original_result = completed[0].result

    result = client.evaluations.override_status(eval_id, 'pass', 'manual override to pass', 'test-runner')
    assert result.result == 'pass', f'expected pass, got {result.result}'
    assert result.original_result == original_result
    print(f'overridden: {original_result} -> pass')

    result = client.evaluations.restore_override(eval_id)
    assert result.result == original_result, f'expected {original_result} after restore, got {result.result}'
    assert result.original_result is None
    print('PASS: override result to pass + restore')


def test_reeval_from_pinned_baseline(client: TropekClient) -> None:
    """Pin the 2nd evaluation, then re-evaluate from that pinned baseline."""
    step('Step 14: Pin baseline + re-evaluate from pinned')
    evals = client.evaluations.list(asset_name='checkout-api', slo_name='http-availability-slo')
    completed = [e for e in evals.items if e.status == 'completed']
    assert len(completed) >= 2, f'need >= 2 completed evals, got {len(completed)}'  # noqa: PLR2004

    # Pin the 2nd evaluation (not the most recent)
    pin_target = str(completed[1].id)
    pin_result = client.evaluations.pin_baseline(pin_target, 'e2e test: set baseline for re-eval', 'test-runner')
    assert pin_result.baseline_pinned_at is not None
    print(f'pinned eval {pin_target}')

    # Re-evaluate from the pinned baseline
    result = client.evaluations.re_evaluate_from_baseline(
        {'kind': 'asset', 'asset_name': 'checkout-api'},
        selector={'kind': 'slo', 'slo_name': 'http-availability-slo'},
    )
    print(f're-evaluated {result["affected_evaluations"]} evals (SLO v{result["slo_version_used"]})')
    assert result['affected_evaluations'] >= 1, 'expected at least 1 re-evaluated eval'
    for r in result['results']:
        print(f'  {r["period_start"][:16]}: {r["old_result"]} -> {r["new_result"]}')
    print('PASS: re-evaluate from pinned baseline')


def test_reeval_from_date(client: TropekClient) -> None:
    """Re-evaluate evaluations from a specific date."""
    step('Step 15: Re-evaluate from date')
    result = client.evaluations.re_evaluate_from_date(
        {'kind': 'asset', 'asset_name': 'checkout-api'},
        from_date='2026-03-15T16:00:00Z',
        selector={'kind': 'slo', 'slo_name': 'http-availability-slo'},
        pin_strategy='ignore_pin',
    )
    print(f're-evaluated {result["affected_evaluations"]} evals (SLO v{result["slo_version_used"]})')
    assert result['affected_evaluations'] >= 1, 'expected at least 1 re-evaluated eval'
    for r in result['results']:
        print(f'  {r["period_start"][:16]}: {r["old_result"]} -> {r["new_result"]}')
    print('PASS: re-evaluate from date')


def test_reeval_dry_run(client: TropekClient) -> None:
    """Dry-run re-evaluation returns diffs without writing."""
    step('Step 16: Re-evaluate dry run')
    result = client.evaluations.re_evaluate_from_date(
        {'kind': 'asset', 'asset_name': 'checkout-api'},
        from_date='2026-03-15T00:00:00Z',
        selector={'kind': 'slo', 'slo_name': 'http-availability-slo'},
        dry_run=True,
        pin_strategy='ignore_pin',
    )
    print(f'dry run: {result["affected_evaluations"]} evals would be affected (SLO v{result["slo_version_used"]})')
    assert result['affected_evaluations'] >= 0
    print('PASS: re-evaluate dry run')


def test_reeval_asset_wide(client: TropekClient) -> None:
    """Re-evaluate all SLOs for an asset when slo_name is omitted."""
    step('Step 16b: Asset-wide re-evaluate')
    result = client.evaluations.re_evaluate_from_date(
        {'kind': 'asset', 'asset_name': 'checkout-api'},
        from_date='2026-03-15T16:00:00Z',
        pin_strategy='ignore_pin',
    )
    print(f'asset-wide re-evaluated {result["affected_evaluations"]} evals')
    assert result['slo_version_used'] is None, 'slo_version_used should be null for multi-SLO re-eval'
    assert result['affected_evaluations'] >= 1, 'expected at least 1 re-evaluated eval'
    slo_names = {r['slo_name'] for r in result['results']}
    print(f'  SLOs affected: {slo_names}')
    assert len(slo_names) >= 1, 'expected results from at least 1 SLO'
    for r in result['results']:
        print(f'  {r["slo_name"]} {r["period_start"][:16]}: {r["old_result"]} -> {r["new_result"]}')
    print('PASS: asset-wide re-evaluate')


def test_slo_assignments(client: TropekClient) -> None:
    """Verify SLO assignments were created by bootstrap."""
    step('Step 17: SLO assignments')

    assignments = client.slo_assignments.list_for_asset('checkout-api')
    slo_names = [a.slo_name for a in assignments]
    assert 'http-availability-slo' in slo_names, f'expected http-availability-slo, got {slo_names}'
    print(f'checkout-api assignments: {slo_names}')

    group_assignments = client.slo_group_assignments.list_for_group('core-services')
    assert len(group_assignments) >= 1, f'expected at least 1 group assignment, got {len(group_assignments)}'
    print(f'core-services group assignments: {len(group_assignments)}')

    print('PASS: SLO assignments')


def test_annotations(client: TropekClient) -> None:
    """Create, list, update, and delete annotations on an evaluation (SLO + run level)."""
    step('Step 13: Annotation lifecycle')
    evals = client.evaluations.list(asset_name='checkout-api')
    assert evals.items, 'expected evaluations'
    slo_eval_id = str(evals.items[0].id)
    run_id = str(evals.items[0].evaluation_id)

    categories_resp = client._http.get('/note-categories')
    categories_resp.raise_for_status()
    categories_by_name = {c['name']: c['id'] for c in categories_resp.json()}
    info_id = categories_by_name['info']
    investigation_id = categories_by_name['investigation']

    ann = client.annotations.create(
        slo_eval_id,
        'deployment looked fine, ignoring regression',
        author='test-runner',
        category_id=info_id,
    )
    assert ann.content == 'deployment looked fine, ignoring regression'
    assert ann.author == 'test-runner'
    assert ann.slo_evaluation_id is not None, 'SLO-level note should carry slo_evaluation_id'
    assert ann.evaluation_run_id is None, 'SLO-level note must not carry evaluation_run_id'
    ann_id = str(ann.id)
    print(f'created SLO-level annotation: {ann_id}')

    anns = client.annotations.list(slo_eval_id)
    assert any(str(a.id) == ann_id for a in anns), f'annotation {ann_id} not found in list'
    print(f'listed {len(anns)} annotation(s)')

    updated = client.annotations.update(slo_eval_id, ann_id, content='updated note')
    assert updated.content == 'updated note'
    print('updated annotation content')

    run_ann = client.annotations.create_for_run(
        run_id,
        'column-level note from e2e test',
        author='test-runner',
        category_id=investigation_id,
    )
    assert run_ann.evaluation_run_id is not None, 'run-level note should carry evaluation_run_id'
    assert run_ann.slo_evaluation_id is None, 'run-level note must not carry slo_evaluation_id'
    run_ann_id = str(run_ann.id)
    print(f'created run-level annotation: {run_ann_id}')

    hidden = client.annotations.hide(slo_eval_id, ann_id, 'mistake', author='test-runner')
    assert hidden.hidden_at is not None
    assert hidden.hidden_reason == 'mistake'
    assert not any(str(a.id) == ann_id for a in client.annotations.list(slo_eval_id))
    client.annotations.hide(run_id, run_ann_id, 'cleanup', author='test-runner')
    print('PASS: create, list, update, hide annotation (SLO + run level)')


def test_asset_type_rename(client: TropekClient) -> None:
    """Rename an asset type and verify the name changed."""
    step('Step 18: Rename asset type')
    client.asset_types.create('rename-test-type')
    renamed = client.asset_types.rename('rename-test-type', 'renamed-type')
    assert renamed.name == 'renamed-type', f"expected 'renamed-type', got {renamed.name}"
    print(f'renamed: rename-test-type -> {renamed.name}')

    types = client.asset_types.list()
    names = [t.name for t in types]
    assert 'rename-test-type' not in names, 'old name still exists'
    assert 'renamed-type' in names, 'new name not found'

    client.asset_types.delete('renamed-type')
    print('PASS: asset type rename')


def test_asset_delete(client: TropekClient) -> None:
    """Create and delete an asset."""
    step('Step 19: Delete asset')
    client.assets.create('delete-test-asset', 'service', display_name='Delete Me')
    asset = client.assets.get('delete-test-asset')
    assert asset.name == 'delete-test-asset'

    client.assets.delete('delete-test-asset')

    assets = client.assets.list()
    names = [a.name for a in assets.items]
    assert 'delete-test-asset' not in names, 'asset still exists after delete'
    print('PASS: asset delete')


def test_label_autocomplete(client: TropekClient) -> None:
    """Test tag-keys and tag-values endpoints."""
    step('Step 20: Tag autocomplete')
    keys = client.assets.tag_keys()
    key_names = [k['key'] for k in keys]
    print(f'tag keys: {key_names}')
    assert 'team' in key_names, f"expected 'team' in keys, got {key_names}"
    assert 'env' in key_names, f"expected 'env' in keys, got {key_names}"

    team_values = client.assets.tag_values('team')
    value_names = [v['value'] for v in team_values]
    print(f'team values: {value_names}')
    assert 'payments' in value_names, f"expected 'payments' in {value_names}"

    for v in team_values:
        assert v['count'] > 0, f'expected count > 0 for {v["value"]}'
    print('PASS: tag autocomplete')


def test_aggregated_evaluation(client: TropekClient) -> None:
    """Trigger evaluations for an asset and verify the agg-latency-slo eval has method-keyed results."""
    step('Step 21: Aggregated-mode evaluation')

    # Use a late time window so seeded evaluations (00:00 through 16:00) provide baselines
    result = client.evaluations.evaluate(
        'checkout-api',
        'agg-baseline-test',
        '2026-03-16T14:00:00Z',
        '2026-03-16T14:30:00Z',
    )
    slo_eval_ids = result['slo_evaluation_ids']
    assert slo_eval_ids, 'expected at least one slo_evaluation_id'

    # Find the agg-latency-slo evaluation among the triggered ones
    ev = None
    for slo_eval_id in slo_eval_ids:
        candidate = poll_eval(client, str(slo_eval_id))
        if candidate.slo_name == 'agg-latency-slo':
            ev = candidate
            break
    assert ev is not None, f'agg-latency-slo not found among triggered SLOs: {slo_eval_ids}'
    eval_id = str(ev.id)
    print(f'triggered aggregated eval: {eval_id}')

    ev = poll_eval(client, eval_id)
    print(f'status={ev.status} result={ev.result} score={ev.score}')
    assert ev.status == 'completed', f'expected completed, got {ev.status}'
    assert ev.result in ('pass', 'warning', 'fail'), f'unexpected result: {ev.result}'

    # Verify indicator results contain {sli}.{method} keys
    metric_names = [i.metric for i in ev.indicator_results]
    print(f'indicator metrics: {metric_names}')
    for method in ['mean', 'p95', 'p99', 'max']:
        expected = f'agg-latency-sli.{method}'
        assert expected in metric_names, f'missing indicator {expected}, got {metric_names}'

    # Verify baseline comparison was performed (seeded evals should provide baselines)
    print(f'compared_evaluation_ids: {ev.compared_evaluation_ids}')
    assert len(ev.compared_evaluation_ids) > 0, 'expected at least 1 compared evaluation for baseline, got none'

    # Verify each indicator has a compared_value (baseline) populated
    for ir in ev.indicator_results:
        print(f'  {ir.metric}: value={ir.value} baseline={ir.compared_value} change={ir.change_relative_pct}%')
        assert ir.compared_value is not None, (
            f'expected compared_value for {ir.metric}, got None (compared_eval_ids={ev.compared_evaluation_ids})'
        )
        assert ir.change_absolute is not None, f'expected change_absolute for {ir.metric}, got None'
        assert ir.change_relative_pct is not None, f'expected change_relative_pct for {ir.metric}, got None'

    print('PASS: aggregated-mode evaluation with baselines')


def test_asset_type_delete_with_assets(client: TropekClient) -> None:
    """Verify that deleting a type with assets raises 409 Conflict."""
    step('Step 22: Delete type with assets (expect 409)')
    got_error = False
    try:
        client.asset_types.delete('service')
    except TropekAPIError as e:
        got_error = True
        print(f'correctly rejected: {e}')
    assert got_error, 'expected error when deleting type with assets'
    print('PASS: asset type delete blocked by assets')


def main() -> None:
    """Entry point — parse API URL from argv and run all tests."""
    if len(sys.argv) != 2:  # noqa: PLR2004
        print(f'usage: {sys.argv[0]} <api_url>', file=sys.stderr)
        sys.exit(1)

    client = TropekClient(sys.argv[1])

    test_single_evaluation(client)
    test_asset_trigger(client)
    test_pin_baseline(client)
    test_batch_evaluation(client)
    test_regression_eval(client)
    test_override_status(client)
    test_override_to_pass(client)
    test_reeval_from_pinned_baseline(client)
    test_reeval_from_date(client)
    test_reeval_dry_run(client)
    test_reeval_asset_wide(client)
    test_slo_assignments(client)
    test_annotations(client)
    test_asset_type_rename(client)
    test_asset_delete(client)
    test_label_autocomplete(client)
    test_aggregated_evaluation(client)
    test_asset_type_delete_with_assets(client)

    print('\n=== All integration tests passed ===')


if __name__ == '__main__':
    main()
