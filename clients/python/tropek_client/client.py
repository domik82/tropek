"""Typed HTTP client for the TROPEK API."""

from __future__ import annotations

from typing import Any

import httpx

from tropek_client.exceptions import (
    TropekAPIError,
    TropekConflictError,
    TropekNotFoundError,
    TropekValidationError,
)
from tropek_client.models import (
    Annotation,
    Asset,
    AssetGroup,
    AssetGroupSLOLink,
    AssetGroupTree,
    AssetSLOLink,
    AssetType,
    DataSource,
    EvaluationDetail,
    EvaluationSummary,
    PagedResponse,
    SLIDefinition,
    SLOBinding,
    SLODefinition,
    SLOGroup,
    SLOTestResult,
    SLOValidationResult,
    TemplateBinding,
    TrendPoint,
)


def _raise_for_status(resp: httpx.Response) -> None:
    """Raise typed exception for non-2xx responses."""
    if resp.is_success:
        return
    try:
        data = resp.json()
        detail = data.get('detail', resp.text) if isinstance(data, dict) else resp.text
    except ValueError:
        detail = resp.text
    match resp.status_code:
        case 404:
            raise TropekNotFoundError(detail)
        case 409:
            raise TropekConflictError(detail)
        case 422:
            raise TropekValidationError(detail)
        case _:
            raise TropekAPIError(resp.status_code, detail)


class _AssetTypes:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list(self) -> list[AssetType]:
        """List all asset types."""
        resp = self._http.get('/asset-types')
        _raise_for_status(resp)
        return [AssetType.model_validate(i) for i in resp.json()['items']]

    def create(self, name: str, *, is_default: bool = False) -> AssetType:
        """Create an asset type."""
        resp = self._http.post('/asset-types', json={'name': name, 'is_default': is_default})
        _raise_for_status(resp)
        return AssetType.model_validate(resp.json())

    def set_default(self, name: str) -> AssetType:
        """Set an asset type as the default."""
        resp = self._http.patch(f'/asset-types/{name}/set-default')
        _raise_for_status(resp)
        return AssetType.model_validate(resp.json())

    def rename(self, name: str, new_name: str) -> AssetType:
        """Rename an asset type."""
        resp = self._http.patch(f'/asset-types/{name}', json={'name': new_name})
        _raise_for_status(resp)
        return AssetType.model_validate(resp.json())

    def delete(self, name: str) -> None:
        """Delete an asset type."""
        resp = self._http.delete(f'/asset-types/{name}')
        _raise_for_status(resp)


class _Assets:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list(
        self,
        *,
        type_name: str | None = None,
        tag_key: str | None = None,
        tag_val: str | None = None,
    ) -> PagedResponse[Asset]:
        """List assets with optional filters."""
        params: dict[str, str] = {}
        if type_name:
            params['type_name'] = type_name
        if tag_key:
            params['tag_key'] = tag_key
        if tag_val:
            params['tag_val'] = tag_val
        resp = self._http.get('/assets', params=params)
        _raise_for_status(resp)
        data = resp.json()
        return PagedResponse(
            items=[Asset.model_validate(i) for i in data['items']],
            total=data['total'],
        )

    def create(
        self,
        name: str,
        type_name: str = 'vm',
        *,
        display_name: str | None = None,
        tags: dict[str, str] | None = None,
        variables: dict[str, str] | None = None,
    ) -> Asset:
        """Create an asset."""
        body: dict[str, Any] = {'name': name, 'type_name': type_name}
        if display_name is not None:
            body['display_name'] = display_name
        if tags is not None:
            body['tags'] = tags
        if variables is not None:
            body['variables'] = variables
        resp = self._http.post('/assets', json=body)
        _raise_for_status(resp)
        return Asset.model_validate(resp.json())

    def get(self, name: str) -> Asset:
        """Get an asset by name."""
        resp = self._http.get(f'/assets/{name}')
        _raise_for_status(resp)
        return Asset.model_validate(resp.json())

    def update(self, name: str, **kwargs: Any) -> Asset:
        """Update an asset."""
        resp = self._http.patch(f'/assets/{name}', json=kwargs)
        _raise_for_status(resp)
        return Asset.model_validate(resp.json())

    def delete(self, name: str) -> None:
        """Delete an asset."""
        resp = self._http.delete(f'/assets/{name}')
        _raise_for_status(resp)

    def tag_keys(self) -> list[dict[str, Any]]:
        """Get all distinct tag keys across assets with counts."""
        resp = self._http.get('/assets/tag-keys')
        _raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]

    def tag_values(self, key: str) -> list[dict[str, Any]]:
        """Get values and counts for a tag key."""
        resp = self._http.get('/assets/tag-values', params={'key': key})
        _raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]


class _AssetGroups:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list(self) -> PagedResponse[AssetGroup]:
        """List all asset groups."""
        resp = self._http.get('/asset-groups')
        _raise_for_status(resp)
        data = resp.json()
        return PagedResponse(
            items=[AssetGroup.model_validate(i) for i in data['items']],
            total=data['total'],
        )

    def tree(self) -> AssetGroupTree:
        """Get the asset group tree."""
        resp = self._http.get('/asset-groups/tree')
        _raise_for_status(resp)
        return AssetGroupTree.model_validate(resp.json())

    def create(
        self,
        name: str,
        *,
        display_name: str | None = None,
        members: list[dict[str, Any]] | None = None,
        subgroups: list[dict[str, Any]] | None = None,
    ) -> AssetGroup:
        """Create an asset group."""
        body: dict[str, Any] = {'name': name}
        if display_name is not None:
            body['display_name'] = display_name
        if members is not None:
            body['members'] = members
        if subgroups is not None:
            body['subgroups'] = subgroups
        resp = self._http.post('/asset-groups', json=body)
        _raise_for_status(resp)
        return AssetGroup.model_validate(resp.json())

    def get(self, name: str) -> AssetGroup:
        """Get an asset group by name."""
        resp = self._http.get(f'/asset-groups/{name}')
        _raise_for_status(resp)
        return AssetGroup.model_validate(resp.json())

    def add_member(self, group_name: str, asset_id: str, weight: float = 1.0) -> AssetGroup:
        """Add a member to an asset group."""
        resp = self._http.post(
            f'/asset-groups/{group_name}/members',
            json={'asset_id': asset_id, 'weight': weight},
        )
        _raise_for_status(resp)
        return AssetGroup.model_validate(resp.json())

    def remove_member(self, group_name: str, asset_id: str) -> None:
        """Remove a member from an asset group."""
        resp = self._http.delete(f'/asset-groups/{group_name}/members/{asset_id}')
        _raise_for_status(resp)

    def add_subgroup(self, group_name: str, child_group_id: str, weight: float = 1.0) -> AssetGroup:
        """Add a subgroup to an asset group."""
        resp = self._http.post(
            f'/asset-groups/{group_name}/subgroups',
            json={'child_group_id': child_group_id, 'weight': weight},
        )
        _raise_for_status(resp)
        return AssetGroup.model_validate(resp.json())

    def remove_subgroup(self, group_name: str, child_group_id: str) -> None:
        """Remove a subgroup from an asset group."""
        resp = self._http.delete(f'/asset-groups/{group_name}/subgroups/{child_group_id}')
        _raise_for_status(resp)


class _SLOLinks[T: Any]:
    def __init__(self, http: httpx.Client, prefix: str, model: type[T]) -> None:
        self._http = http
        self._prefix = prefix
        self._model = model

    def list(self, parent_name: str) -> list[T]:
        """List SLO links for a parent entity."""
        resp = self._http.get(f'/{self._prefix}/{parent_name}/slo-links')
        _raise_for_status(resp)
        return [self._model.model_validate(i) for i in resp.json()]

    def create(
        self,
        parent_name: str,
        link_name: str,
        slo_name: str,
        sli_name: str,
        data_source_name: str,
    ) -> T:
        """Create an SLO link."""
        resp = self._http.post(
            f'/{self._prefix}/{parent_name}/slo-links',
            json={
                'link_name': link_name,
                'slo_name': slo_name,
                'sli_name': sli_name,
                'data_source_name': data_source_name,
            },
        )
        _raise_for_status(resp)
        return self._model.model_validate(resp.json())

    def delete(self, parent_name: str, link_name: str) -> None:
        """Delete an SLO link."""
        resp = self._http.delete(f'/{self._prefix}/{parent_name}/slo-links/{link_name}')
        _raise_for_status(resp)

    def get_comparison_rules(self, parent_name: str, link_name: str) -> list[dict[str, Any]]:
        """Get comparison rules for an SLO link."""
        resp = self._http.get(f'/{self._prefix}/{parent_name}/slo-links/{link_name}/comparison-rules')
        _raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]

    def update_comparison_rules(
        self,
        parent_name: str,
        link_name: str,
        rules: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Replace comparison rules for an SLO link."""
        resp = self._http.put(
            f'/{self._prefix}/{parent_name}/slo-links/{link_name}/comparison-rules',
            json={'rules': rules},
        )
        _raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]


class _DataSources:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list(self, *, adapter_type: str | None = None) -> PagedResponse[DataSource]:
        """List data sources."""
        params: dict[str, str] = {}
        if adapter_type:
            params['adapter_type'] = adapter_type
        resp = self._http.get('/datasources', params=params)
        _raise_for_status(resp)
        data = resp.json()
        return PagedResponse(
            items=[DataSource.model_validate(i) for i in data['items']],
            total=data['total'],
        )

    def create(self, name: str, adapter_type: str, adapter_url: str, **kwargs: Any) -> DataSource:
        """Create a data source."""
        body = {'name': name, 'adapter_type': adapter_type, 'adapter_url': adapter_url, **kwargs}
        resp = self._http.post('/datasources', json=body)
        _raise_for_status(resp)
        return DataSource.model_validate(resp.json())

    def get(self, name: str) -> DataSource:
        """Get a data source by name."""
        resp = self._http.get(f'/datasources/{name}')
        _raise_for_status(resp)
        return DataSource.model_validate(resp.json())

    def update(self, name: str, **kwargs: Any) -> DataSource:
        """Update a data source."""
        resp = self._http.patch(f'/datasources/{name}', json=kwargs)
        _raise_for_status(resp)
        return DataSource.model_validate(resp.json())

    def delete(self, name: str) -> None:
        """Delete a data source."""
        resp = self._http.delete(f'/datasources/{name}')
        _raise_for_status(resp)

    def tag_keys(self) -> list[dict[str, Any]]:
        """Get all distinct tag keys across data sources with counts."""
        resp = self._http.get('/datasources/tag-keys')
        _raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]

    def tag_values(self, key: str) -> list[dict[str, Any]]:
        """Get values and counts for a tag key."""
        resp = self._http.get('/datasources/tag-values', params={'key': key})
        _raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]


class _SLIDefinitions:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list(self) -> PagedResponse[SLIDefinition]:
        """List all SLI definitions."""
        resp = self._http.get('/sli-definitions')
        _raise_for_status(resp)
        data = resp.json()
        return PagedResponse(
            items=[SLIDefinition.model_validate(i) for i in data['items']],
            total=data['total'],
        )

    def create(self, name: str, indicators: dict[str, str], **kwargs: Any) -> SLIDefinition:
        """Create an SLI definition."""
        body = {'name': name, 'indicators': indicators, **kwargs}
        resp = self._http.post('/sli-definitions', json=body)
        _raise_for_status(resp)
        return SLIDefinition.model_validate(resp.json())

    def get(self, name: str) -> SLIDefinition:
        """Get an SLI definition by name."""
        resp = self._http.get(f'/sli-definitions/{name}')
        _raise_for_status(resp)
        return SLIDefinition.model_validate(resp.json())

    def versions(self, name: str) -> list[SLIDefinition]:
        """Get all versions of an SLI definition."""
        resp = self._http.get(f'/sli-definitions/{name}/versions')
        _raise_for_status(resp)
        return [SLIDefinition.model_validate(v) for v in resp.json()]

    def delete(self, name: str) -> None:
        """Delete an SLI definition."""
        resp = self._http.delete(f'/sli-definitions/{name}')
        _raise_for_status(resp)

    def tag_keys(self) -> list[dict[str, Any]]:
        """Get all distinct tag keys across SLI definitions with counts."""
        resp = self._http.get('/sli-definitions/tag-keys')
        _raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]

    def tag_values(self, key: str) -> list[dict[str, Any]]:
        """Get values and counts for a tag key."""
        resp = self._http.get('/sli-definitions/tag-values', params={'key': key})
        _raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]


class _SLODefinitions:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list(self) -> PagedResponse[SLODefinition]:
        """List all SLO definitions."""
        resp = self._http.get('/slo-definitions')
        _raise_for_status(resp)
        data = resp.json()
        return PagedResponse(
            items=[SLODefinition.model_validate(i) for i in data['items']],
            total=data['total'],
        )

    def create(
        self,
        name: str,
        objectives: list[dict],
        total_score_pass_threshold: float = 90.0,
        total_score_warning_threshold: float = 75.0,
        *,
        comparison: dict | None = None,
        **kwargs: Any,
    ) -> SLODefinition:
        """Create an SLO definition."""
        body = {
            'name': name,
            'objectives': objectives,
            'total_score_pass_threshold': total_score_pass_threshold,
            'total_score_warning_threshold': total_score_warning_threshold,
            'comparison': comparison or {},
            **kwargs,
        }
        resp = self._http.post('/slo-definitions', json=body)
        _raise_for_status(resp)
        return SLODefinition.model_validate(resp.json())

    def get(self, name: str) -> SLODefinition:
        """Get an SLO definition by name."""
        resp = self._http.get(f'/slo-definitions/{name}')
        _raise_for_status(resp)
        return SLODefinition.model_validate(resp.json())

    def versions(self, name: str) -> list[SLODefinition]:
        """Get all versions of an SLO definition."""
        resp = self._http.get(f'/slo-definitions/{name}/versions')
        _raise_for_status(resp)
        return [SLODefinition.model_validate(v) for v in resp.json()]

    def delete(self, name: str) -> None:
        """Delete an SLO definition."""
        resp = self._http.delete(f'/slo-definitions/{name}')
        _raise_for_status(resp)

    def tag_keys(self) -> list[dict[str, Any]]:
        """Get all distinct tag keys across SLO definitions with counts."""
        resp = self._http.get('/slo-definitions/tag-keys')
        _raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]

    def tag_values(self, key: str) -> list[dict[str, Any]]:
        """Get values and counts for a tag key."""
        resp = self._http.get('/slo-definitions/tag-values', params={'key': key})
        _raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]

    def validate(self, slo_yaml: str) -> SLOValidationResult:
        """Validate an SLO YAML without saving."""
        resp = self._http.post('/slo-definitions/validate', json={'slo_yaml': slo_yaml})
        _raise_for_status(resp)
        return SLOValidationResult.model_validate(resp.json())

    def test(self, request: dict[str, Any]) -> SLOTestResult:
        """Run a test evaluation with an SLO."""
        resp = self._http.post('/slo-definitions/test', json=request)
        _raise_for_status(resp)
        return SLOTestResult.model_validate(resp.json())


class _Evaluations:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list(  # noqa: PLR0913
        self,
        *,
        asset_name: str | None = None,
        slo_name: str | None = None,
        result: str | None = None,
        date: str | None = None,
        group_name: str | None = None,
        from_: str | None = None,
        to: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PagedResponse[EvaluationSummary]:
        """List evaluations with optional filters."""
        params: dict[str, Any] = {'limit': limit, 'offset': offset}
        if asset_name:
            params['asset_name'] = asset_name
        if slo_name:
            params['slo_name'] = slo_name
        if result is not None:
            params['result'] = result
        if date is not None:
            params['date'] = date
        if group_name:
            params['group_name'] = group_name
        if from_ is not None:
            params['from'] = from_
        if to is not None:
            params['to'] = to
        resp = self._http.get('/evaluations', params=params)
        _raise_for_status(resp)
        data = resp.json()
        return PagedResponse(
            items=[EvaluationSummary.model_validate(i) for i in data['items']],
            total=data['total'],
        )

    def get(self, eval_id: str) -> EvaluationDetail:
        """Get a full evaluation by ID."""
        resp = self._http.get(f'/evaluations/{eval_id}')
        _raise_for_status(resp)
        return EvaluationDetail.model_validate(resp.json())

    def invalidate(self, eval_id: str, note: str) -> EvaluationSummary:
        """Invalidate an evaluation."""
        resp = self._http.patch(
            f'/evaluations/{eval_id}/invalidate',
            json={'invalidation_note': note},
        )
        _raise_for_status(resp)
        return EvaluationSummary.model_validate(resp.json())

    def restore(self, eval_id: str) -> EvaluationSummary:
        """Restore an invalidated evaluation."""
        resp = self._http.patch(f'/evaluations/{eval_id}/restore')
        _raise_for_status(resp)
        return EvaluationSummary.model_validate(resp.json())

    def trigger(
        self,
        asset_name: str,
        evaluation_name: str,
        slo_name: str,
        period_start: str,
        period_end: str,
        *,
        variables: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Trigger a single asset evaluation."""
        resp = self._http.post(
            '/evaluations',
            json={
                'asset_name': asset_name,
                'evaluation_name': evaluation_name,
                'slo_name': slo_name,
                'period_start': period_start,
                'period_end': period_end,
                'variables': variables or {},
            },
        )
        _raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]

    def trigger_asset(
        self,
        asset_name: str,
        evaluation_name: str,
        period_start: str,
        period_end: str,
        *,
        variables: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Trigger evaluations for all SLOs linked to an asset."""
        resp = self._http.post(
            '/evaluations/asset',
            json={
                'asset_name': asset_name,
                'evaluation_name': evaluation_name,
                'period_start': period_start,
                'period_end': period_end,
                'variables': variables or {},
            },
        )
        _raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]

    def trigger_batch(
        self,
        group_name: str,
        evaluation_name: str,
        period_start: str,
        period_end: str,
        *,
        variables: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Trigger evaluations for all assets in a group."""
        resp = self._http.post(
            '/evaluations/batch',
            json={
                'group_name': group_name,
                'evaluation_name': evaluation_name,
                'period_start': period_start,
                'period_end': period_end,
                'variables': variables or {},
            },
        )
        _raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]

    def pin_baseline(self, eval_id: str, reason: str, author: str) -> EvaluationDetail:
        """Pin an evaluation as baseline."""
        resp = self._http.patch(
            f'/evaluations/{eval_id}/pin-baseline',
            json={'reason': reason, 'author': author},
        )
        _raise_for_status(resp)
        return EvaluationDetail.model_validate(resp.json())

    def unpin_baseline(self, eval_id: str) -> EvaluationDetail:
        """Remove baseline pin from an evaluation."""
        resp = self._http.patch(f'/evaluations/{eval_id}/unpin-baseline')
        _raise_for_status(resp)
        return EvaluationDetail.model_validate(resp.json())

    def override_status(self, eval_id: str, new_result: str, reason: str, author: str) -> EvaluationDetail:
        """Override evaluation result."""
        resp = self._http.patch(
            f'/evaluations/{eval_id}/override-status',
            json={'new_result': new_result, 'reason': reason, 'author': author},
        )
        _raise_for_status(resp)
        return EvaluationDetail.model_validate(resp.json())

    def restore_override(self, eval_id: str) -> EvaluationDetail:
        """Restore original evaluation result."""
        resp = self._http.patch(f'/evaluations/{eval_id}/restore-override')
        _raise_for_status(resp)
        return EvaluationDetail.model_validate(resp.json())

    def re_evaluate(
        self,
        asset_name: str,
        slo_name: str,
        *,
        from_date: str | None = None,
        from_baseline: bool = False,
        from_evaluation_id: str | None = None,
        slo_version: int | None = None,
        dry_run: bool = False,
        pin_strategy: str | None = None,
    ) -> dict[str, Any]:
        """Re-evaluate completed evaluations from stored SLI values."""
        body: dict[str, Any] = {'asset_name': asset_name, 'slo_name': slo_name}
        if from_date is not None:
            body['from_date'] = from_date
        if from_baseline:
            body['from_baseline'] = True
        if from_evaluation_id is not None:
            body['from_evaluation_id'] = from_evaluation_id
        if slo_version is not None:
            body['slo_version'] = slo_version
        if dry_run:
            body['dry_run'] = True
        if pin_strategy is not None:
            body['pin_strategy'] = pin_strategy
        resp = self._http.post('/evaluations/re-evaluate', json=body)
        _raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]


class _Annotations:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list(self, eval_id: str) -> list[Annotation]:
        """List annotations for an evaluation."""
        resp = self._http.get(f'/evaluations/{eval_id}/annotations')
        _raise_for_status(resp)
        return [Annotation.model_validate(a) for a in resp.json()]

    def create(self, eval_id: str, content: str, **kwargs: Any) -> Annotation:
        """Create an annotation on an evaluation."""
        body = {'content': content, **kwargs}
        resp = self._http.post(f'/evaluations/{eval_id}/annotations', json=body)
        _raise_for_status(resp)
        return Annotation.model_validate(resp.json())

    def update(self, eval_id: str, ann_id: str, **kwargs: Any) -> Annotation:
        """Update an annotation."""
        resp = self._http.patch(f'/evaluations/{eval_id}/annotations/{ann_id}', json=kwargs)
        _raise_for_status(resp)
        return Annotation.model_validate(resp.json())

    def hide(self, eval_id: str, ann_id: str, reason: str, author: str | None = None) -> Annotation:
        """Soft-delete (hide) an annotation."""
        body: dict[str, Any] = {'reason': reason}
        if author:
            body['author'] = author
        resp = self._http.post(f'/evaluations/{eval_id}/annotations/{ann_id}/hide', json=body)
        _raise_for_status(resp)
        return Annotation.model_validate(resp.json())


class _Trend:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def by_eval(self, eval_id: str, metric: str, limit: int = 50) -> list[TrendPoint]:
        """Get trend data points for a metric by evaluation ID."""
        resp = self._http.get('/trend', params={'eval_id': eval_id, 'metric': metric, 'limit': limit})
        _raise_for_status(resp)
        return [TrendPoint.model_validate(p) for p in resp.json()]

    def by_asset(self, asset_name: str, slo_name: str, metric: str, limit: int = 50) -> list[TrendPoint]:
        """Get trend data points for a metric by asset and SLO."""
        resp = self._http.get(
            '/trend',
            params={
                'asset_name': asset_name,
                'slo_name': slo_name,
                'metric': metric,
                'limit': limit,
            },
        )
        _raise_for_status(resp)
        return [TrendPoint.model_validate(p) for p in resp.json()]


class _SLOBindings:
    """SLO binding CRUD (new binding model — asset or group linked to SLO via data source)."""

    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def create_for_asset(self, asset_name: str, slo_name: str, data_source_name: str) -> SLOBinding:
        """Create an SLO binding for an asset."""
        resp = self._http.post(
            f'/assets/{asset_name}/slo-bindings',
            json={'slo_name': slo_name, 'data_source_name': data_source_name},
        )
        _raise_for_status(resp)
        return SLOBinding.model_validate(resp.json())

    def create_for_group(self, group_name: str, slo_name: str, data_source_name: str) -> SLOBinding:
        """Create an SLO binding for an asset group."""
        resp = self._http.post(
            f'/asset-groups/{group_name}/slo-bindings',
            json={'slo_name': slo_name, 'data_source_name': data_source_name},
        )
        _raise_for_status(resp)
        return SLOBinding.model_validate(resp.json())

    def list_for_asset(self, asset_name: str) -> list[SLOBinding]:
        """List SLO bindings for an asset."""
        resp = self._http.get(f'/assets/{asset_name}/slo-bindings')
        _raise_for_status(resp)
        return [SLOBinding.model_validate(b) for b in resp.json()]

    def list_for_group(self, group_name: str) -> list[SLOBinding]:
        """List SLO bindings for an asset group."""
        resp = self._http.get(f'/asset-groups/{group_name}/slo-bindings')
        _raise_for_status(resp)
        return [SLOBinding.model_validate(b) for b in resp.json()]

    def delete_for_asset(self, asset_name: str, slo_name: str) -> None:
        """Delete an SLO binding for an asset."""
        resp = self._http.delete(f'/assets/{asset_name}/slo-bindings/{slo_name}')
        _raise_for_status(resp)

    def delete_for_group(self, group_name: str, slo_name: str) -> None:
        """Delete an SLO binding for an asset group."""
        resp = self._http.delete(f'/asset-groups/{group_name}/slo-bindings/{slo_name}')
        _raise_for_status(resp)


class _SLOGroups:
    """SLO group CRUD."""

    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def create(
        self,
        name: str,
        template_slo_name: str,
        template_slo_version: int,
        gen_variables: dict[str, list[str]],
        *,
        display_name: str | None = None,
        tags: dict[str, Any] | None = None,
        author: str | None = None,
    ) -> SLOGroup:
        """Create an SLO group."""
        body: dict[str, Any] = {
            'name': name,
            'template_slo_name': template_slo_name,
            'template_slo_version': template_slo_version,
            'gen_variables': gen_variables,
        }
        if display_name is not None:
            body['display_name'] = display_name
        if tags is not None:
            body['tags'] = tags
        if author is not None:
            body['author'] = author
        resp = self._http.post('/slo-groups', json=body)
        _raise_for_status(resp)
        return SLOGroup.model_validate(resp.json())

    def get(self, name: str) -> SLOGroup:
        """Get an SLO group by name."""
        resp = self._http.get(f'/slo-groups/{name}')
        _raise_for_status(resp)
        return SLOGroup.model_validate(resp.json())

    def list(self, *, tag_key: str | None = None, tag_val: str | None = None) -> list[SLOGroup]:
        """List SLO groups."""
        params: dict[str, str] = {}
        if tag_key:
            params['tag_key'] = tag_key
        if tag_val:
            params['tag_val'] = tag_val
        resp = self._http.get('/slo-groups', params=params)
        _raise_for_status(resp)
        data = resp.json()
        items = data.get('items', data) if isinstance(data, dict) else data
        return [SLOGroup.model_validate(g) for g in items]

    def update(
        self,
        name: str,
        *,
        template_slo_name: str | None = None,
        template_slo_version: int | None = None,
        gen_variables: dict[str, list[str]] | None = None,
        display_name: str | None = None,
        tags: dict[str, Any] | None = None,
    ) -> SLOGroup:
        """Update an SLO group (triggers regeneration)."""
        body: dict[str, Any] = {}
        if template_slo_name is not None:
            body['template_slo_name'] = template_slo_name
        if template_slo_version is not None:
            body['template_slo_version'] = template_slo_version
        if gen_variables is not None:
            body['gen_variables'] = gen_variables
        if display_name is not None:
            body['display_name'] = display_name
        if tags is not None:
            body['tags'] = tags
        resp = self._http.put(f'/slo-groups/{name}', json=body)
        _raise_for_status(resp)
        return SLOGroup.model_validate(resp.json())

    def delete(self, name: str) -> None:
        """Delete (deactivate) an SLO group."""
        resp = self._http.delete(f'/slo-groups/{name}')
        _raise_for_status(resp)

    def extract(self, group_name: str, slo_name: str, new_name: str) -> None:
        """Extract a generated SLO to standalone."""
        resp = self._http.post(
            f'/slo-groups/{group_name}/extract',
            json={'slo_name': slo_name, 'new_name': new_name},
        )
        _raise_for_status(resp)


class _TemplateBindings:
    """Template binding CRUD."""

    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def create_for_asset(self, asset_name: str, template_group_name: str, data_source_name: str) -> TemplateBinding:
        """Create a template binding for an asset."""
        resp = self._http.post(
            f'/assets/{asset_name}/template-bindings',
            json={'template_group_name': template_group_name, 'data_source_name': data_source_name},
        )
        _raise_for_status(resp)
        return TemplateBinding.model_validate(resp.json())

    def create_for_group(self, group_name: str, template_group_name: str, data_source_name: str) -> TemplateBinding:
        """Create a template binding for an asset group."""
        resp = self._http.post(
            f'/asset-groups/{group_name}/template-bindings',
            json={'template_group_name': template_group_name, 'data_source_name': data_source_name},
        )
        _raise_for_status(resp)
        return TemplateBinding.model_validate(resp.json())

    def list_for_asset(self, asset_name: str) -> list[TemplateBinding]:
        """List template bindings for an asset."""
        resp = self._http.get(f'/assets/{asset_name}/template-bindings')
        _raise_for_status(resp)
        return [TemplateBinding.model_validate(b) for b in resp.json()]

    def list_for_group(self, group_name: str) -> list[TemplateBinding]:
        """List template bindings for an asset group."""
        resp = self._http.get(f'/asset-groups/{group_name}/template-bindings')
        _raise_for_status(resp)
        return [TemplateBinding.model_validate(b) for b in resp.json()]

    def delete_for_asset(self, asset_name: str, template_group_name: str) -> None:
        """Delete a template binding for an asset."""
        resp = self._http.delete(f'/assets/{asset_name}/template-bindings/{template_group_name}')
        _raise_for_status(resp)

    def delete_for_group(self, group_name: str, template_group_name: str) -> None:
        """Delete a template binding for an asset group."""
        resp = self._http.delete(f'/asset-groups/{group_name}/template-bindings/{template_group_name}')
        _raise_for_status(resp)


class TropekClient:
    """Typed Python client for the TROPEK API."""

    def __init__(self, base_url: str, *, api_key: str | None = None) -> None:
        self._http = httpx.Client(base_url=base_url, timeout=30.0)
        if api_key:
            self._http.headers['Authorization'] = f'Bearer {api_key}'
        self.asset_types = _AssetTypes(self._http)
        self.assets = _Assets(self._http)
        self.asset_groups = _AssetGroups(self._http)
        self.asset_slo_links: _SLOLinks[AssetSLOLink] = _SLOLinks(self._http, 'assets', AssetSLOLink)
        self.group_slo_links: _SLOLinks[AssetGroupSLOLink] = _SLOLinks(self._http, 'asset-groups', AssetGroupSLOLink)
        self.datasources = _DataSources(self._http)
        self.sli_definitions = _SLIDefinitions(self._http)
        self.slo_definitions = _SLODefinitions(self._http)
        self.slo_bindings = _SLOBindings(self._http)
        self.slo_groups = _SLOGroups(self._http)
        self.template_bindings = _TemplateBindings(self._http)
        self.evaluations = _Evaluations(self._http)
        self.annotations = _Annotations(self._http)
        self.trend = _Trend(self._http)

    def health(self) -> dict[str, str]:
        """Check API health."""
        resp = self._http.get('/health')
        _raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]

    def close(self) -> None:
        """Close the HTTP client."""
        self._http.close()

    def __enter__(self) -> TropekClient:
        """Enter context manager."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context manager."""
        self.close()
