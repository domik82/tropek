"""Typed HTTP client for the TROPEK API."""

from __future__ import annotations

from typing import Any

from tropek_client._http import HttpSession
from tropek_client.models import (
    AddMemberRequest,
    AddSubgroupRequest,
    AnnotationCategoryCreate,
    AnnotationCategoryRead,
    AnnotationCategoryUpdate,
    AnnotationCreate,
    AnnotationHide,
    AnnotationRead,
    AnnotationUpdate,
    AssetCreate,
    AssetGroupCreate,
    AssetGroupRead,
    AssetGroupTreeResponse,
    AssetGroupUpdate,
    AssetRead,
    AssetTypeCreate,
    AssetTypeRead,
    AssetTypeUpdate,
    AssetUpdate,
    BulkActionResponse,
    BulkTriageRequest,
    ChangePointConfigInput,
    ChangePointConfigRead,
    ChangePointRead,
    ComparisonConfig,
    ConfigurationRead,
    DataSourceCreate,
    DataSourceRead,
    DataSourceUpdate,
    DisplayGroupCreate,
    DisplayGroupMemberAdd,
    DisplayGroupRead,
    EvaluateBatchRequest,
    EvaluateBatchResponse,
    EvaluateSingleRequest,
    EvaluateSingleResponse,
    EvaluationDetail,
    EvaluationNameEntry,
    EvaluationSummary,
    ExtractRequest,
    GroupedMetricHeatmapResponse,
    InvalidateManyRequest,
    InvalidateRequest,
    MetaSnapshotCreate,
    MetaSnapshotCreated,
    MetaSnapshotDetail,
    MetaSnapshotSummary,
    MethodCriteriaOverride,
    MetricHeatmapResponse,
    OverrideStatusManyRequest,
    OverrideStatusRequest,
    PagedResponse,
    PinBaselineManyRequest,
    PinBaselineRequest,
    ReEvaluateFromBaselineRequest,
    ReEvaluateFromDateRequest,
    ReEvaluateFromEvaluationRequest,
    ReEvaluateResponse,
    RestoreManyRequest,
    RestoreOverrideManyRequest,
    SLIDefinitionCreate,
    SLIDefinitionRead,
    SLOAssignmentRead,
    SLOAssignmentUpgrade,
    SLOAssignmentUpsert,
    SLODefinitionCreate,
    SLODefinitionRead,
    SLOGroupAssignmentRead,
    SLOGroupAssignmentUpsert,
    SLOGroupCreate,
    SLOGroupRead,
    SLOGroupUpdate,
    SLOObjectiveIn,
    SLOTestRequest,
    SLOTestResult,
    SLOValidateRequest,
    SLOValidationResult,
    TagKeyCount,
    TagValueCount,
    TimelineResponse,
    TimelineSummaryResponse,
    TrendPoint,
    TriageRequest,
    UnpinBaselineManyRequest,
)


class _AssetTypes:
    def __init__(self, http: HttpSession) -> None:
        self._http = http

    def list(self) -> PagedResponse[AssetTypeRead]:
        response = self._http.get('/asset-types')
        data = response.json()
        return PagedResponse(
            items=[AssetTypeRead.model_validate(i) for i in data['items']],
            total=data['total'],
        )

    def create(self, body: AssetTypeCreate) -> AssetTypeRead:
        response = self._http.post('/asset-types', json=body.model_dump(mode='json', exclude_none=True))
        return AssetTypeRead.model_validate(response.json())

    def set_default(self, name: str) -> AssetTypeRead:
        response = self._http.patch(f'/asset-types/{name}/set-default')
        return AssetTypeRead.model_validate(response.json())

    def rename(self, name: str, body: AssetTypeUpdate) -> AssetTypeRead:
        response = self._http.patch(f'/asset-types/{name}', json=body.model_dump(mode='json', exclude_none=True))
        return AssetTypeRead.model_validate(response.json())

    def delete(self, name: str) -> None:
        self._http.delete(f'/asset-types/{name}')


class _Assets:
    def __init__(self, http: HttpSession) -> None:
        self._http = http

    def list(
        self,
        *,
        type_name: str | None = None,
        tag_key: str | None = None,
        tag_val: str | None = None,
    ) -> PagedResponse[AssetRead]:
        params: dict[str, str] = {}
        if type_name:
            params['type_name'] = type_name
        if tag_key:
            params['tag_key'] = tag_key
        if tag_val:
            params['tag_val'] = tag_val
        response = self._http.get('/assets', params=params)
        data = response.json()
        return PagedResponse(
            items=[AssetRead.model_validate(i) for i in data['items']],
            total=data['total'],
        )

    def create(self, body: AssetCreate) -> AssetRead:
        response = self._http.post('/assets', json=body.model_dump(mode='json', exclude_none=True))
        return AssetRead.model_validate(response.json())

    def get(self, name: str) -> AssetRead:
        response = self._http.get(f'/assets/{name}')
        return AssetRead.model_validate(response.json())

    def update(self, name: str, body: AssetUpdate) -> AssetRead:
        response = self._http.patch(f'/assets/{name}', json=body.model_dump(mode='json', exclude_none=True))
        return AssetRead.model_validate(response.json())

    def delete(self, name: str) -> None:
        self._http.delete(f'/assets/{name}')

    def tag_keys(self) -> list[TagKeyCount]:
        response = self._http.get('/assets/tag-keys')
        return [TagKeyCount.model_validate(i) for i in response.json()]

    def tag_values(self, key: str) -> list[TagValueCount]:
        response = self._http.get('/assets/tag-values', params={'key': key})
        return [TagValueCount.model_validate(i) for i in response.json()]


class _AssetGroups:
    def __init__(self, http: HttpSession) -> None:
        self._http = http

    def list(self) -> PagedResponse[AssetGroupRead]:
        response = self._http.get('/asset-groups')
        data = response.json()
        return PagedResponse(
            items=[AssetGroupRead.model_validate(i) for i in data['items']],
            total=data['total'],
        )

    def tree(self) -> AssetGroupTreeResponse:
        response = self._http.get('/asset-groups/tree')
        return AssetGroupTreeResponse.model_validate(response.json())

    def create(self, body: AssetGroupCreate) -> AssetGroupRead:
        response = self._http.post('/asset-groups', json=body.model_dump(mode='json', exclude_none=True))
        return AssetGroupRead.model_validate(response.json())

    def get(self, name: str) -> AssetGroupRead:
        response = self._http.get(f'/asset-groups/{name}')
        return AssetGroupRead.model_validate(response.json())

    def update(self, name: str, body: AssetGroupUpdate) -> AssetGroupRead:
        response = self._http.patch(f'/asset-groups/{name}', json=body.model_dump(mode='json', exclude_none=True))
        return AssetGroupRead.model_validate(response.json())

    def delete(self, name: str) -> None:
        self._http.delete(f'/asset-groups/{name}')

    def add_member(self, group_name: str, body: AddMemberRequest) -> AssetGroupRead:
        response = self._http.post(
            f'/asset-groups/{group_name}/members', json=body.model_dump(mode='json', exclude_none=True)
        )
        return AssetGroupRead.model_validate(response.json())

    def remove_member(self, group_name: str, asset_id: str) -> None:
        self._http.delete(f'/asset-groups/{group_name}/members/{asset_id}')

    def add_subgroup(self, group_name: str, body: AddSubgroupRequest) -> AssetGroupRead:
        response = self._http.post(
            f'/asset-groups/{group_name}/subgroups', json=body.model_dump(mode='json', exclude_none=True)
        )
        return AssetGroupRead.model_validate(response.json())

    def remove_subgroup(self, group_name: str, child_group_id: str) -> None:
        self._http.delete(f'/asset-groups/{group_name}/subgroups/{child_group_id}')


class _DataSources:
    def __init__(self, http: HttpSession) -> None:
        self._http = http

    def list(self, *, adapter_type: str | None = None) -> PagedResponse[DataSourceRead]:
        params: dict[str, str] = {}
        if adapter_type:
            params['adapter_type'] = adapter_type
        response = self._http.get('/datasources', params=params)
        data = response.json()
        return PagedResponse(
            items=[DataSourceRead.model_validate(i) for i in data['items']],
            total=data['total'],
        )

    def create(self, body: DataSourceCreate) -> DataSourceRead:
        response = self._http.post('/datasources', json=body.model_dump(mode='json', exclude_none=True))
        return DataSourceRead.model_validate(response.json())

    def get(self, name: str) -> DataSourceRead:
        response = self._http.get(f'/datasources/{name}')
        return DataSourceRead.model_validate(response.json())

    def update(self, name: str, body: DataSourceUpdate) -> DataSourceRead:
        response = self._http.patch(f'/datasources/{name}', json=body.model_dump(mode='json', exclude_none=True))
        return DataSourceRead.model_validate(response.json())

    def delete(self, name: str) -> None:
        self._http.delete(f'/datasources/{name}')

    def tag_keys(self) -> list[TagKeyCount]:
        response = self._http.get('/datasources/tag-keys')
        return [TagKeyCount.model_validate(i) for i in response.json()]

    def tag_values(self, key: str) -> list[TagValueCount]:
        response = self._http.get('/datasources/tag-values', params={'key': key})
        return [TagValueCount.model_validate(i) for i in response.json()]


class _SLIs:
    def __init__(self, http: HttpSession) -> None:
        self._http = http

    def list(self) -> PagedResponse[SLIDefinitionRead]:
        response = self._http.get('/sli-definitions')
        data = response.json()
        return PagedResponse(
            items=[SLIDefinitionRead.model_validate(i) for i in data['items']],
            total=data['total'],
        )

    def create(self, body: SLIDefinitionCreate) -> SLIDefinitionRead:
        response = self._http.post('/sli-definitions', json=body.model_dump(mode='json', exclude_none=True))
        return SLIDefinitionRead.model_validate(response.json())

    def get(self, name: str) -> SLIDefinitionRead:
        response = self._http.get(f'/sli-definitions/{name}')
        return SLIDefinitionRead.model_validate(response.json())

    def versions(self, name: str) -> list[SLIDefinitionRead]:
        response = self._http.get(f'/sli-definitions/{name}/versions')
        return [SLIDefinitionRead.model_validate(v) for v in response.json()]

    def delete(self, name: str) -> None:
        self._http.delete(f'/sli-definitions/{name}')

    def tag_keys(self) -> list[TagKeyCount]:
        response = self._http.get('/sli-definitions/tag-keys')
        return [TagKeyCount.model_validate(i) for i in response.json()]

    def tag_values(self, key: str) -> list[TagValueCount]:
        response = self._http.get('/sli-definitions/tag-values', params={'key': key})
        return [TagValueCount.model_validate(i) for i in response.json()]

    def new_version(self, name: str, **overrides: Any) -> SLIDefinitionRead:
        current = self.get(name)
        base = SLIDefinitionCreate(
            name=current.name,
            adapter_type=current.adapter_type,
            display_name=current.display_name,
            mode=current.mode,
            indicators=current.indicators or None,
            query_template=current.query_template,
            interval=current.interval,
            methods=current.methods,
            notes=current.notes,
            author=current.author,
            tags=dict(current.tags) if current.tags else None,
        )
        body = base.model_copy(update=overrides)
        return self.create(body)


class _SLOs:
    def __init__(self, http: HttpSession) -> None:
        self._http = http

    def list(self) -> PagedResponse[SLODefinitionRead]:
        response = self._http.get('/slo-definitions')
        data = response.json()
        return PagedResponse(
            items=[SLODefinitionRead.model_validate(i) for i in data['items']],
            total=data['total'],
        )

    def create(self, body: SLODefinitionCreate) -> SLODefinitionRead:
        response = self._http.post('/slo-definitions', json=body.model_dump(mode='json', exclude_none=True))
        return SLODefinitionRead.model_validate(response.json())

    def get(self, name: str) -> SLODefinitionRead:
        response = self._http.get(f'/slo-definitions/{name}')
        return SLODefinitionRead.model_validate(response.json())

    def versions(self, name: str) -> list[SLODefinitionRead]:
        response = self._http.get(f'/slo-definitions/{name}/versions')
        return [SLODefinitionRead.model_validate(v) for v in response.json()]

    def delete(self, name: str) -> None:
        self._http.delete(f'/slo-definitions/{name}')

    def tag_keys(self) -> list[TagKeyCount]:
        response = self._http.get('/slo-definitions/tag-keys')
        return [TagKeyCount.model_validate(i) for i in response.json()]

    def tag_values(self, key: str) -> list[TagValueCount]:
        response = self._http.get('/slo-definitions/tag-values', params={'key': key})
        return [TagValueCount.model_validate(i) for i in response.json()]

    def validate(self, body: SLOValidateRequest) -> SLOValidationResult:
        response = self._http.post('/slo-definitions/validate', json=body.model_dump(mode='json', exclude_none=True))
        return SLOValidationResult.model_validate(response.json())

    def test(self, body: SLOTestRequest) -> SLOTestResult:
        response = self._http.post('/slo-definitions/test', json=body.model_dump(mode='json', exclude_none=True))
        return SLOTestResult.model_validate(response.json())

    def new_version(self, name: str, **overrides: Any) -> SLODefinitionRead:
        current = self.get(name)
        objectives_for_create = [
            SLOObjectiveIn.model_validate(
                objective.model_dump(exclude={'sort_order', 'change_point'})
                | (
                    {'change_point': objective.change_point.model_dump(exclude={'slo_objective_id'})}
                    if objective.change_point
                    else {}
                )
            )
            for objective in current.objectives
        ]
        comparison_for_create = (
            ComparisonConfig.model_validate(current.comparison.model_dump()) if current.comparison else None
        )
        method_criteria_for_create = (
            {
                key: MethodCriteriaOverride.model_validate(override.model_dump())
                for key, override in current.method_criteria.items()
            }
            if current.method_criteria
            else None
        )
        base = SLODefinitionCreate(
            name=current.name,
            display_name=current.display_name,
            objectives=objectives_for_create,
            total_score_pass_threshold=current.total_score_pass_threshold,
            total_score_warning_threshold=current.total_score_warning_threshold,
            comparison=comparison_for_create,
            notes=current.notes,
            author=current.author,
            tags=dict(current.tags) if current.tags else None,
            variables=dict(current.variables) if current.variables else None,
            kind=current.kind,
            sli_name=current.sli_name,
            sli_version=current.sli_version,
            method_criteria=method_criteria_for_create,
        )
        body = base.model_copy(update=overrides)
        return self.create(body)


class _Evaluations:
    def __init__(self, http: HttpSession, change_points: _ChangePoints) -> None:
        self._http = http
        self._change_points = change_points

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
        response = self._http.get('/evaluations', params=params)
        data = response.json()
        return PagedResponse(
            items=[EvaluationSummary.model_validate(i) for i in data['items']],
            total=data['total'],
        )

    def get(self, eval_id: str) -> EvaluationDetail:
        response = self._http.get(f'/evaluation/{eval_id}')
        return EvaluationDetail.model_validate(response.json())

    def trigger(self, body: EvaluateSingleRequest) -> EvaluateSingleResponse:
        response = self._http.post('/evaluations', json=body.model_dump(mode='json', exclude_none=True))
        return EvaluateSingleResponse.model_validate(response.json())

    def trigger_batch(self, body: EvaluateBatchRequest) -> EvaluateBatchResponse:
        response = self._http.post('/evaluations/batch', json=body.model_dump(mode='json', exclude_none=True))
        return EvaluateBatchResponse.model_validate(response.json())

    def invalidate(self, eval_id: str, body: InvalidateRequest) -> EvaluationSummary:
        response = self._http.patch(f'/evaluation/{eval_id}/invalidate', json=body.model_dump(mode='json'))
        return EvaluationSummary.model_validate(response.json())

    def restore(self, eval_id: str) -> EvaluationSummary:
        response = self._http.patch(f'/evaluation/{eval_id}/restore')
        return EvaluationSummary.model_validate(response.json())

    def pin_baseline(self, eval_id: str, body: PinBaselineRequest) -> EvaluationDetail:
        response = self._http.patch(f'/evaluation/{eval_id}/pin-baseline', json=body.model_dump(mode='json'))
        return EvaluationDetail.model_validate(response.json())

    def unpin_baseline(self, eval_id: str) -> EvaluationDetail:
        response = self._http.patch(f'/evaluation/{eval_id}/unpin-baseline')
        return EvaluationDetail.model_validate(response.json())

    def override_status(self, eval_id: str, body: OverrideStatusRequest) -> EvaluationDetail:
        response = self._http.patch(f'/evaluation/{eval_id}/override-status', json=body.model_dump(mode='json'))
        return EvaluationDetail.model_validate(response.json())

    def restore_override(self, eval_id: str) -> EvaluationDetail:
        response = self._http.patch(f'/evaluation/{eval_id}/restore-override')
        return EvaluationDetail.model_validate(response.json())

    def invalidate_many(self, body: InvalidateManyRequest) -> BulkActionResponse:
        response = self._http.patch('/evaluations/invalidate', json=body.model_dump(mode='json'))
        return BulkActionResponse.model_validate(response.json())

    def restore_many(self, body: RestoreManyRequest) -> BulkActionResponse:
        response = self._http.patch('/evaluations/restore', json=body.model_dump(mode='json'))
        return BulkActionResponse.model_validate(response.json())

    def override_status_many(self, body: OverrideStatusManyRequest) -> BulkActionResponse:
        response = self._http.patch('/evaluations/override-status', json=body.model_dump(mode='json'))
        return BulkActionResponse.model_validate(response.json())

    def restore_override_many(self, body: RestoreOverrideManyRequest) -> BulkActionResponse:
        response = self._http.patch('/evaluations/restore-override', json=body.model_dump(mode='json'))
        return BulkActionResponse.model_validate(response.json())

    def pin_baseline_many(self, body: PinBaselineManyRequest) -> BulkActionResponse:
        response = self._http.patch('/evaluations/pin-baseline', json=body.model_dump(mode='json'))
        return BulkActionResponse.model_validate(response.json())

    def unpin_baseline_many(self, body: UnpinBaselineManyRequest) -> BulkActionResponse:
        response = self._http.patch('/evaluations/unpin-baseline', json=body.model_dump(mode='json'))
        return BulkActionResponse.model_validate(response.json())

    def re_evaluate_from_date(self, body: ReEvaluateFromDateRequest) -> ReEvaluateResponse:
        response = self._http.post(
            '/evaluations/re-evaluate/from-date', json=body.model_dump(mode='json', exclude_none=True)
        )
        return ReEvaluateResponse.model_validate(response.json())

    def re_evaluate_from_baseline(self, body: ReEvaluateFromBaselineRequest) -> ReEvaluateResponse:
        response = self._http.post(
            '/evaluations/re-evaluate/from-baseline', json=body.model_dump(mode='json', exclude_none=True)
        )
        return ReEvaluateResponse.model_validate(response.json())

    def re_evaluate_from_evaluation(
        self, evaluation_id: str, body: ReEvaluateFromEvaluationRequest
    ) -> ReEvaluateResponse:
        response = self._http.post(
            f'/evaluations/re-evaluate/from-evaluation/{evaluation_id}',
            json=body.model_dump(mode='json', exclude_none=True),
        )
        return ReEvaluateResponse.model_validate(response.json())

    def names(self, *, asset_name: str | None = None, group_name: str | None = None) -> list[EvaluationNameEntry]:
        params: dict[str, str] = {}
        if asset_name:
            params['asset_name'] = asset_name
        if group_name:
            params['group_name'] = group_name
        response = self._http.get('/evaluations/names', params=params)
        return [EvaluationNameEntry.model_validate(e) for e in response.json()]

    def triage(self, change_point_id: str, body: TriageRequest) -> ChangePointRead:
        """Deprecated alias for client.change_points.triage."""
        return self._change_points.triage(change_point_id, body)


class _ChangePoints:
    def __init__(self, http: HttpSession) -> None:
        self._http = http

    def list(  # noqa: PLR0913
        self,
        *,
        status: str | None = None,
        direction: str | None = None,
        asset_id: str | None = None,
        slo_name: str | None = None,
        metric_name: str | None = None,
        from_ts: str | None = None,
        to_ts: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ChangePointRead]:
        params: dict[str, str] = {}
        if status:
            params['status'] = status
        if direction:
            params['direction'] = direction
        if asset_id:
            params['asset_id'] = asset_id
        if slo_name:
            params['slo_name'] = slo_name
        if metric_name:
            params['metric_name'] = metric_name
        if from_ts:
            params['from_ts'] = from_ts
        if to_ts:
            params['to_ts'] = to_ts
        if limit is not None:
            params['limit'] = str(limit)
        if offset is not None:
            params['offset'] = str(offset)
        response = self._http.get('/change-points', params=params)
        return [ChangePointRead.model_validate(row) for row in response.json()]

    def get(self, change_point_id: str) -> ChangePointRead:
        response = self._http.get(f'/change-points/{change_point_id}')
        return ChangePointRead.model_validate(response.json())

    def triage(self, change_point_id: str, body: TriageRequest) -> ChangePointRead:
        response = self._http.patch(
            f'/change-points/{change_point_id}', json=body.model_dump(mode='json', exclude_none=True)
        )
        return ChangePointRead.model_validate(response.json())

    def bulk_triage(self, body: BulkTriageRequest) -> dict[str, int]:
        response = self._http.patch('/change-points/bulk-triage', json=body.model_dump(mode='json', exclude_none=True))
        return response.json()  # type: ignore[no-any-return]

    def get_config(self, objective_id: str) -> ChangePointConfigRead:
        response = self._http.get(f'/change-points/config/{objective_id}')
        return ChangePointConfigRead.model_validate(response.json())

    def set_config(self, objective_id: str, body: ChangePointConfigInput) -> ChangePointConfigRead:
        response = self._http.put(
            f'/change-points/config/{objective_id}', json=body.model_dump(mode='json', exclude_none=True)
        )
        return ChangePointConfigRead.model_validate(response.json())

    def delete_config(self, objective_id: str) -> None:
        self._http.delete(f'/change-points/config/{objective_id}')


class _Annotations:
    def __init__(self, http: HttpSession) -> None:
        self._http = http

    def list(self, eval_id: str) -> list[AnnotationRead]:
        response = self._http.get(f'/evaluation/{eval_id}/annotations')
        return [AnnotationRead.model_validate(a) for a in response.json()]

    def create(self, eval_id: str, body: AnnotationCreate) -> AnnotationRead:
        response = self._http.post(
            f'/evaluation/{eval_id}/annotations', json=body.model_dump(mode='json', exclude_none=True)
        )
        return AnnotationRead.model_validate(response.json())

    def create_for_run(self, run_id: str, body: AnnotationCreate) -> AnnotationRead:
        response = self._http.post(
            f'/evaluation-run/{run_id}/annotations', json=body.model_dump(mode='json', exclude_none=True)
        )
        return AnnotationRead.model_validate(response.json())

    def update(self, eval_id: str, ann_id: str, body: AnnotationUpdate) -> AnnotationRead:
        response = self._http.patch(
            f'/evaluation/{eval_id}/annotations/{ann_id}', json=body.model_dump(mode='json', exclude_none=True)
        )
        return AnnotationRead.model_validate(response.json())

    def hide(self, eval_id: str, ann_id: str, body: AnnotationHide) -> AnnotationRead:
        response = self._http.post(
            f'/evaluation/{eval_id}/annotations/{ann_id}/hide',
            json=body.model_dump(mode='json', exclude_none=True),
        )
        return AnnotationRead.model_validate(response.json())


class _AnnotationCategories:
    def __init__(self, http: HttpSession) -> None:
        self._http = http

    def list(self) -> list[AnnotationCategoryRead]:
        response = self._http.get('/note-categories')
        return [AnnotationCategoryRead.model_validate(c) for c in response.json()]

    def create(self, body: AnnotationCategoryCreate) -> AnnotationCategoryRead:
        response = self._http.post('/note-categories', json=body.model_dump(mode='json', exclude_none=True))
        return AnnotationCategoryRead.model_validate(response.json())

    def update(self, category_id: str, body: AnnotationCategoryUpdate) -> AnnotationCategoryRead:
        response = self._http.patch(
            f'/note-categories/{category_id}', json=body.model_dump(mode='json', exclude_none=True)
        )
        return AnnotationCategoryRead.model_validate(response.json())

    def delete(self, category_id: str) -> None:
        self._http.delete(f'/note-categories/{category_id}')


class _Trend:
    def __init__(self, http: HttpSession) -> None:
        self._http = http

    def by_eval(
        self,
        eval_id: str,
        metric: str,
        from_: str,
        *,
        to: str | None = None,
    ) -> list[TrendPoint]:
        params: dict[str, str] = {'metric': metric, 'from': from_}
        if to is not None:
            params['to'] = to
        response = self._http.get(f'/evaluation/{eval_id}/trend', params=params)
        return [TrendPoint.model_validate(p) for p in response.json()]

    def by_asset(
        self,
        asset_name: str,
        slo_name: str,
        metric: str,
        from_: str,
        *,
        to: str | None = None,
    ) -> list[TrendPoint]:
        params: dict[str, str] = {'metric': metric, 'from': from_}
        if to is not None:
            params['to'] = to
        response = self._http.get(f'/assets/{asset_name}/slos/{slo_name}/trend', params=params)
        return [TrendPoint.model_validate(p) for p in response.json()]


class _Heatmap:
    def __init__(self, http: HttpSession) -> None:
        self._http = http

    def grouped(
        self,
        asset_name: str,
        *,
        eval_name: str | None = None,
        from_: str | None = None,
        to: str | None = None,
    ) -> GroupedMetricHeatmapResponse:
        params: dict[str, Any] = {'asset_name': asset_name}
        if eval_name:
            params['evaluation_name'] = eval_name
        if from_ is not None:
            params['from'] = from_
        if to is not None:
            params['to'] = to
        response = self._http.get('/evaluations/heatmap', params=params)
        return GroupedMetricHeatmapResponse.model_validate(response.json())

    def flat(
        self,
        asset_name: str,
        *,
        eval_name: str | None = None,
        from_: str | None = None,
        to: str | None = None,
    ) -> MetricHeatmapResponse:
        params: dict[str, Any] = {'asset_name': asset_name}
        if eval_name:
            params['evaluation_name'] = eval_name
        if from_ is not None:
            params['from'] = from_
        if to is not None:
            params['to'] = to
        response = self._http.get('/evaluations/heatmap/by-metric', params=params)
        return MetricHeatmapResponse.model_validate(response.json())


class _Timeline:
    def __init__(self, http: HttpSession) -> None:
        self._http = http

    def get(self, asset_id: str, *, from_: str, to: str) -> TimelineResponse:
        response = self._http.get(f'/assets/{asset_id}/meta/timeline', params={'from': from_, 'to': to})
        return TimelineResponse.model_validate(response.json())

    def summary(self, asset_id: str, *, from_: str, to: str) -> TimelineSummaryResponse:
        response = self._http.get(f'/assets/{asset_id}/meta/timeline/summary', params={'from': from_, 'to': to})
        return TimelineSummaryResponse.model_validate(response.json())


class _SLOAssignments:
    def __init__(self, http: HttpSession) -> None:
        self._http = http

    def create_for_asset(self, asset_name: str, slo_definition_id: str, body: SLOAssignmentUpsert) -> SLOAssignmentRead:
        response = self._http.put(
            f'/assets/{asset_name}/slo-definitions/{slo_definition_id}',
            json=body.model_dump(mode='json', exclude_none=True),
        )
        return SLOAssignmentRead.model_validate(response.json())

    def create_for_group(self, group_name: str, slo_definition_id: str, body: SLOAssignmentUpsert) -> SLOAssignmentRead:
        response = self._http.put(
            f'/asset-groups/{group_name}/slo-definitions/{slo_definition_id}',
            json=body.model_dump(mode='json', exclude_none=True),
        )
        return SLOAssignmentRead.model_validate(response.json())

    def list_for_asset(self, asset_name: str) -> list[SLOAssignmentRead]:
        response = self._http.get(f'/assets/{asset_name}/slo-assignments')
        return [SLOAssignmentRead.model_validate(a) for a in response.json()]

    def list_for_group(self, group_name: str) -> list[SLOAssignmentRead]:
        response = self._http.get(f'/asset-groups/{group_name}/slo-assignments')
        return [SLOAssignmentRead.model_validate(a) for a in response.json()]

    def upgrade(self, asset_name: str, assignment_id: str, body: SLOAssignmentUpgrade) -> SLOAssignmentRead:
        response = self._http.patch(
            f'/assets/{asset_name}/slo-assignments/{assignment_id}',
            json=body.model_dump(mode='json'),
        )
        return SLOAssignmentRead.model_validate(response.json())

    def delete_for_asset(self, asset_name: str, slo_definition_id: str) -> None:
        self._http.delete(f'/assets/{asset_name}/slo-definitions/{slo_definition_id}')

    def delete_for_group(self, group_name: str, slo_definition_id: str) -> None:
        self._http.delete(f'/asset-groups/{group_name}/slo-definitions/{slo_definition_id}')


class _SLOGroups:
    def __init__(self, http: HttpSession) -> None:
        self._http = http

    def list(self, *, tag_key: str | None = None, tag_val: str | None = None) -> PagedResponse[SLOGroupRead]:
        params: dict[str, str] = {}
        if tag_key:
            params['tag_key'] = tag_key
        if tag_val:
            params['tag_val'] = tag_val
        response = self._http.get('/slo-groups', params=params)
        data = response.json()
        return PagedResponse(
            items=[SLOGroupRead.model_validate(g) for g in data['items']],
            total=data['total'],
        )

    def create(self, body: SLOGroupCreate) -> SLOGroupRead:
        response = self._http.post('/slo-groups', json=body.model_dump(mode='json', exclude_none=True))
        return SLOGroupRead.model_validate(response.json())

    def get(self, name: str) -> SLOGroupRead:
        response = self._http.get(f'/slo-groups/{name}')
        return SLOGroupRead.model_validate(response.json())

    def update(self, name: str, body: SLOGroupUpdate) -> SLOGroupRead:
        response = self._http.put(f'/slo-groups/{name}', json=body.model_dump(mode='json', exclude_none=True))
        return SLOGroupRead.model_validate(response.json())

    def delete(self, name: str) -> None:
        self._http.delete(f'/slo-groups/{name}')

    def extract(self, group_name: str, body: ExtractRequest) -> None:
        self._http.post(f'/slo-groups/{group_name}/extract', json=body.model_dump(mode='json'))


class _DisplayGroups:
    def __init__(self, http: HttpSession) -> None:
        self._http = http

    def list(self) -> list[DisplayGroupRead]:
        response = self._http.get('/slo-display-groups')
        return [DisplayGroupRead.model_validate(d) for d in response.json()]

    def create(self, body: DisplayGroupCreate) -> DisplayGroupRead:
        response = self._http.post('/slo-display-groups', json=body.model_dump(mode='json', exclude_none=True))
        return DisplayGroupRead.model_validate(response.json())

    def delete(self, name: str) -> None:
        self._http.delete(f'/slo-display-groups/{name}')

    def list_members(self, name: str) -> list[str]:
        response = self._http.get(f'/slo-display-groups/{name}/members')
        return response.json()

    def add_member(self, name: str, body: DisplayGroupMemberAdd) -> None:
        self._http.post(
            f'/slo-display-groups/{name}/members',
            json=body.model_dump(mode='json'),
        )

    def remove_member(self, name: str, slo_name: str) -> None:
        self._http.delete(f'/slo-display-groups/{name}/members/{slo_name}')


class _SLOGroupAssignments:
    def __init__(self, http: HttpSession) -> None:
        self._http = http

    def create_for_asset(
        self, asset_name: str, slo_group_name: str, body: SLOGroupAssignmentUpsert
    ) -> SLOGroupAssignmentRead:
        response = self._http.put(
            f'/assets/{asset_name}/slo-groups/{slo_group_name}', json=body.model_dump(mode='json')
        )
        return SLOGroupAssignmentRead.model_validate(response.json())

    def create_for_group(
        self, group_name: str, slo_group_name: str, body: SLOGroupAssignmentUpsert
    ) -> SLOGroupAssignmentRead:
        response = self._http.put(
            f'/asset-groups/{group_name}/slo-groups/{slo_group_name}', json=body.model_dump(mode='json')
        )
        return SLOGroupAssignmentRead.model_validate(response.json())

    def list_for_asset(self, asset_name: str) -> list[SLOGroupAssignmentRead]:
        response = self._http.get(f'/assets/{asset_name}/slo-group-assignments')
        return [SLOGroupAssignmentRead.model_validate(a) for a in response.json()]

    def list_for_group(self, group_name: str) -> list[SLOGroupAssignmentRead]:
        response = self._http.get(f'/asset-groups/{group_name}/slo-group-assignments')
        return [SLOGroupAssignmentRead.model_validate(a) for a in response.json()]

    def delete_for_asset(self, asset_name: str, slo_group_name: str) -> None:
        self._http.delete(f'/assets/{asset_name}/slo-groups/{slo_group_name}')

    def delete_for_group(self, group_name: str, slo_group_name: str) -> None:
        self._http.delete(f'/asset-groups/{group_name}/slo-groups/{slo_group_name}')


class _Configuration:
    def __init__(self, http: HttpSession) -> None:
        self._http = http

    def list(self) -> list[ConfigurationRead]:
        response = self._http.get('/configuration')
        return [ConfigurationRead.model_validate(c) for c in response.json()]

    def get(self, name: str) -> ConfigurationRead:
        response = self._http.get(f'/configuration/{name}')
        return ConfigurationRead.model_validate(response.json())

    def update(self, name: str, value: str) -> ConfigurationRead:
        response = self._http.put(f'/configuration/{name}', json={'value': value})
        return ConfigurationRead.model_validate(response.json())


class _Meta:
    def __init__(self, http: HttpSession) -> None:
        self._http = http

    def create_snapshot(self, asset_id: str, body: MetaSnapshotCreate) -> MetaSnapshotCreated:
        """Ingest a point-in-time metadata snapshot for an asset."""
        response = self._http.post(
            f'/assets/{asset_id}/meta/snapshots', json=body.model_dump(mode='json', exclude_none=True)
        )
        return MetaSnapshotCreated.model_validate(response.json())

    def list_snapshots(
        self,
        asset_id: str,
        *,
        source: str | None = None,
        from_: str | None = None,
        to: str | None = None,
    ) -> list[MetaSnapshotSummary]:
        """List meta snapshots for an asset, optionally filtered by source and time range."""
        params: dict[str, str] = {}
        if source is not None:
            params['source'] = source
        if from_ is not None:
            params['from'] = from_
        if to is not None:
            params['to'] = to
        response = self._http.get(f'/assets/{asset_id}/meta/snapshots', params=params or None)
        return [MetaSnapshotSummary.model_validate(item) for item in response.json()]

    def get_snapshot(self, asset_id: str, snapshot_id: str) -> MetaSnapshotDetail:
        """Get full detail of a single meta snapshot."""
        response = self._http.get(f'/assets/{asset_id}/meta/snapshots/{snapshot_id}')
        return MetaSnapshotDetail.model_validate(response.json())

    def delete_snapshot(self, asset_id: str, snapshot_id: str) -> None:
        """Delete a meta snapshot and its associated values and closures."""
        self._http.delete(f'/assets/{asset_id}/meta/snapshots/{snapshot_id}')


class TropekClient:
    """Typed Python client for the TROPEK API."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
        verify: bool = True,
    ) -> None:
        self._http = HttpSession(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            headers=headers,
            verify=verify,
        )
        self.asset_types = _AssetTypes(self._http)
        self.assets = _Assets(self._http)
        self.asset_groups = _AssetGroups(self._http)
        self.datasources = _DataSources(self._http)
        self.slis = _SLIs(self._http)
        self.slos = _SLOs(self._http)
        self.slo_assignments = _SLOAssignments(self._http)
        self.slo_groups = _SLOGroups(self._http)
        self.slo_group_assignments = _SLOGroupAssignments(self._http)
        self.display_groups = _DisplayGroups(self._http)
        self.change_points = _ChangePoints(self._http)
        self.evaluations = _Evaluations(self._http, self.change_points)
        self.annotations = _Annotations(self._http)
        self.annotation_categories = _AnnotationCategories(self._http)
        self.trend = _Trend(self._http)
        self.heatmap = _Heatmap(self._http)
        self.timeline = _Timeline(self._http)
        self.configuration = _Configuration(self._http)
        self.meta = _Meta(self._http)

    def health(self) -> dict[str, str]:
        """Check API health."""
        response = self._http.get('/health')
        return response.json()  # type: ignore[no-any-return]

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._http.close()

    def __enter__(self) -> TropekClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
