"""Service layer for SLO registry — test-run orchestration."""

from __future__ import annotations

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.config import get_settings
from tropek.db.models import Asset, DataSource, SLIDefinition
from tropek.modules.assets.repository import AssetRepository
from tropek.modules.common.exceptions import DomainValidationError, NotFoundError
from tropek.modules.datasource.repository import DataSourceRepository
from tropek.modules.quality_gate.evaluation_engine.criteria import aggregate_values
from tropek.modules.quality_gate.evaluation_engine.evaluator import evaluate
from tropek.modules.quality_gate.evaluation_engine.slo_models import SLO, SLOParseError
from tropek.modules.quality_gate.evaluation_engine.slo_parser import build_slo
from tropek.modules.quality_gate.evaluation_engine.variables import build_variables, substitute_variables
from tropek.modules.quality_gate.repositories.baseline import BaselineRepository
from tropek.modules.quality_gate.schemas import IndicatorResult
from tropek.modules.sli_registry.repository import SLIRepository
from tropek.modules.slo_registry.schemas import (
    BaselineConfig,
    SLOTestRequest,
    SLOTestResult,
)


class SLOTestService:
    """Orchestrates a dry-run SLO evaluation without persisting any results."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def run_test(self, body: SLOTestRequest) -> SLOTestResult:
        """Fetch metrics, evaluate against SLO, return result without persisting."""
        slo = self._parse_slo(body)
        sli_def = await self._resolve_sli(body.sli_name)
        ds = await self._resolve_datasource(body.data_source_name)
        asset = await self._resolve_asset(body.asset_name)

        variables = self._build_variables(body, asset)
        resolved_queries = self._resolve_queries(sli_def.indicators, variables)

        metrics_fetched, fetch_errors = await self._query_adapter(body, ds, resolved_queries)

        baseline_cfg = body.baseline or BaselineConfig()
        baselines, compared_values = await self._resolve_baselines(body, slo, sli_def, asset, baseline_cfg)

        eval_result = evaluate(
            slo,
            dict(metrics_fetched),
            {k: v for k, v in baselines.items() if v is not None},
        )

        indicator_results_typed = [IndicatorResult.model_validate(ir) for ir in eval_result.indicator_results]

        return SLOTestResult(
            result=eval_result.result.value,
            score=eval_result.score,
            indicator_results=indicator_results_typed,
            baseline_mode=baseline_cfg.mode,
            metrics_fetched=metrics_fetched,
            fetch_errors=fetch_errors,
            compared_values=compared_values,
        )

    def _parse_slo(self, body: SLOTestRequest) -> SLO:
        """Parse and validate SLO structure from request body."""
        try:
            return build_slo(
                objectives=[o.model_dump() for o in body.objectives],
                total_score_pass_threshold=body.total_score_pass_threshold,
                total_score_warning_threshold=body.total_score_warning_threshold,
                comparison=body.comparison.model_dump(exclude_none=True),
            )
        except SLOParseError as e:
            raise DomainValidationError(f'invalid slo: {e}') from e

    async def _resolve_sli(self, sli_name: str) -> SLIDefinition:
        """Look up the latest version of an SLI definition."""
        sli_repo = SLIRepository(self._session)
        sli_def = await sli_repo.get_latest(sli_name)
        if sli_def is None:
            raise NotFoundError('sli definition', sli_name)
        return sli_def

    async def _resolve_datasource(self, data_source_name: str) -> DataSource:
        """Look up a datasource by name."""
        ds_repo = DataSourceRepository(self._session)
        ds = await ds_repo.get_by_name(data_source_name)
        if ds is None:
            raise NotFoundError('data source', data_source_name)
        return ds

    async def _resolve_asset(self, asset_name: str) -> Asset:
        """Look up an asset by name."""
        asset_repo = AssetRepository(self._session)
        asset = await asset_repo.get_by_name(asset_name)
        if asset is None:
            raise NotFoundError('asset', asset_name)
        return asset

    def _build_variables(self, body: SLOTestRequest, asset: Asset) -> dict[str, str]:
        """Build merged variable map for query substitution."""
        variables = build_variables(
            metadata={},
            asset_name=asset.name,
            evaluation_name=body.evaluation_name,
            start=body.period_start.isoformat(),
            end=body.period_end.isoformat(),
        )
        # Asset variables (identity bindings)
        for k, v in (getattr(asset, 'variables', {}) or {}).items():
            variables.setdefault(k, str(v))
        # Asset tags as fallback variables (backward compat)
        for k, v in (getattr(asset, 'tags', {}) or {}).items():
            variables.setdefault(k, str(v))
        # Request variables (highest priority)
        for k, v in body.variables.items():
            variables[k] = str(v)
        return variables

    def _resolve_queries(self, indicators: dict[str, str], variables: dict[str, str]) -> dict[str, str]:
        """Substitute variables into each SLI query template."""
        resolved_queries: dict[str, str] = {}
        for indicator_name, query_template in indicators.items():
            try:
                resolved_queries[indicator_name] = substitute_variables(query_template, variables)
            except Exception as e:  # noqa: BLE001
                resolved_queries[indicator_name] = f'ERROR: {e}'
        return resolved_queries

    async def _query_adapter(
        self,
        body: SLOTestRequest,
        ds: DataSource,
        resolved_queries: dict[str, str],
    ) -> tuple[dict[str, float], dict[str, str]]:
        """Call the adapter to fetch metric values for the given time range."""
        metrics_fetched: dict[str, float] = {}
        fetch_errors: dict[str, str] = {}
        adapter_timeout = get_settings().reliability.adapter_timeout_seconds
        try:
            async with httpx.AsyncClient(timeout=adapter_timeout) as http_client:
                adapter_resp = await http_client.post(
                    f'{ds.adapter_url}/query',
                    json={
                        'queries': resolved_queries,
                        'start': body.period_start.isoformat(),
                        'end': body.period_end.isoformat(),
                    },
                )
                adapter_resp.raise_for_status()
                adapter_data = adapter_resp.json()
                for name, val in adapter_data.get('values', {}).items():
                    if val is not None:
                        metrics_fetched[name] = float(val)
                for name, err in adapter_data.get('errors', {}).items():
                    fetch_errors[name] = str(err)
        except httpx.ConnectError as e:
            raise HTTPException(
                status_code=502,
                detail=f'could not reach adapter at {ds.adapter_url}',
            ) from e
        except httpx.TimeoutException as e:
            raise HTTPException(
                status_code=504,
                detail=f'adapter query timed out after {adapter_timeout}s',
            ) from e
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=502,
                detail=f'adapter returned {e.response.status_code}',
            ) from e
        return metrics_fetched, fetch_errors

    async def _resolve_baselines(
        self,
        body: SLOTestRequest,
        slo: SLO,
        sli_def: SLIDefinition,
        asset: Asset,
        baseline_cfg: BaselineConfig,
    ) -> tuple[dict[str, float | None], dict[str, float] | None]:
        """Resolve comparison baselines according to the configured mode."""
        baselines: dict[str, float | None] = {}
        compared_values: dict[str, float] | None = None

        if baseline_cfg.mode == 'manual' and baseline_cfg.values:
            baselines = dict(baseline_cfg.values)
            compared_values = dict(baseline_cfg.values)
        elif baseline_cfg.mode == 'asset_history':
            baseline_repo = BaselineRepository(self._session)
            past_evals = await baseline_repo.get_evaluation_baselines(
                asset_id=asset.id,
                slo_name=body.sli_name,
                period_start_before=body.period_start,
                include_result_with_score=slo.comparison.include_result_with_score.value,
                limit=baseline_cfg.limit,
            )
            if past_evals:
                compared_values = {}
                for indicator_name in sli_def.indicators:
                    vals: list[float] = []
                    for ev in past_evals:
                        vals.extend(
                            float(row.value)
                            for row in (ev.indicator_rows or [])
                            if row.objective.sli == indicator_name and row.value is not None
                        )
                    if vals:
                        agg = aggregate_values(vals, slo.comparison.aggregate_function)
                        baselines[indicator_name] = agg
                        compared_values[indicator_name] = agg

        return baselines, compared_values
