"""Capture real API responses as JSON fixtures for client unit tests.

Runs after bootstrap + seed + e2e stages against a live TROPEK API.
Saves raw JSON responses to clients/python/tests/fixtures/api_responses/ so they can
be used as respx mocks to verify client deserialization.

Usage:
    uv run --directory clients/python python ../../dev_setup/stages/capture_responses.py <api_url>
"""

from __future__ import annotations

import json
import sys

import httpx
from _paths import PROJECT_ROOT

FIXTURES_DIR = PROJECT_ROOT / 'clients' / 'python' / 'tests' / 'fixtures' / 'api_responses'

TIMEOUT = 30
MIN_CLEAN_EVALS_FOR_STATE_CAPTURE = 2


def _save(name: str, data: object) -> None:
    path = FIXTURES_DIR / f'{name}.json'
    path.write_text(json.dumps(data, indent=2, default=str) + '\n')
    print(f'  captured {name} ({path.name})')


def _get(client: httpx.Client, path: str, **params: object) -> dict | list:
    response = client.get(path, params=params or None)
    response.raise_for_status()
    return response.json()


def _eval_matches(
    evaluation: dict,
    *,
    result: str | None = None,
    invalidated: bool | None = None,
    has_override: bool | None = None,
    has_baseline: bool | None = None,
    has_annotations: bool | None = None,
) -> bool:
    if result is not None and evaluation.get('result') != result:
        return False
    if invalidated is not None and evaluation.get('invalidated') != invalidated:
        return False
    if has_override is not None and (evaluation.get('override_reason') is not None) != has_override:
        return False
    if has_baseline is not None and (evaluation.get('baseline_pinned_at') is not None) != has_baseline:
        return False
    return not (has_annotations is not None and (evaluation.get('annotation_count', 0) > 0) != has_annotations)


def _find_eval_by(evaluations: list[dict], **criteria: object) -> dict | None:
    return next((e for e in evaluations if _eval_matches(e, **criteria)), None)


def _capture_resources(client: httpx.Client) -> None:
    print('\n--- Resources ---')

    _save('asset_type_list', _get(client, '/asset-types'))
    _save('datasource_get', _get(client, '/datasources/mock-dc-b'))
    _save('asset_get', _get(client, '/assets/checkout-api'))
    _save('asset_list', _get(client, '/assets', limit=5))
    _save('asset_tag_keys', _get(client, '/assets/tag-keys'))
    _save('asset_group_get', _get(client, '/asset-groups/core-services'))
    _save('asset_group_tree', _get(client, '/asset-groups/tree'))
    _save('sli_get', _get(client, '/sli-definitions/http-service-sli'))
    _save('sli_versions', _get(client, '/sli-definitions/http-service-sli/versions'))
    _save('slo_get', _get(client, '/slo-definitions/http-availability-slo'))
    _save('slo_versions', _get(client, '/slo-definitions/http-availability-slo/versions'))
    _save('slo_assignment_list_for_asset', _get(client, '/assets/checkout-api/slo-assignments'))
    _save('slo_group_get', _get(client, '/slo-groups/app-x-plugins'))
    _save('slo_group_list', _get(client, '/slo-groups'))
    _save('configuration_list', _get(client, '/configuration'))


def _capture_eval_detail(client: httpx.Client, items: list[dict], fixture_name: str, **criteria: object) -> None:
    """Find an evaluation matching criteria and save its detail as a fixture."""
    evaluation = _find_eval_by(items, **criteria)
    if evaluation:
        detail = _get(client, f'/evaluation/{evaluation["id"]}')
        _save(fixture_name, detail)
    else:
        print(f'  WARNING: no evaluation matching {fixture_name} criteria')


def _patch(client: httpx.Client, path: str, body: dict | None = None) -> dict:
    response = client.patch(path, json=body)
    response.raise_for_status()
    return response.json()


def _prepare_and_capture_eval_states(client: httpx.Client, items: list[dict]) -> None:
    """Apply override/invalidate to clean evals, capture, then restore."""
    clean_evals = [
        e
        for e in items
        if e.get('result') == 'pass'
        and not e.get('invalidated')
        and e.get('override_reason') is None
        and e.get('baseline_pinned_at') is None
        and e.get('annotation_count', 0) == 0
    ]

    if len(clean_evals) < MIN_CLEAN_EVALS_FOR_STATE_CAPTURE:
        print('  WARNING: not enough clean evaluations to create override/invalidated fixtures')
        return

    override_target = clean_evals[0]
    invalidate_target = clean_evals[1]

    override_detail = _patch(
        client,
        f'/evaluation/{override_target["id"]}/override-status',
        {'new_result': 'fail', 'reason': 'fixture capture', 'author': 'capture-script'},
    )
    _save('evaluation_detail_override', override_detail)
    _save('evaluation_detail_fail', override_detail)

    _patch(client, f'/evaluation/{override_target["id"]}/restore-override')
    print('  restored override on', override_target['id'])

    _patch(
        client,
        f'/evaluation/{invalidate_target["id"]}/invalidate',
        {'invalidation_note': 'fixture capture — will restore'},
    )
    invalidated_detail = _get(client, f'/evaluation/{invalidate_target["id"]}')
    _save('evaluation_detail_invalidated', invalidated_detail)

    _patch(client, f'/evaluation/{invalidate_target["id"]}/restore')
    print('  restored invalidation on', invalidate_target['id'])


def _capture_evaluations(client: httpx.Client) -> None:
    print('\n--- Evaluations ---')

    evaluation_list = _get(client, '/evaluations', asset_name='checkout-api', limit=50)
    _save('evaluation_list', evaluation_list)

    items = evaluation_list.get('items', [])
    if not items:
        print('  WARNING: no evaluations found for checkout-api, skipping eval details')
        return

    _capture_eval_detail(client, items, 'evaluation_detail_pass', result='pass', invalidated=False, has_override=False)
    _capture_eval_detail(client, items, 'evaluation_detail_baseline', has_baseline=True)

    existing_fail = _find_eval_by(items, result='fail', invalidated=False, has_override=False)
    existing_override = _find_eval_by(items, has_override=True)
    existing_invalid = _find_eval_by(items, invalidated=True)

    if existing_fail and existing_override and existing_invalid:
        _capture_eval_detail(
            client, items, 'evaluation_detail_fail', result='fail', invalidated=False, has_override=False
        )
        _capture_eval_detail(client, items, 'evaluation_detail_override', has_override=True)
        _capture_eval_detail(client, items, 'evaluation_detail_invalidated', invalidated=True)
    else:
        _prepare_and_capture_eval_states(client, items)

    annotated_eval = _find_eval_by(items, has_annotations=True)
    if annotated_eval:
        annotations = _get(client, f'/evaluation/{annotated_eval["id"]}/annotations')
        _save('annotation_list', annotations)
    else:
        print('  WARNING: no annotated evaluation found')

    _save('evaluation_names', _get(client, '/evaluations/names', asset_name='checkout-api'))

    _save('note_category_list', _get(client, '/note-categories'))


def _capture_views(client: httpx.Client) -> None:
    print('\n--- Views ---')

    _save('heatmap_grouped', _get(client, '/evaluations/heatmap', asset_name='checkout-api'))

    asset_data = _get(client, '/assets/checkout-api')
    asset_id = asset_data['id']
    _save(
        'timeline_get',
        _get(
            client,
            f'/assets/{asset_id}/meta/timeline',
            **{'from': '2026-02-01T00:00:00Z', 'to': '2026-04-01T00:00:00Z'},
        ),
    )

    config_list = _get(client, '/configuration')
    if config_list:
        first_name = config_list[0]['name']
        _save('configuration_get', _get(client, f'/configuration/{first_name}'))


def main() -> None:
    """Capture real API responses and save as JSON test fixtures."""
    api_url = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8080'
    print(f'Capturing API responses from {api_url}')
    print(f'Saving fixtures to {FIXTURES_DIR}/')

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    with httpx.Client(base_url=api_url, timeout=TIMEOUT) as client:
        _capture_resources(client)
        _capture_evaluations(client)
        _capture_views(client)

    fixture_count = len(list(FIXTURES_DIR.glob('*.json')))
    print(f'\nDone — {fixture_count} fixtures saved.')


if __name__ == '__main__':
    main()
