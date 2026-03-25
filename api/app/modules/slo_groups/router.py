"""FastAPI router for SLO groups, regeneration, extraction, and template bindings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.assets.repository import (
    AssetGroupRepository,
    AssetRepository,
    SLOBindingRepository,
)
from app.modules.common.errors import raise_not_found
from app.modules.common.schemas import PagedResponse
from app.modules.datasource.repository import DataSourceRepository
from app.modules.sli_registry.repository import SLIRepository
from app.modules.slo_groups.generator import generate_slo_specs
from app.modules.slo_groups.regeneration import plan_regeneration
from app.modules.slo_groups.repository import (
    SLOGroupRepository,
    TemplateBindingRepository,
)
from app.modules.slo_groups.schemas import (
    ExtractRequest,
    SLOGroupCreate,
    SLOGroupRead,
    SLOGroupUpdate,
    TemplateBindingCreate,
    TemplateBindingRead,
)
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
) -> SLOGroupRead:
    """Build an SLOGroupRead with computed generated_slo_count."""
    count = await group_repo.count_generated_slos(group.id)
    return SLOGroupRead(
        id=group.id,
        name=group.name,
        display_name=group.display_name,
        template_slo_name=group.template_slo_name,
        template_slo_version=group.template_slo_version,
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
    if template.kind != "template":
        raise HTTPException(
            status_code=422,
            detail=(f"slo '{template_slo_name}' has kind '{template.kind}', expected 'template'"),
        )
    return template


async def _resolve_sli_indicators(
    session: AsyncSession,
    sli_name: str | None,
    sli_version: int | None,
) -> dict[str, Any]:
    """Resolve an SLI definition's indicators dict, or empty dict if unlinked."""
    if sli_name is None:
        return {}
    sli_repo = SLIRepository(session)
    if sli_version is not None:
        sli_def = await sli_repo.get_version(sli_name, sli_version)
    else:
        sli_def = await sli_repo.get_latest(sli_name)
    if sli_def is None:
        return {}
    return dict(sli_def.indicators)


async def _validate_template_binding_adapter_type(
    session: AsyncSession,
    template_group_name: str,
    data_source_name: str,
) -> None:
    """Validate datasource adapter_type matches the template group's SLI adapter_type."""
    group_repo = SLOGroupRepository(session)
    group = await group_repo.get_by_name(template_group_name)
    if group is None:
        raise HTTPException(
            status_code=422,
            detail=f"slo group '{template_group_name}' not found",
        )
    slo_repo = SLORepository(session)
    template_slo = await slo_repo.get_latest(group.template_slo_name)
    if template_slo is None or not template_slo.sli_name:
        return  # can't validate without SLI link
    sli_repo = SLIRepository(session)
    sli_def = (
        await sli_repo.get_version(template_slo.sli_name, template_slo.sli_version)
        if template_slo.sli_version
        else await sli_repo.get_latest(template_slo.sli_name)
    )
    if sli_def is None:
        return
    ds_repo = DataSourceRepository(session)
    ds = await ds_repo.get_by_name(data_source_name)
    if ds is None:
        raise HTTPException(
            status_code=422,
            detail=f"datasource '{data_source_name}' not found",
        )
    if sli_def.adapter_type != ds.adapter_type:
        raise HTTPException(
            status_code=422,
            detail=(
                f"datasource adapter_type '{ds.adapter_type}' does not match "
                f"sli adapter_type '{sli_def.adapter_type}'"
            ),
        )


async def _fan_out_slo_bindings(
    session: AsyncSession,
    template_binding: Any,
) -> None:
    """Create slo_bindings for each generated SLO in the template binding's group."""
    group_repo = SLOGroupRepository(session)
    group = await group_repo.get_by_name(template_binding.template_group_name)
    if group is None:
        return
    slo_repo = SLORepository(session)
    generated_slos = await slo_repo.list_by_group_id(group.id)
    binding_repo = SLOBindingRepository(session)
    for slo in generated_slos:
        try:
            await binding_repo.create(
                target_type=template_binding.target_type,
                target_id=template_binding.target_id,
                slo_name=slo.name,
                data_source_name=template_binding.data_source_name,
                source="template",
                template_binding_id=template_binding.id,
            )
        except IntegrityError:
            await session.rollback()


async def _sync_template_bindings_for_group(
    session: AsyncSession,
    group_name: str,
    new_slo_names: set[str],
    removed_slo_names: set[str],
) -> None:
    """Sync fanned-out slo_bindings when a group's generated SLOs change."""
    tb_repo = TemplateBindingRepository(session)
    template_bindings = await tb_repo.list_by_group_name(group_name)
    binding_repo = SLOBindingRepository(session)
    for tb in template_bindings:
        # Add bindings for new SLOs
        for slo_name in new_slo_names:
            try:
                await binding_repo.create(
                    target_type=tb.target_type,
                    target_id=tb.target_id,
                    slo_name=slo_name,
                    data_source_name=tb.data_source_name,
                    source="template",
                    template_binding_id=tb.id,
                )
            except IntegrityError:
                await session.rollback()
        # Remove bindings for deactivated SLOs
        for slo_name in removed_slo_names:
            await binding_repo.delete_by_target_and_slo(tb.target_type, tb.target_id, slo_name)


# ---------------------------------------------------------------------------
# SLO Group CRUD
# ---------------------------------------------------------------------------


@router.post("/slo-groups", response_model=SLOGroupRead, status_code=201)
async def create_slo_group(
    body: SLOGroupCreate,
    session: AsyncSession = Depends(get_session),  # noqa: B008
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
        template_slo_name=body.template_slo_name,
        template_slo_version=body.template_slo_version,
        gen_variables=body.gen_variables,
        tags=body.tags,
        author=body.author,
    )

    # Create generated SLO definitions
    for spec in gen_result.specs:
        await slo_repo.create(
            spec.name,
            objectives=[dict(o) for o in spec.objectives],
            total_score_pass_pct=spec.total_score_pass_pct,
            total_score_warning_pct=spec.total_score_warning_pct,
            comparison=spec.comparison,
            variables=spec.variables,
            tags=spec.tags,
            kind="standard",
            sli_name=spec.sli_name,
            sli_version=spec.sli_version,
            generated_by_group_id=group.id,
        )

    return await _build_group_read(group_repo, group)


@router.get("/slo-groups", response_model=PagedResponse[SLOGroupRead])
async def list_slo_groups(
    tag_key: str | None = None,
    tag_val: str | None = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> PagedResponse[SLOGroupRead]:
    """List all active SLO groups with optional tag filter."""
    group_repo = SLOGroupRepository(session)
    groups = await group_repo.list_all(tag_key=tag_key, tag_val=tag_val)
    reads = [await _build_group_read(group_repo, g) for g in groups]
    return PagedResponse(items=reads, total=len(reads))


@router.get("/slo-groups/{name}", response_model=SLOGroupRead)
async def get_slo_group(
    name: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> SLOGroupRead:
    """Get an SLO group by name with generated SLO count."""
    group_repo = SLOGroupRepository(session)
    group = await group_repo.get_by_name(name)
    if group is None:
        raise_not_found("slo group", name)
    return await _build_group_read(group_repo, group)


@router.put("/slo-groups/{name}", response_model=SLOGroupRead)
async def update_slo_group(
    name: str,
    body: SLOGroupUpdate,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> SLOGroupRead:
    """Update an SLO group and regenerate SLO definitions."""
    group_repo = SLOGroupRepository(session)
    group = await group_repo.get_by_name(name)
    if group is None:
        raise_not_found("slo group", name)

    slo_repo = SLORepository(session)

    # Determine effective template
    eff_template_name = body.template_slo_name or group.template_slo_name
    eff_template_version = body.template_slo_version or group.template_slo_version
    template = await _load_template_slo(slo_repo, eff_template_name, eff_template_version)

    # Effective gen_variables
    eff_gen_vars = body.gen_variables or group.gen_variables

    # Load old generated SLOs
    old_generated_slos = await slo_repo.list_by_group_id(group.id)

    # Build OldSLOState-compatible objects
    old_states = [
        _OldSLOState(name=s.name, comparable_from_version=s.comparable_from_version)
        for s in old_generated_slos
    ]

    # Generate new specs
    try:
        gen_result = generate_slo_specs(template, eff_gen_vars, name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Resolve SLI indicators for old and new
    old_sli_indicators = await _resolve_sli_indicators(
        session,
        group.template_slo_name,
        group.template_slo_version if not body.template_slo_name else None,
    )
    new_sli_indicators = await _resolve_sli_indicators(
        session, template.sli_name, template.sli_version
    )

    # Detect template variables change
    template_variables_changed = (
        body.gen_variables is not None and body.gen_variables != group.gen_variables
    )

    # Plan regeneration
    regen_plan = plan_regeneration(
        old_generated=old_states,
        new_specs=gen_result.specs,
        old_sli_indicators=old_sli_indicators,
        new_sli_indicators=new_sli_indicators,
        template_variables_changed=template_variables_changed,
    )

    # Apply plan: create new SLOs
    for spec in regen_plan.to_create:
        await slo_repo.create(
            spec.name,
            objectives=[dict(o) for o in spec.objectives],
            total_score_pass_pct=spec.total_score_pass_pct,
            total_score_warning_pct=spec.total_score_warning_pct,
            comparison=spec.comparison,
            variables=spec.variables,
            tags=spec.tags,
            kind="standard",
            sli_name=spec.sli_name,
            sli_version=spec.sli_version,
            generated_by_group_id=group.id,
        )

    # Apply plan: update existing SLOs (create new version)
    for action in regen_plan.to_update:
        spec = action.spec
        await slo_repo.create(
            spec.name,
            objectives=[dict(o) for o in spec.objectives],
            total_score_pass_pct=spec.total_score_pass_pct,
            total_score_warning_pct=spec.total_score_warning_pct,
            comparison=spec.comparison,
            variables=spec.variables,
            tags=spec.tags,
            kind="standard",
            sli_name=spec.sli_name,
            sli_version=spec.sli_version,
            generated_by_group_id=group.id,
            comparable_from_version=action.comparable_from_version,
        )

    # Apply plan: deactivate removed SLOs
    for slo_name in regen_plan.to_deactivate:
        await slo_repo.deactivate(slo_name)

    # Sync fanned-out slo_bindings for added/removed SLOs
    new_slo_names = {s.name for s in regen_plan.to_create}
    removed_slo_names = set(regen_plan.to_deactivate)
    if new_slo_names or removed_slo_names:
        await _sync_template_bindings_for_group(session, name, new_slo_names, removed_slo_names)

    # Update group row
    updated_group = await group_repo.update(
        name,
        template_slo_name=eff_template_name,
        template_slo_version=eff_template_version,
        gen_variables=eff_gen_vars,
        display_name=body.display_name if body.display_name is not None else group.display_name,
        tags=body.tags if body.tags is not None else None,
    )
    if updated_group is None:
        raise_not_found("slo group", name)

    return await _build_group_read(group_repo, updated_group)


@router.delete("/slo-groups/{name}", status_code=204)
async def delete_slo_group(
    name: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> None:
    """Deactivate an SLO group, its generated SLOs, and template bindings."""
    group_repo = SLOGroupRepository(session)
    group = await group_repo.get_by_name(name)
    if group is None:
        raise_not_found("slo group", name)

    slo_repo = SLORepository(session)
    generated_slos = await slo_repo.list_by_group_id(group.id)
    for slo in generated_slos:
        await slo_repo.deactivate(slo.name)

    binding_repo = TemplateBindingRepository(session)
    await binding_repo.delete_all_by_group(name)

    await group_repo.deactivate(name)


@router.post(
    "/slo-groups/{name}/extract",
    response_model=SLOGroupRead,
    status_code=201,
)
async def extract_slo(  # noqa: C901
    name: str,
    body: ExtractRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> SLOGroupRead:
    """Extract a generated SLO from the group to a standalone definition."""
    group_repo = SLOGroupRepository(session)
    group = await group_repo.get_by_name(name)
    if group is None:
        raise_not_found("slo group", name)

    slo_repo = SLORepository(session)

    # Verify the SLO belongs to this group
    gen_slo = await slo_repo.get_latest(body.slo_name)
    if gen_slo is None:
        raise_not_found("generated slo", body.slo_name)
    if gen_slo.generated_by_group_id != group.id:
        raise HTTPException(
            status_code=422,
            detail=(f"slo '{body.slo_name}' is not generated by group '{name}'"),
        )

    # Create standalone copy
    objectives = [
        {
            "sli": obj.sli,
            "display_name": obj.display_name,
            "weight": obj.weight,
            "key_sli": obj.key_sli,
            "pass_criteria": obj.pass_criteria,
            "warning_criteria": obj.warning_criteria,
        }
        for obj in gen_slo.objectives
    ]
    standalone = await slo_repo.create(
        body.new_name,
        objectives=objectives,
        total_score_pass_pct=gen_slo.total_score_pass_pct,
        total_score_warning_pct=gen_slo.total_score_warning_pct,
        comparison=dict(gen_slo.comparison),
        variables=dict(gen_slo.variables),
        tags={k: v for k, v in gen_slo.tags.items() if k != "slo_group"},
        kind="standard",
        sli_name=gen_slo.sli_name,
        sli_version=gen_slo.sli_version,
    )

    # Re-run generator to find the row index of the extracted SLO
    template = await _load_template_slo(
        slo_repo, group.template_slo_name, group.template_slo_version
    )
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

    # Copy template bindings to slo_bindings for the extracted SLO
    tb_repo = TemplateBindingRepository(session)
    bindings = await tb_repo.list_by_group_name(name)
    binding_repo = SLOBindingRepository(session)
    for tb in bindings:
        await binding_repo.create(
            target_type=tb.target_type,
            target_id=tb.target_id,
            slo_name=standalone.name,
            data_source_name=tb.data_source_name,
        )

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
        return SLOGroupRead(
            id=group.id,
            name=group.name,
            display_name=group.display_name,
            template_slo_name=group.template_slo_name,
            template_slo_version=group.template_slo_version,
            gen_variables=new_gen_vars,
            tags=group.tags,
            author=group.author,
            version=group.version,
            active=False,
            created_at=group.created_at,
            updated_at=group.updated_at,
            generated_slo_count=0,
        )
    return await _build_group_read(group_repo, updated_group)


# ---------------------------------------------------------------------------
# Template Binding CRUD — assets
# ---------------------------------------------------------------------------


@router.get(
    "/assets/{name}/template-bindings",
    response_model=list[TemplateBindingRead],
)
async def list_asset_template_bindings(
    name: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[TemplateBindingRead]:
    """List all template bindings for an asset."""
    asset_repo = AssetRepository(session)
    asset = await asset_repo.get_by_name(name)
    if asset is None:
        raise_not_found("asset", name)
    tb_repo = TemplateBindingRepository(session)
    bindings = await tb_repo.list_by_target("asset", asset.id)
    return [TemplateBindingRead.model_validate(b) for b in bindings]


@router.post(
    "/assets/{name}/template-bindings",
    response_model=TemplateBindingRead,
    status_code=201,
)
async def create_asset_template_binding(
    name: str,
    body: TemplateBindingCreate,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> TemplateBindingRead:
    """Create a template binding for an asset."""
    asset_repo = AssetRepository(session)
    asset = await asset_repo.get_by_name(name)
    if asset is None:
        raise_not_found("asset", name)
    await _validate_template_binding_adapter_type(
        session, body.template_group_name, body.data_source_name
    )
    tb_repo = TemplateBindingRepository(session)
    try:
        binding = await tb_repo.create(
            target_type="asset",
            target_id=asset.id,
            template_group_name=body.template_group_name,
            data_source_name=body.data_source_name,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="template binding already exists for this target and group",
        ) from exc
    await _fan_out_slo_bindings(session, binding)
    return TemplateBindingRead.model_validate(binding)


@router.delete("/assets/{name}/template-bindings/{group_name}", status_code=204)
async def delete_asset_template_binding(
    name: str,
    group_name: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> None:
    """Delete a template binding from an asset (cascade deletes fanned-out slo_bindings)."""
    asset_repo = AssetRepository(session)
    asset = await asset_repo.get_by_name(name)
    if asset is None:
        raise_not_found("asset", name)
    tb_repo = TemplateBindingRepository(session)
    await tb_repo.delete_by_target_and_group("asset", asset.id, group_name)


# ---------------------------------------------------------------------------
# Template Binding CRUD — asset groups
# ---------------------------------------------------------------------------


@router.get(
    "/asset-groups/{name}/template-bindings",
    response_model=list[TemplateBindingRead],
)
async def list_group_template_bindings(
    name: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[TemplateBindingRead]:
    """List all template bindings for an asset group."""
    ag_repo = AssetGroupRepository(session)
    ag = await ag_repo.get_by_name(name)
    if ag is None:
        raise_not_found("asset group", name)
    tb_repo = TemplateBindingRepository(session)
    bindings = await tb_repo.list_by_target("asset_group", ag.id)
    return [TemplateBindingRead.model_validate(b) for b in bindings]


@router.post(
    "/asset-groups/{name}/template-bindings",
    response_model=TemplateBindingRead,
    status_code=201,
)
async def create_group_template_binding(
    name: str,
    body: TemplateBindingCreate,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> TemplateBindingRead:
    """Create a template binding for an asset group."""
    ag_repo = AssetGroupRepository(session)
    ag = await ag_repo.get_by_name(name)
    if ag is None:
        raise_not_found("asset group", name)
    await _validate_template_binding_adapter_type(
        session, body.template_group_name, body.data_source_name
    )
    tb_repo = TemplateBindingRepository(session)
    try:
        binding = await tb_repo.create(
            target_type="asset_group",
            target_id=ag.id,
            template_group_name=body.template_group_name,
            data_source_name=body.data_source_name,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="template binding already exists for this target and group",
        ) from exc
    await _fan_out_slo_bindings(session, binding)
    return TemplateBindingRead.model_validate(binding)


@router.delete(
    "/asset-groups/{name}/template-bindings/{group_name}",
    status_code=204,
)
async def delete_group_template_binding(
    name: str,
    group_name: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> None:
    """Delete a template binding from an asset group (cascade deletes fanned-out slo_bindings)."""
    ag_repo = AssetGroupRepository(session)
    ag = await ag_repo.get_by_name(name)
    if ag is None:
        raise_not_found("asset group", name)
    tb_repo = TemplateBindingRepository(session)
    await tb_repo.delete_by_target_and_group("asset_group", ag.id, group_name)
