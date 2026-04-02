"""FastAPI router for SLO groups, regeneration, and extraction."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.common.errors import raise_not_found
from app.modules.common.schemas import PagedResponse
from app.modules.sli_registry.repository import SLIRepository
from app.modules.slo_groups.generator import generate_slo_specs
from app.modules.slo_groups.regeneration import plan_regeneration
from app.modules.slo_groups.repository import SLOGroupRepository
from app.modules.slo_groups.schemas import (
    ExtractRequest,
    SLOGroupCreate,
    SLOGroupRead,
    SLOGroupUpdate,
)
from app.modules.slo_registry.params import SLOCreateParams, SLOObjectiveParams
from app.modules.slo_registry.repository import SLORepository

router = APIRouter()


@dataclass
class _OldSLOState:
    """Adapter to satisfy the OldSLOState protocol for plan_regeneration."""

    name: str
    comparable_from_version: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _build_group_read(
    group_repo: SLOGroupRepository,
    group: Any,
    slo_repo: SLORepository,
) -> SLOGroupRead:
    """Build an SLOGroupRead with computed fields from FK join."""
    count = await group_repo.count_generated_slos(group.id)
    template_slo = await slo_repo.get_by_id(group.template_slo_definition_id)
    if template_slo is None:
        raise HTTPException(status_code=500, detail='template slo definition not found')
    return SLOGroupRead(
        id=group.id,
        name=group.name,
        display_name=group.display_name,
        template_slo_name=template_slo.name,
        template_slo_version=template_slo.version,
        template_slo_definition_id=group.template_slo_definition_id,
        gen_variables=group.gen_variables,
        tags=group.tags,
        author=group.author,
        version=group.version,
        active=group.active,
        created_at=group.created_at,
        updated_at=group.updated_at,
        generated_slo_count=count,
    )


async def _load_template_slo(
    slo_repo: SLORepository,
    template_slo_name: str,
    template_slo_version: int | None,
) -> Any:
    """Load and validate a template SLO, raising on not-found or wrong kind."""
    if template_slo_version is not None:
        template = await slo_repo.get_version(template_slo_name, template_slo_version)
    else:
        template = await slo_repo.get_latest(template_slo_name)
    if template is None:
        raise HTTPException(
            status_code=422,
            detail=f"template slo '{template_slo_name}' not found",
        )
    if template.kind != 'template':
        raise HTTPException(
            status_code=422,
            detail=(f"slo '{template_slo_name}' has kind '{template.kind}', expected 'template'"),
        )
    return template


async def _resolve_sli_indicators(
    session: AsyncSession,
    sli_definition_id: uuid.UUID | None,
) -> dict[str, Any]:
    """Resolve an SLI definition's indicators dict by FK, or empty dict if unlinked."""
    if sli_definition_id is None:
        return {}
    sli_repo = SLIRepository(session)
    sli_def = await sli_repo.get_by_id(sli_definition_id)
    if sli_def is None:
        return {}
    return dict(sli_def.indicators)



# ---------------------------------------------------------------------------
# SLO Group CRUD
# ---------------------------------------------------------------------------


@router.post('/slo-groups', response_model=SLOGroupRead, status_code=201)
async def create_slo_group(
    body: SLOGroupCreate,
    session: AsyncSession = Depends(get_session),
) -> SLOGroupRead:
    """Create an SLO group and generate SLO definitions from the template."""
    slo_repo = SLORepository(session)
    template = await _load_template_slo(slo_repo, body.template_slo_name, body.template_slo_version)

    # Generate specs
    try:
        gen_result = generate_slo_specs(template, body.gen_variables, body.name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Check for name collisions
    for spec in gen_result.specs:
        existing = await slo_repo.get_latest(spec.name)
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail=f"slo '{spec.name}' already exists",
            )

    # Create group row
    group_repo = SLOGroupRepository(session)
    group = await group_repo.create(
        name=body.name,
        display_name=body.display_name,
        template_slo_definition_id=template.id,
        gen_variables=body.gen_variables,
        tags=body.tags,
        author=body.author,
    )

    # Resolve SLI FK for generated SLOs from template
    resolved_sli_def_id: uuid.UUID | None = template.sli_definition_id

    # Create generated SLO definitions
    for spec in gen_result.specs:
        await slo_repo.create(
            SLOCreateParams(
                name=spec.name,
                objectives=[SLOObjectiveParams.model_validate(o) for o in spec.objectives],
                total_score_pass_threshold=spec.total_score_pass_threshold,
                total_score_warning_threshold=spec.total_score_warning_threshold,
                comparison=spec.comparison,
                variables=spec.variables,
                tags=spec.tags,
                kind='standard',
                sli_definition_id=resolved_sli_def_id,
                generated_by_group_id=group.id,
            )
        )

    return await _build_group_read(group_repo, group, slo_repo)


@router.get('/slo-groups', response_model=PagedResponse[SLOGroupRead])
async def list_slo_groups(
    tag_key: str | None = None,
    tag_val: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> PagedResponse[SLOGroupRead]:
    """List all active SLO groups with optional tag filter."""
    group_repo = SLOGroupRepository(session)
    slo_repo = SLORepository(session)
    groups = await group_repo.list_all(tag_key=tag_key, tag_val=tag_val)
    reads = [await _build_group_read(group_repo, g, slo_repo) for g in groups]
    return PagedResponse(items=reads, total=len(reads))


@router.get('/slo-groups/{name}', response_model=SLOGroupRead)
async def get_slo_group(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> SLOGroupRead:
    """Get an SLO group by name with generated SLO count."""
    group_repo = SLOGroupRepository(session)
    group = await group_repo.get_by_name(name)
    if group is None:
        raise_not_found('slo group', name)
    slo_repo = SLORepository(session)
    return await _build_group_read(group_repo, group, slo_repo)


@router.put('/slo-groups/{name}', response_model=SLOGroupRead)
async def update_slo_group(
    name: str,
    body: SLOGroupUpdate,
    session: AsyncSession = Depends(get_session),
) -> SLOGroupRead:
    """Update an SLO group and regenerate SLO definitions."""
    group_repo = SLOGroupRepository(session)
    group = await group_repo.get_by_name(name)
    if group is None:
        raise_not_found('slo group', name)

    slo_repo = SLORepository(session)

    # Load current (old) template via FK
    old_template = await slo_repo.get_by_id(group.template_slo_definition_id)
    if old_template is None:
        raise HTTPException(status_code=422, detail='current template slo definition not found')

    # Determine effective (new) template — by name/version if provided, else keep current
    if body.template_slo_name is not None:
        template = await _load_template_slo(slo_repo, body.template_slo_name, body.template_slo_version)
    else:
        template = old_template

    # Effective gen_variables
    eff_gen_vars = body.gen_variables or group.gen_variables

    # Load old generated SLOs
    old_generated_slos = await slo_repo.list_by_group_id(group.id)

    # Build OldSLOState-compatible objects
    old_states = [
        _OldSLOState(name=s.name, comparable_from_version=s.comparable_from_version) for s in old_generated_slos
    ]

    # Generate new specs
    try:
        gen_result = generate_slo_specs(template, eff_gen_vars, name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Resolve SLI indicators for old and new via FK
    old_sli_indicators = await _resolve_sli_indicators(
        session,
        old_template.sli_definition_id if not body.template_slo_name else None,
    )
    new_sli_indicators = await _resolve_sli_indicators(session, template.sli_definition_id)

    # Detect template variables change
    template_variables_changed = body.gen_variables is not None and body.gen_variables != group.gen_variables

    # Plan regeneration
    regen_plan = plan_regeneration(
        old_generated=old_states,
        new_specs=gen_result.specs,
        old_sli_indicators=old_sli_indicators,
        new_sli_indicators=new_sli_indicators,
        template_variables_changed=template_variables_changed,
    )

    # Resolve SLI FK for generated SLOs from template
    resolved_sli_def_id: uuid.UUID | None = template.sli_definition_id

    # Apply plan: create new SLOs
    for spec in regen_plan.to_create:
        await slo_repo.create(
            SLOCreateParams(
                name=spec.name,
                objectives=[SLOObjectiveParams.model_validate(o) for o in spec.objectives],
                total_score_pass_threshold=spec.total_score_pass_threshold,
                total_score_warning_threshold=spec.total_score_warning_threshold,
                comparison=spec.comparison,
                variables=spec.variables,
                tags=spec.tags,
                kind='standard',
                sli_definition_id=resolved_sli_def_id,
                generated_by_group_id=group.id,
            )
        )

    # Apply plan: update existing SLOs (create new version)
    for action in regen_plan.to_update:
        spec = action.spec
        await slo_repo.create(
            SLOCreateParams(
                name=spec.name,
                objectives=[SLOObjectiveParams.model_validate(o) for o in spec.objectives],
                total_score_pass_threshold=spec.total_score_pass_threshold,
                total_score_warning_threshold=spec.total_score_warning_threshold,
                comparison=spec.comparison,
                variables=spec.variables,
                tags=spec.tags,
                kind='standard',
                sli_definition_id=resolved_sli_def_id,
                generated_by_group_id=group.id,
                comparable_from_version=action.comparable_from_version,
            )
        )

    # Apply plan: deactivate removed SLOs
    for slo_name in regen_plan.to_deactivate:
        await slo_repo.deactivate(slo_name)

    # Update group row
    updated_group = await group_repo.update(
        name,
        template_slo_definition_id=template.id,
        gen_variables=eff_gen_vars,
        display_name=body.display_name if body.display_name is not None else group.display_name,
        tags=body.tags if body.tags is not None else None,
    )
    if updated_group is None:
        raise_not_found('slo group', name)

    return await _build_group_read(group_repo, updated_group, slo_repo)


@router.delete('/slo-groups/{name}', status_code=204)
async def delete_slo_group(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Deactivate an SLO group and its generated SLOs."""
    group_repo = SLOGroupRepository(session)
    group = await group_repo.get_by_name(name)
    if group is None:
        raise_not_found('slo group', name)

    slo_repo = SLORepository(session)
    generated_slos = await slo_repo.list_by_group_id(group.id)
    for slo in generated_slos:
        await slo_repo.deactivate(slo.name)

    await group_repo.deactivate(name)


@router.post(
    '/slo-groups/{name}/extract',
    response_model=SLOGroupRead,
    status_code=201,
)
async def extract_slo(  # noqa: C901
    name: str,
    body: ExtractRequest,
    session: AsyncSession = Depends(get_session),
) -> SLOGroupRead:
    """Extract a generated SLO from the group to a standalone definition."""
    group_repo = SLOGroupRepository(session)
    group = await group_repo.get_by_name(name)
    if group is None:
        raise_not_found('slo group', name)

    slo_repo = SLORepository(session)

    # Verify the SLO belongs to this group
    gen_slo = await slo_repo.get_latest(body.slo_name)
    if gen_slo is None:
        raise_not_found('generated slo', body.slo_name)
    if gen_slo.generated_by_group_id != group.id:
        raise HTTPException(
            status_code=422,
            detail=(f"slo '{body.slo_name}' is not generated by group '{name}'"),
        )

    # Create standalone copy
    _ = await slo_repo.create(
        SLOCreateParams(
            name=body.new_name,
            objectives=[
                SLOObjectiveParams(
                    sli=obj.sli,
                    display_name=obj.display_name,
                    weight=obj.weight,
                    key_sli=obj.key_sli,
                    pass_threshold=list(obj.pass_threshold),
                    warning_threshold=list(obj.warning_threshold),
                )
                for obj in gen_slo.objectives
            ],
            total_score_pass_threshold=gen_slo.total_score_pass_threshold,
            total_score_warning_threshold=gen_slo.total_score_warning_threshold,
            comparison=dict(gen_slo.comparison),
            variables=dict(gen_slo.variables),
            tags={k: v for k, v in gen_slo.tags.items() if k != 'slo_group'},
            kind='standard',
            sli_definition_id=gen_slo.sli_definition_id,
        )
    )

    # Re-run generator to find the row index of the extracted SLO
    template = await slo_repo.get_by_id(group.template_slo_definition_id)
    if template is None:
        raise HTTPException(status_code=422, detail='template slo definition not found')
    gen_result = generate_slo_specs(template, group.gen_variables, name)
    extracted_idx: int | None = None
    for i, spec in enumerate(gen_result.specs):
        if spec.name == body.slo_name:
            extracted_idx = i
            break

    # Remove extracted index from gen_variables
    if extracted_idx is not None:
        new_gen_vars: dict[str, list[str]] = {}
        for key, vals in group.gen_variables.items():
            new_gen_vars[key] = [v for j, v in enumerate(vals) if j != extracted_idx]
    else:
        new_gen_vars = dict(group.gen_variables)

    # Deactivate the generated SLO
    await slo_repo.deactivate(body.slo_name)

    # Update group with shrunk gen_variables
    first_vals = next(iter(new_gen_vars.values())) if new_gen_vars else []
    if new_gen_vars and first_vals:
        await group_repo.update(name, gen_variables=new_gen_vars)
    else:
        # All variables removed — deactivate group
        await group_repo.deactivate(name)

    # Reload group for response
    updated_group = await group_repo.get_by_name(name)
    if updated_group is None:
        # Group was deactivated — return minimal response from original
        template_slo = await slo_repo.get_by_id(group.template_slo_definition_id)
        if template_slo is None:
            raise HTTPException(status_code=500, detail='template slo definition not found')
        return SLOGroupRead(
            id=group.id,
            name=group.name,
            display_name=group.display_name,
            template_slo_name=template_slo.name,
            template_slo_version=template_slo.version,
            template_slo_definition_id=group.template_slo_definition_id,
            gen_variables=new_gen_vars,
            tags=group.tags,
            author=group.author,
            version=group.version,
            active=False,
            created_at=group.created_at,
            updated_at=group.updated_at,
            generated_slo_count=0,
        )
    return await _build_group_read(group_repo, updated_group, slo_repo)
