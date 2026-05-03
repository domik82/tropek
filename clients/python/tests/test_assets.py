"""Tests for asset types, assets, and asset groups."""

import httpx
import pytest
import respx
from tropek_client.exceptions import TropekNotFoundError
from tropek_client.models import (
    AddMemberRequest,
    AssetCreate,
    AssetGroupCreate,
    AssetGroupRead,
    AssetGroupTreeResponse,
    AssetRead,
    AssetTypeCreate,
    AssetTypeRead,
    PagedResponse,
    TagKeyCount,
)

from .conftest import BASE_URL, TIMESTAMP, UUID1, load_fixture

ASSET_JSON = {
    'id': UUID1,
    'name': 'vm-01',
    'display_name': 'VM 01',
    'type_name': 'vm',
    'tags': {},
    'variables': {},
    'created_at': TIMESTAMP,
    'updated_at': TIMESTAMP,
}

ASSET_TYPE_JSON = {
    'id': UUID1,
    'name': 'vm',
    'is_default': True,
    'asset_count': 5,
}

ASSET_GROUP_JSON = {
    'id': UUID1,
    'name': 'prod-group',
    'display_name': None,
    'description': None,
    'members': [],
    'subgroups': [],
    'created_at': TIMESTAMP,
    'updated_at': TIMESTAMP,
}


class TestAssetTypes:
    @respx.mock
    def test_list(self, client):
        respx.get(f'{BASE_URL}/asset-types').mock(
            return_value=httpx.Response(200, json={'items': [ASSET_TYPE_JSON], 'total': 1})
        )
        result = client.asset_types.list()
        assert isinstance(result, PagedResponse)
        assert result.total == 1
        assert isinstance(result.items[0], AssetTypeRead)
        assert result.items[0].name == 'vm'

    @respx.mock
    def test_create(self, client):
        route = respx.post(f'{BASE_URL}/asset-types').mock(return_value=httpx.Response(201, json=ASSET_TYPE_JSON))
        result = client.asset_types.create(AssetTypeCreate(name='vm'))
        assert isinstance(result, AssetTypeRead)
        assert result.name == 'vm'
        assert b'"name":"vm"' in route.calls[0].request.content


class TestAssets:
    @respx.mock
    def test_list(self, client):
        respx.get(f'{BASE_URL}/assets').mock(return_value=httpx.Response(200, json={'items': [ASSET_JSON], 'total': 1}))
        result = client.assets.list()
        assert isinstance(result, PagedResponse)
        assert result.total == 1
        assert isinstance(result.items[0], AssetRead)
        assert result.items[0].name == 'vm-01'

    @respx.mock
    def test_create(self, client):
        route = respx.post(f'{BASE_URL}/assets').mock(return_value=httpx.Response(201, json=ASSET_JSON))
        result = client.assets.create(AssetCreate(name='vm-01', type_name='vm'))
        assert isinstance(result, AssetRead)
        assert result.name == 'vm-01'
        assert b'"name":"vm-01"' in route.calls[0].request.content
        assert b'"type_name":"vm"' in route.calls[0].request.content

    @respx.mock
    def test_get(self, client):
        respx.get(f'{BASE_URL}/assets/vm-01').mock(return_value=httpx.Response(200, json=ASSET_JSON))
        result = client.assets.get('vm-01')
        assert isinstance(result, AssetRead)
        assert result.name == 'vm-01'

    @respx.mock
    def test_delete(self, client):
        route = respx.delete(f'{BASE_URL}/assets/vm-01').mock(return_value=httpx.Response(204))
        client.assets.delete('vm-01')
        assert route.called


class TestAssetGroups:
    @respx.mock
    def test_list(self, client):
        respx.get(f'{BASE_URL}/asset-groups').mock(
            return_value=httpx.Response(200, json={'items': [ASSET_GROUP_JSON], 'total': 1})
        )
        result = client.asset_groups.list()
        assert isinstance(result, PagedResponse)
        assert result.total == 1
        assert isinstance(result.items[0], AssetGroupRead)

    @respx.mock
    def test_create(self, client):
        route = respx.post(f'{BASE_URL}/asset-groups').mock(return_value=httpx.Response(201, json=ASSET_GROUP_JSON))
        result = client.asset_groups.create(AssetGroupCreate(name='prod-group'))
        assert isinstance(result, AssetGroupRead)
        assert b'"name":"prod-group"' in route.calls[0].request.content

    @respx.mock
    def test_add_member(self, client):
        route = respx.post(f'{BASE_URL}/asset-groups/prod-group/members').mock(
            return_value=httpx.Response(200, json=ASSET_GROUP_JSON)
        )
        result = client.asset_groups.add_member(
            'prod-group',
            AddMemberRequest(asset_id=UUID1),
        )
        assert isinstance(result, AssetGroupRead)
        assert route.called


class TestNotFound:
    @respx.mock
    def test_get_missing_asset_raises_not_found(self, client):
        respx.get(f'{BASE_URL}/assets/missing').mock(
            return_value=httpx.Response(404, json={'detail': "asset 'missing' not found"})
        )
        with pytest.raises(TropekNotFoundError) as exc_info:
            client.assets.get('missing')
        assert exc_info.value.entity == 'asset'
        assert exc_info.value.name == 'missing'


class TestAssetTypeFixtures:
    @respx.mock
    def test_list(self, client):
        data = load_fixture('asset_type_list')
        respx.get(f'{BASE_URL}/asset-types').mock(return_value=httpx.Response(200, json=data))
        result = client.asset_types.list()
        assert isinstance(result, PagedResponse)
        assert len(result.items) > 0
        assert all(isinstance(item, AssetTypeRead) for item in result.items)
        first = result.items[0]
        assert first.name
        assert first.id


class TestAssetFixtures:
    @respx.mock
    def test_get(self, client):
        data = load_fixture('asset_get')
        respx.get(f'{BASE_URL}/assets/checkout-api').mock(return_value=httpx.Response(200, json=data))
        result = client.assets.get('checkout-api')
        assert isinstance(result, AssetRead)
        assert result.name == 'checkout-api'
        assert result.id
        assert result.type_name

    @respx.mock
    def test_list(self, client):
        data = load_fixture('asset_list')
        respx.get(f'{BASE_URL}/assets').mock(return_value=httpx.Response(200, json=data))
        result = client.assets.list()
        assert isinstance(result, PagedResponse)
        assert len(result.items) > 0
        assert all(isinstance(item, AssetRead) for item in result.items)

    @respx.mock
    def test_tag_keys(self, client):
        data = load_fixture('asset_tag_keys')
        respx.get(f'{BASE_URL}/assets/tag-keys').mock(return_value=httpx.Response(200, json=data))
        result = client.assets.tag_keys()
        assert isinstance(result, list)
        if result:
            assert all(isinstance(item, TagKeyCount) for item in result)


class TestAssetGroupFixtures:
    @respx.mock
    def test_get(self, client):
        data = load_fixture('asset_group_get')
        respx.get(f'{BASE_URL}/asset-groups/core-services').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.asset_groups.get('core-services')
        assert isinstance(result, AssetGroupRead)
        assert result.name == 'core-services'
        assert result.members is not None

    @respx.mock
    def test_tree(self, client):
        data = load_fixture('asset_group_tree')
        respx.get(f'{BASE_URL}/asset-groups/tree').mock(return_value=httpx.Response(200, json=data))
        result = client.asset_groups.tree()
        assert isinstance(result, AssetGroupTreeResponse)
