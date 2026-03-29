"""TriggerService — orchestrates single and batch evaluation triggers."""

from __future__ import annotations

import uuid
from typing import Any

from arq.connections import ArqRedis

from app.db.models import AssetGroupSLOLink, AssetSLOLink, EvaluationBatch
from app.modules.quality_gate.dependencies import QualityGateRepos
from app.modules.quality_gate.exceptions import (
    AssetNotFoundError,
    DuplicateEvaluationError,
    EvaluationError,
)
from app.modules.quality_gate.params import EvalCreateParams
from app.modules.quality_gate.schemas import (
    BatchConflict,
    BatchTriggerRequest,
    BatchTriggerResponse,
    TriggerRequest,
    TriggerResponse,
)
from app.modules.quality_gate.trigger import TriggerContext, resolve_single_trigger


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
            slo_link_repo=self._repos.slo_link_repo,
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
            msg = (
                'evaluation already exists for this asset/SLO/period — use re-evaluate to re-score'
            )
            raise DuplicateEvaluationError(msg)

        ev = await self._repos.eval_repo.create_pending(
            EvalCreateParams(
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

    async def trigger_batch(self, request: BatchTriggerRequest) -> BatchTriggerResponse:
        """Validate batch, detect conflicts, enqueue all-or-nothing."""
        group = await self._repos.asset_group_repo.get_by_name(request.group_name)
        if group is None:
            msg = f"asset group '{request.group_name}' not found"
            raise AssetNotFoundError(msg)

        group_links = await self._repos.group_link_repo.list_by_group(group.id)

        # Phase 1: resolve all triggers and check for duplicates
        resolved, conflicts = await self._scan_batch_members(
            members=group.members,
            request=request,
            group_links=group_links,
        )

        if conflicts:
            msg = 'batch contains duplicate evaluations'
            raise DuplicateEvaluationError(msg)

        # Phase 2: create all evaluations (single transaction)
        evaluation_ids: list[uuid.UUID] = []
        for ctx, _asset_name in resolved:
            ev = await self._repos.eval_repo.create_pending(
                EvalCreateParams(
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

        batch = EvaluationBatch(
            evaluation_ids=[str(eid) for eid in evaluation_ids],
            trigger_params={
                'group_name': request.group_name,
                'evaluation_name': request.evaluation_name,
                'period_start': request.period_start.isoformat(),
                'period_end': request.period_end.isoformat(),
            },
        )
        self._repos.session.add(batch)
        await self._repos.session.commit()

        for eid in evaluation_ids:
            await self._pool.enqueue_job('run_evaluation_job', str(eid))

        return BatchTriggerResponse(
            batch_id=batch.id,
            evaluation_ids=evaluation_ids,
            status='pending',
        )

    async def _scan_batch_members(
        self,
        members: list[Any],
        request: BatchTriggerRequest,
        group_links: list[Any],
    ) -> tuple[list[tuple[TriggerContext, str]], list[BatchConflict]]:
        """Resolve all triggers in a batch and scan for duplicates."""
        resolved: list[tuple[TriggerContext, str]] = []
        conflicts: list[BatchConflict] = []

        for member in members:
            asset = await self._repos.asset_repo.get_by_name(member.asset_name)
            if asset is None:
                continue
            asset_links = await self._repos.slo_link_repo.list_by_asset(asset.id)
            all_links: dict[str, AssetSLOLink | AssetGroupSLOLink] = {
                lnk.slo_name: lnk for lnk in asset_links
            }
            for gl in group_links:
                if gl.slo_name not in all_links:
                    all_links[gl.slo_name] = gl

            for slo_name in all_links:
                try:
                    ctx = await resolve_single_trigger(
                        asset_name=asset.name,
                        slo_name=slo_name,
                        asset_repo=self._repos.asset_repo,
                        slo_link_repo=self._repos.slo_link_repo,
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

        return resolved, conflicts
