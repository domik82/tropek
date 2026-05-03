"""Tests for model round-trips: construct from dict → validate → check fields."""

from uuid import UUID

from tropek_client.models import (
    AssetCreate,
    AssetRead,
    AssetTypeRead,
    EvaluationSummary,
    FailingIndicator,
    PagedResponse,
)
from tropek_client.models.assets import AssetSnapshot

_UUID = '00000000-0000-0000-0000-000000000001'
_UUID2 = '00000000-0000-0000-0000-000000000002'
_TS = '2026-03-01T00:00:00Z'


class TestAssetRead:
    def test_required_fields(self):
        asset = AssetRead.model_validate(
            {
                'id': _UUID,
                'name': 'vm-01',
                'display_name': None,
                'type_name': 'vm',
                'tags': {'env': 'prod'},
                'variables': {},
                'created_at': _TS,
                'updated_at': _TS,
            }
        )
        assert asset.name == 'vm-01'
        assert asset.type_name == 'vm'
        assert asset.tags == {'env': 'prod'}
        assert asset.variables == {}
        assert asset.display_name is None
        assert isinstance(asset.id, UUID)

    def test_optional_fields_default(self):
        asset = AssetRead.model_validate(
            {
                'id': _UUID,
                'name': 'svc',
                'display_name': 'My Service',
                'type_name': 'service',
                'tags': {},
                'variables': {},
                'created_at': _TS,
                'updated_at': _TS,
            }
        )
        assert asset.heatmap_config is None
        assert asset.color is None

    def test_round_trip(self):
        data = {
            'id': _UUID,
            'name': 'svc',
            'display_name': 'My Service',
            'type_name': 'service',
            'tags': {'team': 'platform'},
            'variables': {'region': 'eu-west-1'},
            'color': '#ff0000',
            'created_at': _TS,
            'updated_at': _TS,
        }
        asset = AssetRead.model_validate(data)
        dumped = asset.model_dump()
        asset2 = AssetRead.model_validate(dumped)
        assert asset2.name == asset.name
        assert asset2.color == asset.color
        assert asset2.variables == asset.variables


class TestAssetCreate:
    def test_required_fields_only(self):
        body = AssetCreate.model_validate({'name': 'vm-01', 'type_name': 'vm'})
        assert body.name == 'vm-01'
        assert body.type_name == 'vm'
        assert body.display_name is None
        assert body.tags is None

    def test_with_optional_fields(self):
        body = AssetCreate.model_validate(
            {
                'name': 'svc',
                'type_name': 'service',
                'display_name': 'My SVC',
                'tags': {'env': 'staging'},
                'variables': {'version': '1.2'},
                'color': 'green',
            }
        )
        assert body.display_name == 'My SVC'
        assert body.tags == {'env': 'staging'}
        assert body.color == 'green'

    def test_exclude_none_dump(self):
        body = AssetCreate(name='x', type_name='vm')
        dumped = body.model_dump(exclude_none=True)
        assert 'display_name' not in dumped
        assert dumped == {'name': 'x', 'type_name': 'vm'}


class TestEvaluationSummary:
    def _asset_snapshot(self):
        return {
            'name': 'vm-01',
            'display_name': 'VM 01',
            'asset_id': _UUID,
            'tags': {'env': 'prod'},
        }

    def _base_summary(self):
        return {
            'id': _UUID,
            'evaluation_id': _UUID2,
            'evaluation_name': 'nightly-eval',
            'status': 'succeeded',
            'result': 'pass',
            'score': 95.0,
            'period_start': '2026-03-01T00:00:00Z',
            'period_end': '2026-03-01T01:00:00Z',
            'slo_name': 'my-slo',
            'slo_version': 1,
            'sli_name': 'my-sli',
            'sli_version': 1,
            'data_source_name': 'prometheus',
            'ingestion_mode': 'live',
            'adapter_used': 'prometheus',
            'invalidated': False,
            'asset_snapshot': self._asset_snapshot(),
            'variables': {},
            'created_at': _TS,
        }

    def test_required_fields(self):
        summary = EvaluationSummary.model_validate(self._base_summary())
        assert summary.evaluation_name == 'nightly-eval'
        assert summary.result == 'pass'
        assert summary.score == 95.0
        assert summary.invalidated is False
        assert isinstance(summary.id, UUID)

    def test_asset_snapshot_nested(self):
        summary = EvaluationSummary.model_validate(self._base_summary())
        assert isinstance(summary.asset_snapshot, AssetSnapshot)
        assert summary.asset_snapshot.name == 'vm-01'

    def test_failing_indicators(self):
        data = self._base_summary()
        data['top_failures'] = [
            {'metric': 'response_time', 'display_name': 'Response Time', 'value': 650.0, 'threshold': '<600'},
        ]
        summary = EvaluationSummary.model_validate(data)
        assert summary.top_failures is not None
        assert len(summary.top_failures) == 1
        assert isinstance(summary.top_failures[0], FailingIndicator)
        assert summary.top_failures[0].metric == 'response_time'

    def test_optional_fields_default_to_none(self):
        summary = EvaluationSummary.model_validate(self._base_summary())
        assert summary.baseline_pinned_at is None
        assert summary.override_reason is None
        assert summary.latest_annotation is None
        assert summary.annotation_count == 0


class TestPagedResponse:
    def test_paged_response_of_asset_read(self):
        asset_data = {
            'id': _UUID,
            'name': 'vm-01',
            'display_name': None,
            'type_name': 'vm',
            'tags': {},
            'variables': {},
            'created_at': _TS,
            'updated_at': _TS,
        }
        paged: PagedResponse[AssetRead] = PagedResponse(
            items=[AssetRead.model_validate(asset_data)],
            total=1,
        )
        assert paged.total == 1
        assert len(paged.items) == 1
        assert isinstance(paged.items[0], AssetRead)
        assert paged.items[0].name == 'vm-01'

    def test_empty_paged_response(self):
        paged: PagedResponse[AssetRead] = PagedResponse(items=[], total=0)
        assert paged.total == 0
        assert paged.items == []

    def test_paged_response_of_asset_type_read(self):
        at = AssetTypeRead.model_validate({'id': _UUID, 'name': 'vm', 'is_default': True})
        paged: PagedResponse[AssetTypeRead] = PagedResponse(items=[at], total=1)
        assert paged.items[0].is_default is True
