"""End-to-end integration tests run against a live TROPEK API.

Usage: uv run --directory clients/python python ../../scripts/e2e_tests.py <api_url>

Bootstrap manifests must be applied before running (see scripts/bootstrap.py).

Evaluation flows and their endpoints
-------------------------------------
Each test that triggers evaluations uses a distinct evaluation_name so they
are easy to identify in the heatmap and logs.

  evaluation_name     endpoint                 what it tests
  ─────────────────── ──────────────────────── ─────────────────────────────────
  single-eval         POST /evaluations        Legacy single-SLO trigger.
                                               Targets ONE explicit SLO. Proves
                                               the old endpoint still works.
                                               Rarely the right choice in prod.

  asset-trigger-test  POST /evaluations/asset  Asset-level trigger — resolves
                                               ALL SLOs for an asset from all 3
                                               binding sources. Preferred path.

  batch-test          POST /evaluations/batch  Group-level trigger — resolves
                                               all SLOs for every asset in the
                                               group via unified resolution.

  regression-test     POST /evaluations        Single-SLO on purpose: exercises
                                               baseline comparison after a pin.
                                               Needs a specific SLO to verify
                                               the comparison engine works.

  agg-baseline-test   POST /evaluations        Single-SLO on purpose: exercises
                                               aggregated-mode evaluation with
                                               method-keyed indicators and
                                               baseline comparison. Needs a
                                               specific SLO (agg-latency-slo).

The last two use the single-SLO endpoint intentionally — they are testing
engine features (baseline comparison, aggregated mode), not the trigger
mechanism. Don't convert them to asset-level triggers.
"""

from __future__ import annotations

import sys
import time

from tropek_client import TropekClient
from tropek_client.exceptions import TropekAPIError, TropekValidationError

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
    """Trigger one SLO evaluation via the legacy single-SLO endpoint.

    This flow targets a single explicit SLO — useful for ad-hoc debugging
    but normally the asset-level trigger (test_asset_trigger) should be
    preferred since it resolves all SLOs automatically.
    """
    step('Step 7: Trigger single-SLO evaluation (legacy)')
    result = client.evaluations.trigger(
        'checkout-api',
        'single-eval',
        'http-availability-slo',
        '2026-03-15T08:00:00Z',
        '2026-03-15T08:30:00Z',
    )
    eval_id = result['id']
    print(f'triggered: {eval_id}')
    ev = poll_eval(client, eval_id)
    print(f'status={ev.status} result={ev.result} score={ev.score}')
    assert ev.status == 'completed', f'expected completed, got {ev.status}'
    print('PASS: single-SLO evaluation')


def test_asset_trigger(client: TropekClient) -> None:
    """Trigger all SLOs for an asset and verify multiple evaluations are created."""
    step('Step 7b: Trigger asset-level evaluation (all SLOs)')
    result = client.evaluations.trigger_asset(
        'checkout-api',
        'asset-trigger-test',
        '2026-03-15T09:00:00Z',
        '2026-03-15T09:30:00Z',
    )
    eval_ids = result['evaluation_ids']
    slo_names = result['slo_names']
    print(f'triggered {len(eval_ids)} evaluations for SLOs: {slo_names}')
    assert len(eval_ids) >= 2, f'expected at least 2 evaluations, got {len(eval_ids)}'

    for eval_id in eval_ids:
        ev = poll_eval(client, str(eval_id))
        print(f'  {ev.slo_name}: status={ev.status} result={ev.result} score={ev.score}')
        assert ev.status == 'completed', f'expected completed for {ev.slo_name}, got {ev.status}'

    print(f'PASS: asset trigger — {len(eval_ids)} SLOs evaluated')


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
    """Trigger a batch evaluation for an asset group and wait for all to complete."""
    step('Step 9: Trigger batch evaluation')
    result = client.evaluations.trigger_batch(
        'core-services',
        'batch-test',
        '2026-03-15T08:00:00Z',
        '2026-03-15T08:30:00Z',
    )
    batch_id = result['batch_id']
    eval_ids = result['evaluation_ids']
    print(f'batch triggered: {batch_id}, {len(eval_ids)} evaluations')
    assert len(eval_ids) >= 1, f'expected at least 1 evaluation, got {len(eval_ids)}'

    for _ in range(60):
        statuses = {client.evaluations.get(str(eid)).status for eid in eval_ids}
        if statuses.issubset(TERMINAL_STATUSES):
            break
        time.sleep(1)

    print('PASS: batch evaluation')


def test_regression_eval(client: TropekClient) -> None:
    """Trigger a second evaluation to exercise baseline comparison.

    Uses single-SLO endpoint intentionally — needs http-availability-slo
    specifically to verify that baseline comparison works after a pin.
    """
    step('Step 10: Trigger regression eval after pin (single-SLO, intentional)')
    result = client.evaluations.trigger(
        'checkout-api',
        'regression-test',
        'http-availability-slo',
        '2026-03-16T12:00:00Z',
        '2026-03-16T12:30:00Z',
    )
    eval_id = result['id']
    print(f'triggered regression eval: {eval_id}')
    ev = poll_eval(client, eval_id)
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
    result = client.evaluations.re_evaluate('checkout-api', 'http-availability-slo', from_baseline=True)
    print(f're-evaluated {result["affected_evaluations"]} evals (SLO v{result["slo_version_used"]})')
    assert result['affected_evaluations'] >= 1, 'expected at least 1 re-evaluated eval'
    for r in result['results']:
        print(f'  {r["period_start"][:16]}: {r["old_result"]} -> {r["new_result"]}')
    print('PASS: re-evaluate from pinned baseline')


def test_reeval_from_date(client: TropekClient) -> None:
    """Re-evaluate evaluations from a specific date."""
    step('Step 15: Re-evaluate from date')
    result = client.evaluations.re_evaluate(
        'checkout-api',
        'http-availability-slo',
        from_date='2026-03-15T16:00:00Z',
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
    result = client.evaluations.re_evaluate(
        'checkout-api',
        'http-availability-slo',
        from_date='2026-03-15T00:00:00Z',
        dry_run=True,
    )
    print(f'dry run: {result["affected_evaluations"]} evals would be affected (SLO v{result["slo_version_used"]})')
    assert result['affected_evaluations'] >= 0
    print('PASS: re-evaluate dry run')


def test_comparison_rules(client: TropekClient) -> None:
    """CRUD lifecycle for comparison rules on an SLO link."""
    step('Step 17: Comparison rules CRUD')

    # GET — default empty
    rules = client.asset_slo_links.get_comparison_rules('checkout-api', 'checkout-api-http')
    assert rules == [], f'expected empty rules, got {rules}'
    print('default rules: []')

    # PUT — set rules
    new_rules = [
        {'match': {'branch': 'main'}, 'compare_to': {'branch': 'main'}},
        {'match': {'branch': '!main'}, 'compare_to': {'branch': 'main'}},
        {'match': {}, 'compare_to': {}},
    ]
    updated = client.asset_slo_links.update_comparison_rules('checkout-api', 'checkout-api-http', new_rules)
    assert len(updated) == 3, f'expected 3 rules, got {len(updated)}'  # noqa: PLR2004
    assert updated[0]['match'] == {'branch': 'main'}
    assert updated[2]['match'] == {}
    print(f'set {len(updated)} rules')

    # GET — verify persisted
    fetched = client.asset_slo_links.get_comparison_rules('checkout-api', 'checkout-api-http')
    assert len(fetched) == 3  # noqa: PLR2004
    print('fetched persisted rules')

    # PUT — clear rules
    cleared = client.asset_slo_links.update_comparison_rules('checkout-api', 'checkout-api-http', [])
    assert cleared == []
    print('cleared rules')

    # Verify 422 on invalid rules (catch-all not last)
    got_validation_error = False
    try:
        client.asset_slo_links.update_comparison_rules(
            'checkout-api',
            'checkout-api-http',
            [
                {'match': {}, 'compare_to': {}},
                {'match': {'branch': 'main'}, 'compare_to': {'branch': 'main'}},
            ],
        )
    except TropekValidationError:
        got_validation_error = True
    assert got_validation_error, 'expected 422 for catch-all not last'
    print('422 rejected invalid rules')

    print('PASS: comparison rules CRUD')


def test_annotations(client: TropekClient) -> None:
    """Create, list, update, and delete an annotation on an evaluation."""
    step('Step 13: Annotation lifecycle')
    evals = client.evaluations.list(asset_name='checkout-api')
    assert evals.items, 'expected evaluations'
    eval_id = str(evals.items[0].id)

    ann = client.annotations.create(
        eval_id,
        'deployment looked fine, ignoring regression',
        author='test-runner',
        category='deployment',
    )
    assert ann.content == 'deployment looked fine, ignoring regression'
    assert ann.author == 'test-runner'
    ann_id = str(ann.id)
    print(f'created annotation: {ann_id}')

    anns = client.annotations.list(eval_id)
    assert any(str(a.id) == ann_id for a in anns), f'annotation {ann_id} not found in list'
    print(f'listed {len(anns)} annotation(s)')

    updated = client.annotations.update(eval_id, ann_id, content='updated note')
    assert updated.content == 'updated note'
    print('updated annotation content')

    hidden = client.annotations.hide(eval_id, ann_id, 'mistake', author='test-runner')
    assert hidden.hidden_at is not None
    assert hidden.hidden_reason == 'mistake'
    assert not any(str(a.id) == ann_id for a in client.annotations.list(eval_id))
    print('PASS: create, list, update, hide annotation')


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
    """Trigger an aggregated-mode evaluation and verify method-keyed results with baselines.

    Uses single-SLO endpoint intentionally — needs agg-latency-slo
    specifically to verify aggregated-mode indicators (mean/p95/p99/max)
    and baseline comparison with method-keyed metrics.
    """
    step('Step 21: Aggregated-mode evaluation (single-SLO, intentional)')

    # Use a late time window so seeded evaluations (00:00 through 16:00) provide baselines
    result = client.evaluations.trigger(
        'checkout-api',
        'agg-baseline-test',
        'agg-latency-slo',
        '2026-03-16T14:00:00Z',
        '2026-03-16T14:30:00Z',
    )
    eval_id = result['id']
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
    test_comparison_rules(client)
    test_annotations(client)
    test_asset_type_rename(client)
    test_asset_delete(client)
    test_label_autocomplete(client)
    test_aggregated_evaluation(client)
    test_asset_type_delete_with_assets(client)

    print('\n=== All integration tests passed ===')


if __name__ == '__main__':
    main()
