"""FastAPI router for SLO groups, regeneration, and extraction."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.session import get_session
from tropek.modules.common.exceptions import ConflictError, DomainValidationError, NotFoundError
from tropek.modules.common.schemas import PagedResponse, SafeQueryStr
from tropek.modules.sli_registry.repository import SLIRepository
from tropek.modules.slo_groups.generator import generate_slo_specs
from tropek.modules.slo_groups.regeneration import RegenerationPlan, plan_regeneration
from tropek.modules.slo_groups.repository import SLOGroupRepository
from tropek.modules.slo_groups.schemas import (
    ExtractRequest,
    SLOGroupCreate,
    SLOGroupRead,
    SLOGroupUpdate,
)
from tropek.modules.slo_registry.params import SLOCreateParams, SLOObjectiveParams
from tropek.modules.slo_registry.repository import SLORepository

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
        raise DomainValidationError('template slo definition not found')
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
        raise DomainValidationError(f"template slo '{template_slo_name}' not found")
    if template.kind != 'template':
        raise DomainValidationError(f"slo '{template_slo_name}' has kind '{template.kind}', expected 'template'")
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


def _build_generated_slo_params(
    spec: Any,
    *,
    sli_definition_id: uuid.UUID | None,
    group_id: uuid.UUID,
    comparable_from_version: int | None = None,
) -> SLOCreateParams:
    """Build SLOCreateParams for an SLO generated from a template spec."""
    return SLOCreateParams(
        name=spec.name,
        objectives=[SLOObjectiveParams.model_validate(o) for o in spec.objectives],
        total_score_pass_threshold=spec.total_score_pass_threshold,
        total_score_warning_threshold=spec.total_score_warning_threshold,
        comparison=spec.comparison,
        variables=spec.variables,
        tags=spec.tags,
        kind='standard',
        sli_definition_id=sli_definition_id,
        generated_by_group_id=group_id,
        comparable_from_version=comparable_from_version,
    )


async def _apply_regeneration_plan(
    slo_repo: SLORepository,
    plan: RegenerationPlan,
    *,
    sli_definition_id: uuid.UUID | None,
    group_id: uuid.UUID,
) -> None:
    """Execute a regeneration plan: create new SLOs, version existing ones, deactivate removed."""
    for spec in plan.to_create:
        await slo_repo.create(
            _build_generated_slo_params(
                spec,
                sli_definition_id=sli_definition_id,
                group_id=group_id,
            )
        )
    for action in plan.to_update:
        await slo_repo.create(
            _build_generated_slo_params(
                action.spec,
                sli_definition_id=sli_definition_id,
                group_id=group_id,
                comparable_from_version=action.comparable_from_version,
            )
        )
    for slo_name in plan.to_deactivate:
        await slo_repo.deactivate(slo_name)


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
        raise DomainValidationError(str(exc)) from exc

    # Check for name collisions
    for spec in gen_result.specs:
        existing = await slo_repo.get_latest(spec.name)
        if existing is not None:
            raise ConflictError('slo', spec.name, 'already exists')

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

    # Create generated SLO definitions
    for spec in gen_result.specs:
        await slo_repo.create(
            _build_generated_slo_params(
                spec,
                sli_definition_id=template.sli_definition_id,
                group_id=group.id,
            )
        )

    return await _build_group_read(group_repo, group, slo_repo)


@router.get('/slo-groups', response_model=PagedResponse[SLOGroupRead])
async def list_slo_groups(
    tag_key: SafeQueryStr | None = None,
    tag_val: SafeQueryStr | None = None,
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
        raise NotFoundError('slo group', name)
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
        raise NotFoundError('slo group', name)

    slo_repo = SLORepository(session)

    # Load current (old) template via FK
    old_template = await slo_repo.get_by_id(group.template_slo_definition_id)
    if old_template is None:
        raise DomainValidationError('current template slo definition not found')

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
        raise DomainValidationError(str(exc)) from exc

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

    # Apply plan: create, re-version, and deactivate generated SLOs
    await _apply_regeneration_plan(
        slo_repo,
        regen_plan,
        sli_definition_id=template.sli_definition_id,
        group_id=group.id,
    )

    # Update group row
    updated_group = await group_repo.update(
        name,
        template_slo_definition_id=template.id,
        gen_variables=eff_gen_vars,
        display_name=body.display_name if body.display_name is not None else group.display_name,
        tags=body.tags if body.tags is not None else None,
    )
    if updated_group is None:
        raise NotFoundError('slo group', name)

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
        raise NotFoundError('slo group', name)

    slo_repo = SLORepository(session)
    generated_slos = await slo_repo.list_by_group_id(group.id)
    for slo in generated_slos:
        await slo_repo.deactivate(slo.name)

    await group_repo.deactivate(name)


def _build_standalone_slo_params(gen_slo: Any, new_name: str) -> SLOCreateParams:
    """Build SLOCreateParams for a standalone copy of a generated SLO.

    Strips the 'slo_group' tag (no longer generator-owned) and preserves
    objectives, thresholds, comparison, variables, and the SLI link.
    """
    return SLOCreateParams(
        name=new_name,
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


def _shrink_gen_variables(
    gen_variables: dict[str, list[str]],
    row_idx: int,
) -> dict[str, list[str]]:
    """Return a copy of gen_variables with row ``row_idx`` removed from each column.

    ``gen_variables`` is a column-oriented table: each key is a column name and
    each value is a list whose positions are rows. All columns have equal length,
    and each row (one value picked from every column at the same index) produces
    one generated SLO.

    Example — removing row 1 (``cache`` / ``prod``)::

        >>> _shrink_gen_variables(
        ...     {
        ...         'service': ['auth', 'cache', 'db'],
        ...         'env':     ['prod', 'prod',  'prod'],
        ...     },
        ...     row_idx=1,
        ... )
        {'service': ['auth', 'db'], 'env': ['prod', 'prod']}
    """
    return {key: vals[:row_idx] + vals[row_idx + 1 :] for key, vals in gen_variables.items()}


@router.post(
    '/slo-groups/{name}/extract',
    response_model=SLOGroupRead,
    status_code=201,
)
async def extract_slo(
    name: str,
    body: ExtractRequest,
    session: AsyncSession = Depends(get_session),
) -> SLOGroupRead:
    """Extract a generated SLO from the group to a standalone definition."""
    group_repo = SLOGroupRepository(session)
    slo_repo = SLORepository(session)

    group = await group_repo.get_by_name(name)
    if group is None:
        raise NotFoundError('slo group', name)

    gen_slo = await slo_repo.get_latest(body.slo_name)
    if gen_slo is None:
        raise NotFoundError('generated slo', body.slo_name)
    if gen_slo.generated_by_group_id != group.id:
        raise DomainValidationError(f"slo '{body.slo_name}' is not generated by group '{name}'")

    template = await slo_repo.get_by_id(group.template_slo_definition_id)
    if template is None:
        raise DomainValidationError('template slo definition not found')

    # Create the standalone copy and deactivate the original generated SLO
    await slo_repo.create(_build_standalone_slo_params(gen_slo, body.new_name))
    await slo_repo.deactivate(body.slo_name)

    # Find which gen_variables row produced this SLO and remove it
    gen_specs = generate_slo_specs(template, group.gen_variables, name).specs
    row_idx = next((i for i, s in enumerate(gen_specs) if s.name == body.slo_name), None)
    new_gen_vars = (
        _shrink_gen_variables(group.gen_variables, row_idx) if row_idx is not None else dict(group.gen_variables)
    )

    # Update the group, or deactivate it if no rows remain.
    # Both repo calls mutate `group` in place via SQLAlchemy's identity map,
    # so a single call to _build_group_read handles both outcomes.
    if new_gen_vars and all(new_gen_vars.values()):
        await group_repo.update(name, gen_variables=new_gen_vars)
    else:
        await group_repo.deactivate(name)
        group.gen_variables = new_gen_vars  # reflect shrink in the response

    return await _build_group_read(group_repo, group, slo_repo)
