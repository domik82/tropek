"""TriggerService — orchestrates single and batch evaluation triggers."""

from __future__ import annotations

import uuid
from datetime import datetime

from arq.connections import ArqRedis

from app.modules.quality_gate.shared.dependencies import QualityGateRepos
from app.modules.quality_gate.shared.exceptions import (
    AssetNotFoundError,
    EvaluationError,
)
from app.modules.quality_gate.shared.params import EvalCreateParams
from app.modules.quality_gate.schemas import (
    EvaluateBatchRequest,
    EvaluateBatchResponse,
    EvaluateSingleRequest,
    EvaluateSingleResponse,
)
from app.modules.quality_gate.workflows.trigger.trigger_resolver import (
    resolve_all_slos_for_asset,
    resolve_single_trigger,
)


class TriggerService:
    """Encapsulates trigger logic for single and batch evaluations."""

    def __init__(self, repos: QualityGateRepos, arq_pool: ArqRedis) -> None:
        self._repos = repos
        self._pool = arq_pool

    async def trigger_evaluate(self, request: EvaluateSingleRequest) -> EvaluateSingleResponse:
        """Create parent EvaluationRun + one SLOEvaluation per SLO assignment. Enqueue all."""
        asset = await self._repos.asset_repo.get_by_name(request.asset_name)
        if asset is None:
            msg = f"asset '{request.asset_name}' not found"
            raise AssetNotFoundError(msg)

        group_ids = await self._repos.asset_group_repo.list_group_ids_for_asset(asset.id)
        slo_names = await resolve_all_slos_for_asset(
            asset_id=asset.id,
            assignment_repo=self._repos.assignment_repo,
            group_ids=group_ids,
        )
        if not slo_names:
            msg = f"no slo assignments found for asset '{request.asset_name}'"
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
                    assignment_repo=self._repos.assignment_repo,
                    group_ids=group_ids,
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
                    slo_definition_id=ctx.slo_definition_id,
                    sli_name=ctx.sli_name,
                    sli_version=ctx.sli_version,
                    sli_definition_id=ctx.sli_definition_id,
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
