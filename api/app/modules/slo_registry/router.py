"""FastAPI router for SLO definition versioned CRUD."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.assets.schemas import TagKeyCount, TagValueCount
from app.modules.common.exceptions import NotFoundError
from app.modules.common.schemas import PagedResponse
from app.modules.quality_gate.engine.criteria import parse_criteria_string
from app.modules.quality_gate.engine.slo_models import SLOParseError
from app.modules.quality_gate.engine.slo_parser import build_slo
from app.modules.sli_registry.repository import SLIRepository
from app.modules.slo_registry.params import SLOCreateParams, SLOObjectiveParams
from app.modules.slo_registry.repository import SLORepository
from app.modules.slo_registry.schemas import (
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
from app.modules.slo_registry.service import SLOTestService

router = APIRouter()


@router.get('/slo-definitions', response_model=PagedResponse[SLODefinitionRead])
async def list_slo_definitions(
    tag_key: str | None = None,
    tag_val: str | None = None,
    kind: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> PagedResponse[SLODefinitionRead]:
    """List all active SLO definitions."""
    repo = SLORepository(session)
    items = await repo.list_all(tag_key=tag_key, tag_val=tag_val, kind=kind)
    return PagedResponse(items=[SLODefinitionRead.model_validate(i) for i in items], total=len(items))


@router.post('/slo-definitions', response_model=SLODefinitionRead, status_code=201)
async def create_slo_definition(
    body: SLODefinitionCreate,
    session: AsyncSession = Depends(get_session),
) -> SLODefinitionRead:
    """Create a new SLO definition (or a new version if name already exists)."""
    resolved_sli_id: uuid.UUID | None = None
    if body.sli_name is not None:
        sli_repo = SLIRepository(session)
        if body.sli_version is not None:
            sli_def = await sli_repo.get_version(body.sli_name, body.sli_version)
        else:
            sli_def = await sli_repo.get_latest(body.sli_name)
        if sli_def is None:
            raise HTTPException(
                status_code=422,
                detail=f"sli definition '{body.sli_name}' version {body.sli_version} not found",
            )
        if sli_def.mode == 'aggregated' and sli_def.methods:
            indicator_keys = {f'{body.sli_name}.{m}' for m in sli_def.methods}
        else:
            indicator_keys = set(sli_def.indicators.keys())
        for obj in body.objectives:
            if obj.sli not in indicator_keys:
                raise HTTPException(
                    status_code=422,
                    detail=f"objective sli '{obj.sli}' not found in SLI definition '{body.sli_name}' indicators",
                )
        resolved_sli_id = sli_def.id
    repo = SLORepository(session)
    params = SLOCreateParams(
        name=body.name,
        objectives=[SLOObjectiveParams(**o.model_dump()) for o in body.objectives],
        total_score_pass_threshold=body.total_score_pass_threshold,
        total_score_warning_threshold=body.total_score_warning_threshold,
        comparison=body.comparison or None,
        display_name=body.display_name,
        notes=body.notes,
        author=body.author,
        tags=body.tags,
        variables=body.variables,
        comparable_from_version=body.comparable_from_version,
        kind=body.kind,
        sli_definition_id=resolved_sli_id,
        method_criteria=body.method_criteria,
    )
    slo = await repo.create(params)
    return SLODefinitionRead.model_validate(slo)


@router.post('/slo-definitions/validate', response_model=SLOValidationResult)
async def validate_slo(body: SLOValidateRequest) -> SLOValidationResult:  # noqa: C901
    """Validate SLO structure without saving."""
    errors: list[SLOValError] = []

    if not body.objectives:
        return SLOValidationResult(
            valid=False,
            errors=[SLOValError(field='objectives', message='objectives list is empty')],
        )

    try:
        slo = build_slo(
            objectives=[o.model_dump() for o in body.objectives],
            total_score_pass_threshold=body.total_score_pass_threshold,
            total_score_warning_threshold=body.total_score_warning_threshold,
            comparison=body.comparison,
        )
    except SLOParseError as e:
        return SLOValidationResult(
            valid=False,
            errors=[SLOValError(field='objectives', message=str(e))],
        )

    # Validate all criteria strings
    for i, obj in enumerate(slo.objectives):
        for raw in obj.pass_threshold:
            try:
                parse_criteria_string(raw)
            except ValueError as e:
                errors.append(SLOValError(field=f'objectives[{i}].pass_threshold', message=str(e)))
        for raw in obj.warning_threshold:
            try:
                parse_criteria_string(raw)
            except ValueError as e:
                errors.append(SLOValError(field=f'objectives[{i}].warning_threshold', message=str(e)))

    # Validate total_score percentages
    if not (0 <= slo.total_score.pass_threshold <= 100):  # noqa: PLR2004
        errors.append(SLOValError(field='total_score_pass_threshold', message='must be 0-100'))
    if not (0 <= slo.total_score.warning_threshold <= 100):  # noqa: PLR2004
        errors.append(SLOValError(field='total_score_warning_threshold', message='must be 0-100'))

    if errors:
        return SLOValidationResult(valid=False, errors=errors)

    return SLOValidationResult(valid=True, errors=[], objectives=body.objectives)


@router.post('/slo-definitions/test', response_model=SLOTestResult)
async def test_slo(
    body: SLOTestRequest,
    session: AsyncSession = Depends(get_session),  # noqa: PT028
) -> SLOTestResult:
    """Dry-run SLO evaluation — fetch metrics, evaluate, return result without persisting."""
    service = SLOTestService(session)
    return await service.run_test(body)


@router.get('/slo-definitions/tag-keys', response_model=list[TagKeyCount])
async def get_slo_tag_keys(
    session: AsyncSession = Depends(get_session),
) -> list[TagKeyCount]:
    """Return distinct tag keys with usage counts."""
    repo = SLORepository(session)
    keys = await repo.get_tag_keys()
    return [TagKeyCount(key=k, count=v) for k, v in keys.items()]


@router.get('/slo-definitions/tag-values', response_model=list[TagValueCount])
async def get_slo_tag_values(
    key: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> list[TagValueCount]:
    """Return distinct tag values for a key with usage counts."""
    repo = SLORepository(session)
    values = await repo.get_tag_values(key)
    return [TagValueCount(value=v, count=c) for v, c in values.items()]


@router.get('/slo-definitions/{name:path}/versions', response_model=list[SLODefinitionRead])
async def list_slo_versions(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> list[SLODefinitionRead]:
    """List all versions of an SLO definition."""
    repo = SLORepository(session)
    versions = await repo.list_versions(name)
    return [SLODefinitionRead.model_validate(v) for v in versions]


@router.get('/slo-definitions/{name:path}', response_model=SLODefinitionRead)
async def get_slo_definition(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> SLODefinitionRead:
    """Get the latest active version of an SLO definition."""
    repo = SLORepository(session)
    slo = await repo.get_latest(name)
    if slo is None:
        raise NotFoundError('slo definition', name)
    return SLODefinitionRead.model_validate(slo)


@router.delete('/slo-definitions/{name:path}', status_code=204)
async def delete_slo_definition(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Deactivate all versions of an SLO definition."""
    repo = SLORepository(session)
    existing = await repo.get_latest(name)
    if existing is None:
        raise NotFoundError('slo definition', name)
    await repo.deactivate(name)
