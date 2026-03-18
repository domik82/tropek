"""FastAPI router for SLO definition versioned CRUD."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.assets.repository import AssetRepository
from app.modules.common.errors import raise_not_found
from app.modules.common.schemas import PagedResponse
from app.modules.datasource.repository import DataSourceRepository
from app.modules.quality_gate.engine.criteria import aggregate_values, parse_criteria_string
from app.modules.quality_gate.engine.evaluator import evaluate
from app.modules.quality_gate.engine.slo_models import SLOParseError
from app.modules.quality_gate.engine.slo_parser import build_slo
from app.modules.quality_gate.engine.variables import build_variables, substitute_variables
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.quality_gate.schemas import IndicatorResult
from app.modules.sli_registry.repository import SLIRepository
from app.modules.slo_registry.repository import SLORepository
from app.modules.slo_registry.schemas import (
    BaselineConfig,
    SLODefinitionCreate,
    SLODefinitionRead,
    SLOTestRequest,
    SLOTestResult,
    SLOValidateRequest,
    SLOValidationResult,
)
from app.modules.slo_registry.schemas import (
    SLOValidationError as SLOValError,
)

router = APIRouter()


@router.get("/slo-definitions", response_model=PagedResponse[SLODefinitionRead])
async def list_slo_definitions(
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> PagedResponse[SLODefinitionRead]:
    """List all active SLO definitions."""
    repo = SLORepository(session)
    items = await repo.list_all()
    return PagedResponse(
        items=[SLODefinitionRead.model_validate(i) for i in items], total=len(items)
    )


@router.post("/slo-definitions", response_model=SLODefinitionRead, status_code=201)
async def create_slo_definition(
    body: SLODefinitionCreate,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> SLODefinitionRead:
    """Create a new SLO definition (or a new version if name already exists)."""
    repo = SLORepository(session)
    slo = await repo.create(
        body.name,
        objectives=[o.model_dump() for o in body.objectives],
        total_score_pass_pct=body.total_score_pass_pct,
        total_score_warning_pct=body.total_score_warning_pct,
        comparison=body.comparison,
        display_name=body.display_name,
        notes=body.notes,
        author=body.author,
        meta=body.meta,
        comparable_from_version=body.comparable_from_version,
    )
    return SLODefinitionRead.model_validate(slo)


@router.post("/slo-definitions/validate", response_model=SLOValidationResult)
async def validate_slo(body: SLOValidateRequest) -> SLOValidationResult:  # noqa: C901
    """Validate SLO structure without saving."""
    errors: list[SLOValError] = []

    if not body.objectives:
        return SLOValidationResult(
            valid=False,
            errors=[SLOValError(field="objectives", message="objectives list is empty")],
        )

    try:
        slo = build_slo(
            objectives=[o.model_dump() for o in body.objectives],
            total_score_pass_pct=body.total_score_pass_pct,
            total_score_warning_pct=body.total_score_warning_pct,
            comparison=body.comparison,
        )
    except SLOParseError as e:
        return SLOValidationResult(
            valid=False,
            errors=[SLOValError(field="objectives", message=str(e))],
        )

    # Validate all criteria strings
    for i, obj in enumerate(slo.objectives):
        for raw in obj.pass_criteria:
            try:
                parse_criteria_string(raw)
            except ValueError as e:
                errors.append(SLOValError(field=f"objectives[{i}].pass_criteria", message=str(e)))
        for raw in obj.warning_criteria:
            try:
                parse_criteria_string(raw)
            except ValueError as e:
                errors.append(
                    SLOValError(field=f"objectives[{i}].warning_criteria", message=str(e))
                )

    # Validate total_score percentages
    if not (0 <= slo.total_score.pass_pct <= 100):
        errors.append(SLOValError(field="total_score_pass_pct", message="must be 0-100"))
    if not (0 <= slo.total_score.warning_pct <= 100):
        errors.append(SLOValError(field="total_score_warning_pct", message="must be 0-100"))

    if errors:
        return SLOValidationResult(valid=False, errors=errors)

    return SLOValidationResult(valid=True, errors=[], objectives=body.objectives)


@router.post("/slo-definitions/test", response_model=SLOTestResult)
async def test_slo(  # noqa: C901
    body: SLOTestRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008, PT028
) -> SLOTestResult:
    """Dry-run SLO evaluation — fetch metrics, evaluate, return result without persisting."""
    # 1. Build SLO model from structured request
    try:
        slo = build_slo(
            objectives=[o.model_dump() for o in body.objectives],
            total_score_pass_pct=body.total_score_pass_pct,
            total_score_warning_pct=body.total_score_warning_pct,
            comparison=body.comparison,
        )
    except SLOParseError as e:
        raise HTTPException(status_code=422, detail=f"invalid slo: {e}") from e

    # 2. Resolve SLI definition
    sli_repo = SLIRepository(session)
    sli_def = await sli_repo.get_latest(body.sli_name)
    if sli_def is None:
        raise_not_found("sli definition", body.sli_name)

    # 3. Resolve data source
    ds_repo = DataSourceRepository(session)
    ds = await ds_repo.get_by_name(body.data_source_name)
    if ds is None:
        raise_not_found("data source", body.data_source_name)

    # 4. Resolve asset
    asset_repo = AssetRepository(session)
    asset = await asset_repo.get_by_name(body.asset_name)
    if asset is None:
        raise_not_found("asset", body.asset_name)

    # 5. Build variables and substitute in SLI queries
    asset_labels: dict[str, str] = {
        str(k): str(v) for k, v in (getattr(asset, "labels", {}) or {}).items()
    }
    variables = build_variables(
        metadata={**asset_labels, **body.metadata},
        asset_name=asset.name,
        start=body.period_start.isoformat(),
        end=body.period_end.isoformat(),
    )

    resolved_queries: dict[str, str] = {}
    for indicator_name, query_template in sli_def.indicators.items():
        try:
            resolved_queries[indicator_name] = substitute_variables(query_template, variables)
        except Exception as e:
            resolved_queries[indicator_name] = f"ERROR: {e}"

    # 6. Query adapter
    metrics_fetched: dict[str, float] = {}
    fetch_errors: dict[str, str] = {}

    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            adapter_resp = await http_client.post(
                f"{ds.adapter_url}/query",
                json={
                    "queries": resolved_queries,
                    "start": body.period_start.isoformat(),
                    "end": body.period_end.isoformat(),
                },
            )
            adapter_resp.raise_for_status()
            adapter_data = adapter_resp.json()
            for name, val in adapter_data.get("values", {}).items():
                if val is not None:
                    metrics_fetched[name] = float(val)
            for name, err in adapter_data.get("errors", {}).items():
                fetch_errors[name] = str(err)
    except httpx.ConnectError as e:
        raise HTTPException(
            status_code=502,
            detail=f"could not reach adapter at {ds.adapter_url}",
        ) from e
    except httpx.TimeoutException as e:
        raise HTTPException(
            status_code=504,
            detail="adapter query timed out after 30s",
        ) from e
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"adapter returned {e.response.status_code}",
        ) from e

    # 7. Resolve baselines
    baseline_cfg = body.baseline or BaselineConfig()
    baselines: dict[str, float | None] = {}
    compared_values: dict[str, float] | None = None

    if baseline_cfg.mode == "manual" and baseline_cfg.values:
        baselines = {k: v for k, v in baseline_cfg.values.items()}
        compared_values = dict(baseline_cfg.values)
    elif baseline_cfg.mode == "asset_history":
        eval_repo = EvaluationRepository(session)
        past_evals = await eval_repo.get_baselines(
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
                        float(ind["value"])
                        for ind in ev.indicator_results or []
                        if ind.get("metric") == indicator_name and ind.get("value") is not None
                    )
                if vals:
                    agg = aggregate_values(vals, slo.comparison.aggregate_function)
                    baselines[indicator_name] = agg
                    compared_values[indicator_name] = agg

    # 8. Evaluate
    eval_result = evaluate(
        slo,
        {k: v for k, v in metrics_fetched.items()},
        {k: v for k, v in baselines.items() if v is not None},
    )

    indicator_results_typed = [
        IndicatorResult.model_validate(ir) for ir in eval_result.indicator_results
    ]

    return SLOTestResult(
        result=eval_result.result.value,
        score=eval_result.score,
        indicator_results=indicator_results_typed,
        baseline_mode=baseline_cfg.mode,
        metrics_fetched=metrics_fetched,
        fetch_errors=fetch_errors,
        compared_values=compared_values,
    )


@router.get("/slo-definitions/{name}", response_model=SLODefinitionRead)
async def get_slo_definition(
    name: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> SLODefinitionRead:
    """Get the latest active version of an SLO definition."""
    repo = SLORepository(session)
    slo = await repo.get_latest(name)
    if slo is None:
        raise_not_found("slo definition", name)
    return SLODefinitionRead.model_validate(slo)


@router.get("/slo-definitions/{name}/versions", response_model=list[SLODefinitionRead])
async def list_slo_versions(
    name: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[SLODefinitionRead]:
    """List all versions of an SLO definition."""
    repo = SLORepository(session)
    versions = await repo.list_versions(name)
    return [SLODefinitionRead.model_validate(v) for v in versions]


@router.delete("/slo-definitions/{name}", status_code=204)
async def delete_slo_definition(
    name: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> None:
    """Deactivate all versions of an SLO definition."""
    repo = SLORepository(session)
    existing = await repo.get_latest(name)
    if existing is None:
        raise_not_found("slo definition", name)
    await repo.deactivate(name)
