"""TriggerService — orchestrates single and batch evaluation triggers."""

from __future__ import annotations

import uuid
from datetime import datetime

from arq.connections import ArqRedis

from app.modules.quality_gate.dependencies import QualityGateRepos
from app.modules.quality_gate.exceptions import (
    AssetNotFoundError,
    DuplicateEvaluationError,
    EvaluationError,
)
from app.modules.quality_gate.params import EvalCreateParams
from app.modules.quality_gate.schemas import (
    AssetTriggerRequest,
    AssetTriggerResponse,
    BatchConflict,
    BatchTriggerRequest,
    BatchTriggerResponse,
    EvaluateBatchRequest,
    EvaluateBatchResponse,
    EvaluateSingleRequest,
    EvaluateSingleResponse,
    TriggerRequest,
    TriggerResponse,
)
from app.modules.quality_gate.trigger import (
    TriggerContext,
    resolve_all_slos_for_asset,
    resolve_single_trigger,
)


class TriggerService:
    """Encapsulates trigger logic for single and batch evaluations."""

    def __init__(self, repos: QualityGateRepos, arq_pool: ArqRedis) -> None:
        self._repos = repos
        self._pool = arq_pool

    async def trigger_single(self, request: TriggerRequest) -> TriggerResponse:
        """Resolve references, create pending evaluation, enqueue job."""
        ctx = await resolve_single_trigger(
            asset_name=request.asset_name,
            slo_name=request.slo_name,
            asset_repo=self._repos.asset_repo,
            sli_repo=self._repos.sli_def_repo,
            slo_repo=self._repos.slo_repo,
            ds_repo=self._repos.ds_repo,
            binding_repo=self._repos.binding_repo,
        )

        # Duplicate prevention: app-level check for clean error messages.
        # The DB partial unique index is the safety net for races.
        existing = await self._repos.eval_repo.find_duplicate(
            asset_id=ctx.asset_id,
            slo_name=ctx.slo_name,
            evaluation_name=request.evaluation_name,
            period_start=request.period_start,
            period_end=request.period_end,
        )
        if existing is not None:
            if existing.status in ('pending', 'running'):
                msg = 'evaluation is already in progress for this period'
                raise DuplicateEvaluationError(msg)
            msg = 'evaluation already exists for this asset/SLO/period — use re-evaluate to re-score'
            raise DuplicateEvaluationError(msg)

        # TODO: create EvaluationRun parent first and pass its id here.
        # Transient run_id until trigger_single is reworked in a follow-on task.
        run_id = uuid.uuid4()
        ev = await self._repos.eval_repo.create_pending(
            EvalCreateParams(
                evaluation_id=run_id,
                evaluation_name=request.evaluation_name,
                period_start=request.period_start,
                period_end=request.period_end,
                ingestion_mode='pull',
                asset_snapshot={
                    'name': ctx.asset_name,
                    'display_name': ctx.asset_display_name,
                    'tags': ctx.asset_tags,
                    'variables': ctx.asset_variables,
                },
                variables=request.variables,
                asset_id=ctx.asset_id,
                slo_name=ctx.slo_name,
                slo_version=ctx.slo_version,
                sli_name=ctx.sli_name,
                sli_version=ctx.sli_version,
                data_source_name=ctx.data_source_name,
                adapter_used=ctx.adapter_type,
            )
        )
        await self._repos.session.commit()

        await self._pool.enqueue_job('run_evaluation_job', str(ev.id))
        return TriggerResponse(id=ev.id, status='pending')

    async def trigger_asset(self, request: AssetTriggerRequest) -> AssetTriggerResponse:
        """Resolve all SLOs for an asset, create one evaluation per SLO, enqueue all."""
        asset = await self._repos.asset_repo.get_by_name(request.asset_name)
        if asset is None:
            msg = f"asset '{request.asset_name}' not found"
            raise AssetNotFoundError(msg)

        group_ids = await self._repos.asset_group_repo.list_group_ids_for_asset(asset.id)

        slo_names = await resolve_all_slos_for_asset(
            asset_id=asset.id,
            binding_repo=self._repos.binding_repo,
            group_ids=group_ids,
        )

        if not slo_names:
            msg = f"no slo links or bindings found for asset '{request.asset_name}'"
            raise EvaluationError(msg)

        evaluation_ids: list[uuid.UUID] = []
        triggered_slos: list[str] = []

        for slo_name in slo_names:
            try:
                ctx = await resolve_single_trigger(
                    asset_name=request.asset_name,
                    slo_name=slo_name,
                    asset_repo=self._repos.asset_repo,
                    sli_repo=self._repos.sli_def_repo,
                    slo_repo=self._repos.slo_repo,
                    ds_repo=self._repos.ds_repo,
                    binding_repo=self._repos.binding_repo,
                )
            except EvaluationError:
                continue

            existing = await self._repos.eval_repo.find_duplicate(
                asset_id=ctx.asset_id,
                slo_name=ctx.slo_name,
                evaluation_name=request.evaluation_name,
                period_start=request.period_start,
                period_end=request.period_end,
            )
            if existing is not None:
                continue

            # TODO: create EvaluationRun parent first and pass its id here.
            # Transient run_id until trigger_asset is reworked in a follow-on task.
            run_id = uuid.uuid4()
            ev = await self._repos.eval_repo.create_pending(
                EvalCreateParams(
                    evaluation_id=run_id,
                    evaluation_name=request.evaluation_name,
                    period_start=request.period_start,
                    period_end=request.period_end,
                    ingestion_mode='pull',
                    asset_snapshot={
                        'name': ctx.asset_name,
                        'display_name': ctx.asset_display_name,
                        'tags': ctx.asset_tags,
                        'variables': ctx.asset_variables,
                    },
                    variables=request.variables,
                    asset_id=ctx.asset_id,
                    slo_name=ctx.slo_name,
                    slo_version=ctx.slo_version,
                    sli_name=ctx.sli_name,
                    sli_version=ctx.sli_version,
                    data_source_name=ctx.data_source_name,
                    adapter_used=ctx.adapter_type,
                )
            )
            evaluation_ids.append(ev.id)
            triggered_slos.append(ctx.slo_name)

        await self._repos.session.commit()

        for eid in evaluation_ids:
            await self._pool.enqueue_job('run_evaluation_job', str(eid))

        return AssetTriggerResponse(
            evaluation_ids=evaluation_ids,
            slo_names=triggered_slos,
            status='pending',
        )

    async def trigger_batch(self, request: BatchTriggerRequest) -> BatchTriggerResponse:
        """Validate batch, detect conflicts, enqueue all-or-nothing."""
        group = await self._repos.asset_group_repo.get_by_name(request.group_name)
        if group is None:
            msg = f"asset group '{request.group_name}' not found"
            raise AssetNotFoundError(msg)

        # Phase 1: resolve all triggers per member using unified SLO resolution
        resolved: list[tuple[TriggerContext, str]] = []
        conflicts: list[BatchConflict] = []

        for member in group.members:
            asset = await self._repos.asset_repo.get_by_name(member.asset_name)
            if asset is None:
                continue

            member_group_ids = await self._repos.asset_group_repo.list_group_ids_for_asset(
                asset.id,
            )
            slo_names = await resolve_all_slos_for_asset(
                asset_id=asset.id,
                binding_repo=self._repos.binding_repo,
                group_ids=member_group_ids,
            )

            for slo_name in slo_names:
                try:
                    ctx = await resolve_single_trigger(
                        asset_name=asset.name,
                        slo_name=slo_name,
                        asset_repo=self._repos.asset_repo,
                        sli_repo=self._repos.sli_def_repo,
                        slo_repo=self._repos.slo_repo,
                        ds_repo=self._repos.ds_repo,
                        binding_repo=self._repos.binding_repo,
                    )
                except EvaluationError:
                    continue

                existing = await self._repos.eval_repo.find_duplicate(
                    asset_id=ctx.asset_id,
                    slo_name=ctx.slo_name,
                    evaluation_name=request.evaluation_name,
                    period_start=request.period_start,
                    period_end=request.period_end,
                )
                if existing is not None:
                    conflicts.append(
                        BatchConflict(
                            asset_name=asset.name,
                            slo_name=ctx.slo_name,
                            evaluation_name=request.evaluation_name,
                            period_start=request.period_start,
                            period_end=request.period_end,
                            existing_status=existing.status,
                        )
                    )
                else:
                    resolved.append((ctx, asset.name))

        if conflicts:
            msg = 'batch contains duplicate evaluations'
            raise DuplicateEvaluationError(msg)

        # Phase 2: create all evaluations (single transaction)
        evaluation_ids: list[uuid.UUID] = []
        for ctx, _asset_name in resolved:
            # TODO: remove with old trigger endpoints
            run_id = uuid.uuid4()
            ev = await self._repos.eval_repo.create_pending(
                EvalCreateParams(
                    evaluation_id=run_id,
                    evaluation_name=request.evaluation_name,
                    period_start=request.period_start,
                    period_end=request.period_end,
                    ingestion_mode='pull',
                    asset_snapshot={
                        'name': ctx.asset_name,
                        'display_name': ctx.asset_display_name,
                        'tags': ctx.asset_tags,
                        'variables': ctx.asset_variables,
                    },
                    variables=request.variables,
                    asset_id=ctx.asset_id,
                    slo_name=ctx.slo_name,
                    slo_version=ctx.slo_version,
                    sli_name=ctx.sli_name,
                    sli_version=ctx.sli_version,
                    data_source_name=ctx.data_source_name,
                    adapter_used=ctx.adapter_type,
                )
            )
            evaluation_ids.append(ev.id)

        await self._repos.session.commit()

        for eid in evaluation_ids:
            await self._pool.enqueue_job('run_evaluation_job', str(eid))

        # TODO: remove with old trigger endpoints
        batch_id = uuid.uuid4()
        return BatchTriggerResponse(
            batch_id=batch_id,
            evaluation_ids=evaluation_ids,
            status='pending',
        )

    async def trigger_evaluate(self, request: EvaluateSingleRequest) -> EvaluateSingleResponse:
        """Create parent EvaluationRun + one SLOEvaluation per SLO binding. Enqueue all."""
        asset = await self._repos.asset_repo.get_by_name(request.asset_name)
        if asset is None:
            msg = f"asset '{request.asset_name}' not found"
            raise AssetNotFoundError(msg)

        group_ids = await self._repos.asset_group_repo.list_group_ids_for_asset(asset.id)
        slo_names = await resolve_all_slos_for_asset(
            asset_id=asset.id,
            binding_repo=self._repos.binding_repo,
            group_ids=group_ids,
        )
        if not slo_names:
            msg = f"no slo bindings found for asset '{request.asset_name}'"
            raise EvaluationError(msg)

        run = await self._repos.eval_run_repo.create(
            asset_id=asset.id,
            eval_name=request.eval_name,
            period_start=request.period_start,
            period_end=request.period_end,
        )

        slo_eval_ids: list[uuid.UUID] = []
        for slo_name in slo_names:
            try:
                ctx = await resolve_single_trigger(
                    asset_name=request.asset_name,
                    slo_name=slo_name,
                    asset_repo=self._repos.asset_repo,
                    sli_repo=self._repos.sli_def_repo,
                    slo_repo=self._repos.slo_repo,
                    ds_repo=self._repos.ds_repo,
                    binding_repo=self._repos.binding_repo,
                )
            except EvaluationError:
                continue

            slo_ev = await self._repos.eval_repo.create_pending(
                EvalCreateParams(
                    evaluation_id=run.id,
                    evaluation_name=request.eval_name,
                    period_start=request.period_start,
                    period_end=request.period_end,
                    ingestion_mode='pull',
                    asset_snapshot={
                        'name': ctx.asset_name,
                        'display_name': ctx.asset_display_name,
                        'tags': ctx.asset_tags,
                        'variables': ctx.asset_variables,
                    },
                    variables=request.variables,
                    asset_id=ctx.asset_id,
                    slo_name=ctx.slo_name,
                    slo_version=ctx.slo_version,
                    sli_name=ctx.sli_name,
                    sli_version=ctx.sli_version,
                    data_source_name=ctx.data_source_name,
                    adapter_used=ctx.adapter_type,
                )
            )
            slo_eval_ids.append(slo_ev.id)

        await self._repos.session.commit()

        for eid in slo_eval_ids:
            await self._pool.enqueue_job('run_evaluation_job', str(eid))

        return EvaluateSingleResponse(evaluation_id=run.id, slo_evaluation_ids=slo_eval_ids)

    async def trigger_evaluate_batch(
        self, request: EvaluateBatchRequest
    ) -> EvaluateBatchResponse:
        """Batch evaluation: by_date (one asset, many periods) or by_asset (many assets, one period)."""
        if request.mode == 'by_date':
            if not request.asset_name or not request.periods:
                raise EvaluationError('by_date mode requires asset_name and periods')
            pairs: list[tuple[str, datetime, datetime]] = [
                (request.asset_name, p.period_start, p.period_end)
                for p in request.periods
            ]
        elif request.mode == 'by_asset':
            if not request.asset_names or not request.period_start or not request.period_end:
                raise EvaluationError('by_asset mode requires asset_names, period_start, period_end')
            pairs = [
                (name, request.period_start, request.period_end)
                for name in request.asset_names
            ]
        else:
            raise EvaluationError(f"unknown batch mode '{request.mode}'")

        all_run_ids: list[uuid.UUID] = []
        all_slo_eval_ids: list[uuid.UUID] = []

        for asset_name, period_start, period_end in pairs:
            single_req = EvaluateSingleRequest(
                asset_name=asset_name,
                eval_name=request.eval_name,
                period_start=period_start,
                period_end=period_end,
                variables=request.variables,
            )
            resp = await self.trigger_evaluate(single_req)
            all_run_ids.append(resp.evaluation_id)
            all_slo_eval_ids.extend(resp.slo_evaluation_ids)

        return EvaluateBatchResponse(
            evaluation_ids=all_run_ids,
            slo_evaluation_ids=all_slo_eval_ids,
        )
