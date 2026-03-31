from __future__ import annotations

from tropek_client.models import Asset, AssetType, SLODefinition, SLOTestRequest

_UUID = '00000000-0000-0000-0000-000000000123'


def test_asset_type_from_dict():
    at = AssetType.model_validate({'id': _UUID, 'name': 'vm', 'is_default': True})
    assert at.name == 'vm'
    assert at.is_default is True


def test_asset_from_dict():
    a = Asset.model_validate(
        {
            'id': _UUID,
            'name': 'vm-01',
            'display_name': 'VM 01',
            'type_name': 'vm',
            'tags': {'os': 'linux'},
            'created_at': '2026-03-01T00:00:00Z',
        }
    )
    assert a.name == 'vm-01'
    assert a.tags['os'] == 'linux'


def test_slo_definition_from_dict():
    slo = SLODefinition.model_validate(
        {
            'id': _UUID,
            'name': 'my-slo',
            'display_name': None,
            'version': 1,
            'active': True,
            'objectives': [],
            'total_score_pass_threshold': 90.0,
            'total_score_warning_threshold': 75.0,
            'comparison': {},
            'notes': None,
            'author': None,
            'tags': {},
            'created_at': '2026-03-01T00:00:00Z',
        }
    )
    assert slo.version == 1
    assert slo.total_score_pass_threshold == 90.0


def test_slo_test_request_from_dict():
    req = SLOTestRequest.model_validate(
        {
            'slo_yaml': "spec_version: '1.0'",
            'sli_name': 'my-sli',
            'data_source_name': 'prom',
            'asset_name': 'vm-01',
            'period_start': '2026-03-01T00:00:00Z',
            'period_end': '2026-03-01T01:00:00Z',
        }
    )
    assert req.sli_name == 'my-sli'
    assert req.baseline is None
