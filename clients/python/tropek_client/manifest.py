"""YAML manifest loader and desired-state reconciler."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from tropek_client.manifest_meta import _normalize_timestamp, create_meta_snapshots
from tropek_client.models import (
    AddMemberRequest,
    AddSubgroupRequest,
    AssetCreate,
    AssetGroupCreate,
    AssetTypeCreate,
    AssetUpdate,
    ComparisonConfig,
    DataSourceCreate,
    DataSourceUpdate,
    DisplayGroupCreate,
    DisplayGroupMemberAdd,
    SLIDefinitionCreate,
    SLOAssignmentUpgrade,
    SLOAssignmentUpsert,
    SLODefinitionCreate,
    SLOGroupAssignmentUpsert,
    SLOGroupCreate,
    SLOGroupUpdate,
    SLOObjectiveIn,
)

# Processing order — dependencies must come first
_KIND_ORDER = [
    'AssetType',
    'DataSource',
    'Asset',
    'SLI',
    'SLO',
    'AssetGroup',
    'SLOGroup',
    'SLODisplayGroup',
    'SLOAssignment',
    'SLOGroupAssignment',
    'MetaSnapshot',
]


class ManifestDocument(BaseModel):
    """A single parsed manifest document."""

    api_version: str
    kind: str
    metadata: dict[str, Any]
    spec: dict[str, Any] = Field(default_factory=dict)


class PlanAction(BaseModel):
    """A single action in a reconciliation plan."""

    operation: str  # CREATE | UPDATE | SKIP
    kind: str
    name: str
    reason: str


class ApplyPlan(BaseModel):
    """Result of dry_run — list of planned actions."""

    actions: list[PlanAction] = Field(default_factory=list)


class ApplyError(BaseModel):
    """A single error during apply."""

    kind: str
    name: str
    error: str


class ApplyResult(BaseModel):
    """Result of apply — counts and errors."""

    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[ApplyError] = Field(default_factory=list)


def load_manifests(path: str) -> list[ManifestDocument]:
    """Load and topologically sort manifests from a file or directory."""
    p = Path(path)
    raw_docs: list[dict[str, Any]] = []

    if p.is_dir():
        for f in sorted(p.glob('*.yaml')):
            raw_docs.extend(_load_file(f))
        for f in sorted(p.glob('*.yml')):
            raw_docs.extend(_load_file(f))
    else:
        raw_docs.extend(_load_file(p))

    docs = [_parse_document(d) for d in raw_docs]
    return _topological_sort(docs)


def _load_file(path: Path) -> list[dict[str, Any]]:
    """Load all YAML documents from a single file."""
    text = path.read_text(encoding='utf-8')
    return [doc for doc in yaml.safe_load_all(text) if doc]


def _parse_document(raw: dict[str, Any]) -> ManifestDocument:
    """Validate and parse a raw YAML document into a ManifestDocument."""
    if 'api_version' not in raw:
        raise ValueError('manifest document missing required field: api_version')
    if 'kind' not in raw:
        raise ValueError('manifest document missing required field: kind')
    if 'metadata' not in raw:
        raise ValueError('manifest document missing required field: metadata')
    if raw['kind'] not in _KIND_ORDER:
        raise ValueError(f'unknown kind: {raw["kind"]}. valid: {_KIND_ORDER}')

    return ManifestDocument(
        api_version=raw['api_version'],
        kind=raw['kind'],
        metadata=raw['metadata'],
        spec=raw.get('spec', {}),
    )


def _topological_sort(docs: list[ManifestDocument]) -> list[ManifestDocument]:
    """Sort documents by kind dependency order, preserving file order within a kind."""

    def sort_key(doc: ManifestDocument) -> int:
        try:
            return _KIND_ORDER.index(doc.kind)
        except ValueError:
            return len(_KIND_ORDER)

    return sorted(docs, key=sort_key)


def _validate_doc_refs(  # noqa: C901
    doc: ManifestDocument, names_by_kind: dict[str, set[str]], errors: list[str]
) -> None:
    """Validate cross-references in a single manifest document (appends warnings to errors)."""
    doc_name = doc.metadata.get('name', '')
    if doc.kind == 'Asset':
        type_name = doc.spec.get('type_name')
        if type_name and type_name not in names_by_kind.get('AssetType', set()):
            errors.append(
                f"WARNING: Asset '{doc_name}' references AssetType "
                f"'{type_name}' not found in manifest (may exist in API)"
            )
    elif doc.kind == 'SLOAssignment':
        for ref_field, ref_kind in [('slo_name', 'SLO'), ('data_source_name', 'DataSource')]:
            ref_val = doc.spec.get(ref_field)
            if ref_val and ref_val not in names_by_kind.get(ref_kind, set()):
                errors.append(
                    f"WARNING: SLOAssignment '{doc_name}' references {ref_kind} "
                    f"'{ref_val}' not found in manifest (may exist in API)"
                )
    elif doc.kind == 'SLOGroup':
        tpl_name = doc.spec.get('template_slo_name')
        if tpl_name and tpl_name not in names_by_kind.get('SLO', set()):
            errors.append(
                f"WARNING: SLOGroup '{doc_name}' references SLO '{tpl_name}' not found in manifest (may exist in API)"
            )
    elif doc.kind == 'SLODisplayGroup':
        parent_name = doc.spec.get('parent_name')
        if parent_name and parent_name not in names_by_kind.get('SLODisplayGroup', set()):
            errors.append(
                f"WARNING: SLODisplayGroup '{doc_name}' references parent SLODisplayGroup "
                f"'{parent_name}' not found in manifest (may exist in API)"
            )
        errors.extend(
            f"WARNING: SLODisplayGroup '{doc_name}' references SLO '{slo_name}' not found in manifest (may exist in API)"
            for slo_name in doc.spec.get('members', [])
            if slo_name not in names_by_kind.get('SLO', set())
        )
    elif doc.kind == 'SLOGroupAssignment':
        for ref_field, ref_kind in [
            ('slo_group_name', 'SLOGroup'),
            ('data_source_name', 'DataSource'),
        ]:
            ref_val = doc.spec.get(ref_field)
            if ref_val and ref_val not in names_by_kind.get(ref_kind, set()):
                errors.append(
                    f"WARNING: SLOGroupAssignment '{doc_name}' references {ref_kind} "
                    f"'{ref_val}' not found in manifest (may exist in API)"
                )


def validate_manifests(path: str) -> list[str]:
    """Validate manifest files without making API calls. Returns list of errors."""
    errors: list[str] = []
    try:
        docs = load_manifests(path)
    except (ValueError, OSError) as e:
        errors.append(str(e))
        return errors

    # Cross-reference validation (warnings, not errors — refs may exist in API)
    names_by_kind: dict[str, set[str]] = {}
    for doc in docs:
        identifier = doc.metadata.get('name', doc.metadata.get('asset', ''))
        names_by_kind.setdefault(doc.kind, set()).add(identifier)

    for doc in docs:
        _validate_doc_refs(doc, names_by_kind, errors)

    return errors


def dry_run(client: Any, manifests: list[ManifestDocument]) -> ApplyPlan:
    """Compare manifests against API state and return planned actions."""
    plan = ApplyPlan()
    for doc in manifests:
        name = doc.metadata.get('name', doc.metadata.get('asset', 'unknown'))
        try:
            existing = _lookup(client, doc)
            if existing is None:
                plan.actions.append(
                    PlanAction(
                        operation='CREATE',
                        kind=doc.kind,
                        name=name,
                        reason='not found in current state',
                    )
                )
            elif _has_diff(client, doc, existing):
                reason = _diff_reason(client, doc, existing)
                plan.actions.append(PlanAction(operation='UPDATE', kind=doc.kind, name=name, reason=reason))
            else:
                plan.actions.append(
                    PlanAction(
                        operation='SKIP',
                        kind=doc.kind,
                        name=name,
                        reason='already exists, no changes',
                    )
                )
        except Exception as e:  # noqa: BLE001
            plan.actions.append(PlanAction(operation='CREATE', kind=doc.kind, name=name, reason=f'lookup failed: {e}'))
    return plan


def apply(client: Any, manifests: list[ManifestDocument]) -> ApplyResult:
    """Apply manifests using desired-state reconciliation.

    Each document is compared against CURRENT state at the moment it is applied, rather than against
    a plan computed once before anything changed. That distinction is the whole correctness of this
    function for dependent kinds:

    ``_KIND_DEPS`` orders SLOs before the assignments that reference them, so applying a changed SLO
    creates a new version and the assignment that points at the old one becomes stale DURING this
    run. A plan built up front cannot see that -- at plan time the SLO is still v1 and the assignment
    correctly points at v1, so the assignment is recorded SKIP, and the new version it should have
    been repointed to is created moments later. The apply then reports success while the change is
    inert, and a following `dry_run` agrees that nothing is pending, because by then both halves
    are self-consistent again at the wrong version.

    :func:`dry_run` is unchanged and remains the way to preview: it answers "what would change from
    here", which is a different and still-useful question.
    """
    result = ApplyResult()
    blocked_kinds: set[str] = set()

    for doc in manifests:
        name = doc.metadata.get('name', doc.metadata.get('asset', 'unknown'))
        if doc.kind in blocked_kinds:
            result.failed += 1
            result.errors.append(ApplyError(kind=doc.kind, name=name, error='blocked by prior error'))
            continue
        try:
            existing = _lookup(client, doc)
            if existing is not None and not _has_diff(client, doc, existing):
                result.skipped += 1
                continue
            if existing is None:
                _create(client, doc)
                result.created += 1
            else:
                _update(client, doc)
                result.updated += 1
        except Exception as e:  # noqa: BLE001
            result.failed += 1
            result.errors.append(ApplyError(kind=doc.kind, name=name, error=str(e)))
            # Block only kinds that depend on the failed kind
            for dep_kind in _dependents_of(doc.kind):
                blocked_kinds.add(dep_kind)

    return result


_KIND_DEPS: dict[str, set[str]] = {
    'AssetType': {'Asset'},
    'DataSource': {'SLOAssignment', 'SLOGroupAssignment'},
    'Asset': {'AssetGroup', 'SLOAssignment', 'SLOGroupAssignment', 'MetaSnapshot'},
    'SLO': {'SLOAssignment', 'SLOGroup', 'SLODisplayGroup'},
    'AssetGroup': {'SLOAssignment', 'SLOGroupAssignment'},
    'SLOGroup': {'SLOGroupAssignment'},
}


def _dependents_of(kind: str) -> set[str]:
    """Return the set of kinds that depend on the given kind (transitively)."""
    result: set[str] = set()
    stack = [kind]
    while stack:
        k = stack.pop()
        for dep in _KIND_DEPS.get(k, set()):
            if dep not in result:
                result.add(dep)
                stack.append(dep)
    return result


def _lookup_slo_group(client: Any, doc: ManifestDocument) -> Any | None:
    """Look up an existing SLO group by name."""
    name = doc.metadata['name']
    try:
        return client.slo_groups.get(name)
    except Exception:  # noqa: BLE001
        return None


def _lookup_slo_assignment(client: Any, doc: ManifestDocument) -> Any | None:
    """Look up an existing SLO assignment by target + slo_name."""
    target_type = doc.spec.get('target_type', '')
    target_name = doc.spec.get('target_name', '')
    slo_name = doc.spec.get('slo_name', '')
    if target_type == 'asset':
        assignments = client.slo_assignments.list_for_asset(target_name)
    else:
        assignments = client.slo_assignments.list_for_group(target_name)
    return next((a for a in assignments if a.slo_name == slo_name), None)


def _lookup_slo_group_assignment(client: Any, doc: ManifestDocument) -> Any | None:
    """Look up an existing SLO group assignment by target + slo_group_name."""
    target_type = doc.spec.get('target_type', '')
    target_name = doc.spec.get('target_name', '')
    slo_group_name = doc.spec.get('slo_group_name', '')
    if target_type == 'asset':
        assignments = client.slo_group_assignments.list_for_asset(target_name)
    else:
        assignments = client.slo_group_assignments.list_for_group(target_name)
    return next((a for a in assignments if a.slo_group_name == slo_group_name), None)


def _lookup_meta_snapshots(client: Any, doc: ManifestDocument) -> bool | None:
    """Check if all snapshots in a MetaSnapshot document already exist.

    Returns True if all exist (→ SKIP), None if any are missing (→ CREATE).
    """
    asset_name = doc.metadata.get('asset', '')
    try:
        asset = client.assets.get(asset_name)
    except Exception:  # noqa: BLE001
        return None
    asset_id = str(asset.id)
    for snapshot_entry in doc.spec.get('snapshots', []):
        source = snapshot_entry['source']
        observed_at = _normalize_timestamp(snapshot_entry['observed_at'])
        existing = client.meta.list_snapshots(asset_id, source=source, from_=observed_at, to=observed_at)
        if not existing:
            return None
    return True


def _lookup_display_group(client: Any, doc: ManifestDocument) -> Any | None:
    """Look up an existing SLO display group by name.

    Unlike `asset_groups`/`slo_groups`, the client has no `get(name)` — only `list()` — so this
    filters client-side, the same way `_lookup` already does for `AssetType` (client.asset_types.list()
    + next(...)).
    """
    name = doc.metadata['name']
    try:
        return next((group for group in client.display_groups.list() if group.name == name), None)
    except Exception:  # noqa: BLE001
        return None


def _lookup(client: Any, doc: ManifestDocument) -> Any | None:  # noqa: C901, PLR0911, PLR0912
    """Look up an existing entity by name via the client."""
    name = doc.metadata.get('name', doc.metadata.get('asset', ''))
    try:
        match doc.kind:
            case 'AssetType':
                paged_types = client.asset_types.list()
                return next((t for t in paged_types.items if t.name == name), None)
            case 'Asset':
                return client.assets.get(name)
            case 'AssetGroup':
                return client.asset_groups.get(name)
            case 'DataSource':
                return client.datasources.get(name)
            case 'SLI':
                return client.slis.get(name)
            case 'SLO':
                return client.slos.get(name)
            case 'SLOAssignment':
                return _lookup_slo_assignment(client, doc)
            case 'SLOGroup':
                return _lookup_slo_group(client, doc)
            case 'SLODisplayGroup':
                return _lookup_display_group(client, doc)
            case 'SLOGroupAssignment':
                return _lookup_slo_group_assignment(client, doc)
            case 'MetaSnapshot':
                return _lookup_meta_snapshots(client, doc)
            case _:
                return None
    except Exception:  # noqa: BLE001
        return None


# Objective fields that exist only on the read side, or cannot be compared across the
# input/read boundary at all. ``sort_order`` is API-assigned.
#
# ``change_point`` is excluded because the read side has nothing to compare against: the ORM
# attribute is named ``change_point_config`` (api/tropek/db/models.py) but the response schema field
# is ``change_point`` (api/tropek/modules/slo_registry/schemas.py), with ``from_attributes=True`` and
# nothing bridging the name mismatch -- so ``SLOObjectiveRead.change_point`` is structurally always
# ``None`` on every response, regardless of what was configured. Comparing a manifest's change_point
# block against that permanent ``None`` would make every SLO report a diff again, since
# ``library_config.yaml``'s ``slo_defaults`` sets ``change_point.enabled: true`` for every SLO. This
# is a *narrower* exclusion than ``_SLOs.new_version`` (client.py), which does have a real read value
# to work with and projects it (dropping only ``slo_objective_id``) rather than dropping the whole
# field -- see ``_normalized_objectives`` for the resulting limitation this leaves in the diff.
_OBJECTIVE_DIFF_EXCLUDED = frozenset({'sort_order', 'change_point'})

# The defaults ``_create``/``_update`` themselves send when a manifest omits the block. Comparing
# against ``None`` instead reported a diff for every manifest that simply left total_score out.
_DEFAULT_TOTAL_SCORE_PASS = 90.0
_DEFAULT_TOTAL_SCORE_WARNING = 75.0


def _normalized_objectives(objectives: Any) -> list[dict[str, Any]]:
    """Project objectives from either side of the API boundary onto one comparable shape.

    Manifest objectives are raw YAML dicts with omitted keys; API objectives are ``SLOObjectiveRead``
    models with every default filled and read-only fields added. Round-tripping both through
    ``SLOObjectiveIn`` fills the same defaults on each side, so a manifest that omits ``key_sli``
    stops reading as a change against an API response that always includes it.

    **Known limitation:** ``change_point`` is dropped entirely (see ``_OBJECTIVE_DIFF_EXCLUDED``) and
    is never compared. A manifest edit that only changes an objective's ``change_point`` config
    (``enabled``, ``window_size``, ``max_pvalue``, etc.) will not be detected as a diff and will not
    create a new SLO version -- until the read path is fixed to actually populate
    ``SLOObjectiveRead.change_point`` (currently always ``None`` due to the ``change_point_config``
    ORM attribute / ``change_point`` schema field mismatch), such a change needs a manual version
    bump. Revisit this exclusion once that's fixed.

    :param Any objectives: A list of raw dicts or of objective models, or ``None``.
    :returns: One normalized dict per objective, in the order given.
    :rtype: list[dict[str, Any]]
    """
    normalized: list[dict[str, Any]] = []
    for objective in objectives or []:
        raw = objective if isinstance(objective, dict) else objective.model_dump()
        kept = {key: value for key, value in raw.items() if key not in _OBJECTIVE_DIFF_EXCLUDED}
        normalized.append(SLOObjectiveIn.model_validate(kept).model_dump(exclude={'change_point'}))
    return normalized


def _normalized_comparison(value: Any) -> dict[str, Any]:
    """Project a comparison config from either side onto one comparable dict.

    ``existing.comparison`` is a non-optional ``ComparisonConfigRead`` model while the manifest side is
    a plain dict or absent. Pydantic returns ``NotImplemented`` when comparing a model to a dict, so
    the raw comparison was never equal -- on its own enough to make every SLO report a diff.

    :param Any value: A raw dict, a comparison model, or ``None``.
    :returns: The normalized mapping; ``{}`` becomes a defaulted config so both sides agree.
    :rtype: dict[str, Any]
    """
    if value is None:
        return ComparisonConfig().model_dump(mode='json')
    raw = value if isinstance(value, dict) else value.model_dump(mode='json')
    return ComparisonConfig.model_validate(raw).model_dump(mode='json')


def _has_diff(client: Any, doc: ManifestDocument, existing: Any) -> bool:  # noqa: C901, PLR0911
    """Check if the manifest differs from the existing entity.

    Takes ``client`` because not every comparison is answerable from the document and the existing
    row alone: an ``SLOAssignment`` pins an SLO VERSION, and deciding whether it is stale means
    asking what the latest version of that SLO now is.
    """
    match doc.kind:
        case 'AssetType':
            return doc.spec.get('is_default') != getattr(existing, 'is_default', None)
        case 'Asset':
            return (
                doc.metadata.get('display_name') != getattr(existing, 'display_name', None)
                or doc.metadata.get('tags', {}) != getattr(existing, 'tags', {})
                or doc.metadata.get('variables', {}) != getattr(existing, 'variables', {})
            )
        case 'AssetGroup':
            # Member/subgroup sync not yet implemented; skip updates
            return False
        case 'DataSource':
            return (
                doc.metadata.get('display_name') != getattr(existing, 'display_name', None)
                or doc.spec.get('adapter_url') != getattr(existing, 'adapter_url', None)
                or doc.metadata.get('tags', {}) != getattr(existing, 'tags', {})
            )
        case 'SLI':
            return (
                doc.spec.get('indicators', {}) != getattr(existing, 'indicators', {})
                or doc.spec.get('mode', 'raw') != getattr(existing, 'mode', 'raw')
                or doc.spec.get('query_template') != getattr(existing, 'query_template', None)
                or doc.spec.get('interval') != getattr(existing, 'interval', None)
                or doc.spec.get('methods') != getattr(existing, 'methods', None)
            )
        case 'SLO':
            total_score = doc.spec.get('total_score') or {}
            return (
                _normalized_objectives(doc.spec.get('objectives'))
                != _normalized_objectives(getattr(existing, 'objectives', []))
                or total_score.get('pass_threshold', _DEFAULT_TOTAL_SCORE_PASS)
                != getattr(existing, 'total_score_pass_threshold', _DEFAULT_TOTAL_SCORE_PASS)
                or total_score.get('warning_threshold', _DEFAULT_TOTAL_SCORE_WARNING)
                != getattr(existing, 'total_score_warning_threshold', _DEFAULT_TOTAL_SCORE_WARNING)
                or _normalized_comparison(doc.spec.get('comparison'))
                != _normalized_comparison(getattr(existing, 'comparison', None))
            )
        case 'SLOAssignment':
            # An assignment binds an asset to ONE SLO version, chosen when it was created. Applying a
            # changed SLO creates a NEW version (the 'SLO' branch above -> client.slos.create) and
            # leaves the assignment pinned to the old one, so the new version scores nothing.
            #
            # This returned False unconditionally, on the grounds that assignments are immutable. The
            # immutability is real, but it is a reason to REPOINT rather than a reason to report no
            # difference: an assignment on v1 when the SLO's latest is v2 genuinely differs from the
            # desired state. `_update` repoints it via the assignments upgrade endpoint.
            #
            # Observed in practice: an SLO reached v2, its assignment stayed on v1, and every
            # evaluation afterwards scored v1 while `apply` and `plan` both reported success. The
            # v2 never scored anything.
            return str(getattr(existing, 'slo_definition_id', '')) != _resolve_slo_definition_id(
                client, doc.spec.get('slo_name', '')
            )
        case 'SLOGroup':
            return doc.spec.get('gen_variables') != getattr(existing, 'gen_variables', None) or doc.spec.get(
                'template_slo_version'
            ) != getattr(existing, 'template_slo_version', None)
        case 'SLODisplayGroup':
            # Member sync not implemented yet, mirroring 'AssetGroup' above — members are set once,
            # at creation, and never reconciled on later applies.
            return False
        case 'SLOGroupAssignment':
            return False  # group assignments are immutable — delete + recreate
        case _:
            return False


def _diff_reason(client: Any, doc: ManifestDocument, existing: Any) -> str:
    """Generate a human-readable diff reason."""
    match doc.kind:
        case 'SLOAssignment':
            # Name both versions: "UPDATE SLOAssignment <name>" on its own reads as a spec change,
            # when what actually happens is a repoint that changes which version scores.
            pinned = getattr(existing, 'slo_version', None)
            return f'assignment pinned to SLO v{pinned}, latest is newer (will be repointed)'
        case 'SLI':
            return 'indicators differ (new version will be created)'
        case 'SLO':
            return 'objectives or score differ (new version will be created)'
        case _:
            return 'fields differ'


def _resolve_slo_definition_id(client: Any, slo_name: str) -> str:
    """Resolve an SLO name to its latest definition ID."""
    slo = client.slos.get(slo_name)
    return str(slo.id)


def _create_slo_assignment(client: Any, spec: dict[str, Any]) -> None:
    """Create an SLO assignment for an asset or group."""
    target_type = spec['target_type']
    target_name = spec['target_name']
    slo_definition_id = _resolve_slo_definition_id(client, spec['slo_name'])
    if target_type == 'asset':
        client.slo_assignments.create_for_asset(
            target_name, slo_definition_id, SLOAssignmentUpsert(data_source_name=spec['data_source_name'])
        )
    else:
        client.slo_assignments.create_for_group(
            target_name, slo_definition_id, SLOAssignmentUpsert(data_source_name=spec['data_source_name'])
        )


def _delete_slo_assignment(client: Any, spec: dict[str, Any], existing: Any) -> None:
    """Delete an SLO assignment for an asset or group."""
    target_type = spec['target_type']
    target_name = spec['target_name']
    if target_type == 'asset':
        client.slo_assignments.delete_for_asset(target_name, existing.id)
    else:
        client.slo_assignments.delete_for_group(target_name, existing.id)


def _create_slo_group(client: Any, name: str, spec: dict[str, Any]) -> None:
    """Create an SLO group."""
    client.slo_groups.create(
        SLOGroupCreate(
            name=name,
            template_slo_name=spec['template_slo_name'],
            template_slo_version=spec['template_slo_version'],
            gen_variables=spec['gen_variables'],
            display_name=spec.get('display_name'),
            tags=spec.get('tags'),
            author=spec.get('author'),
        )
    )


def _create_slo_group_assignment(client: Any, spec: dict[str, Any]) -> None:
    """Create an SLO group assignment."""
    target_type = spec['target_type']
    target_name = spec['target_name']
    if target_type == 'asset':
        client.slo_group_assignments.create_for_asset(
            target_name,
            spec['slo_group_name'],
            SLOGroupAssignmentUpsert(data_source_name=spec['data_source_name']),
        )
    else:
        client.slo_group_assignments.create_for_group(
            target_name,
            spec['slo_group_name'],
            SLOGroupAssignmentUpsert(data_source_name=spec['data_source_name']),
        )


def _delete_slo_group_assignment(client: Any, spec: dict[str, Any], existing: Any) -> None:
    """Delete an SLO group assignment."""
    target_type = spec['target_type']
    target_name = spec['target_name']
    if target_type == 'asset':
        client.slo_group_assignments.delete_for_asset(target_name, existing.id)
    else:
        client.slo_group_assignments.delete_for_group(target_name, existing.id)


def _create_display_group(
    client: Any,
    name: str,
    spec: dict[str, Any],
    *,
    display_name: str | None = None,
) -> None:
    """Create an SLO display group, resolving its parent by name, then adding initial members.

    The parent must already exist. `_topological_sort` only orders documents BETWEEN kinds — it
    preserves whatever order they arrived in within one kind — so nothing here orders one
    `SLODisplayGroup` document relative to another. It is the CALLER's responsibility to apply
    parents before children, in whatever order it feeds documents to `apply`/`apply_files`: build the
    document list with the parentless group(s) first, or otherwise pre-sort by `spec.parent_name`
    before calling. A caller that instead relies on this module's own dependency-order sort will find
    `SLODisplayGroup` documents applied in file/list order and this call raising for any child whose
    parent hasn't been created yet.

    Not atomic: this issues the group creation and one `add_member` call per name in
    `spec['members']` as separate requests. If a later `add_member` call fails, the group is left
    behind partially populated — and because `_has_diff` always returns `False` for `SLODisplayGroup`
    (membership is never reconciled after creation, see its docstring), no future `apply` will ever
    finish populating it. Recovery is deleting the group via the API and re-applying so it is created
    fresh with its complete member list.
    """
    parent_id = None
    parent_name = spec.get('parent_name')
    if parent_name:
        parent = next((group for group in client.display_groups.list() if group.name == parent_name), None)
        if parent is None:
            raise ValueError(f"SLODisplayGroup parent '{parent_name}' not found — apply parents before children")
        parent_id = parent.id
    client.display_groups.create(
        DisplayGroupCreate(
            name=name,
            display_name=display_name,
            parent_id=parent_id,
            sort_order=spec.get('sort_order', 0),
        )
    )
    for slo_name in spec.get('members', []):
        client.display_groups.add_member(name, DisplayGroupMemberAdd(slo_name=slo_name))


def _create_asset_group(
    client: Any,
    name: str,
    spec: dict[str, Any],
    *,
    display_name: str | None = None,
) -> None:
    """Create an asset group with members and subgroups."""
    client.asset_groups.create(AssetGroupCreate(name=name, display_name=display_name))
    for member in spec.get('members', []):
        asset = client.assets.get(member['asset_name'])
        client.asset_groups.add_member(name, AddMemberRequest(asset_id=asset.id, weight=member.get('weight', 1.0)))
    for subgroup in spec.get('subgroups', []):
        child = client.asset_groups.get(subgroup['group_name'])
        client.asset_groups.add_subgroup(
            name, AddSubgroupRequest(child_group_id=child.id, weight=subgroup.get('weight', 1.0))
        )


def _create(client: Any, doc: ManifestDocument) -> None:  # noqa: C901
    """Create a new entity via the client."""
    name = doc.metadata.get('name', doc.metadata.get('asset', ''))
    match doc.kind:
        case 'AssetType':
            client.asset_types.create(AssetTypeCreate(name=name, is_default=doc.spec.get('is_default', False)))
        case 'Asset':
            client.assets.create(
                AssetCreate(
                    name=name,
                    type_name=doc.spec.get('type_name', 'vm'),
                    display_name=doc.metadata.get('display_name'),
                    tags=doc.metadata.get('tags'),
                    variables=doc.metadata.get('variables'),
                )
            )
        case 'AssetGroup':
            _create_asset_group(client, name, doc.spec, display_name=doc.metadata.get('display_name'))
        case 'DataSource':
            client.datasources.create(
                DataSourceCreate(
                    name=name,
                    adapter_type=doc.spec['adapter_type'],
                    adapter_url=doc.spec['adapter_url'],
                    display_name=doc.metadata.get('display_name'),
                    tags=doc.metadata.get('tags'),
                )
            )
        case 'SLI':
            client.slis.create(
                SLIDefinitionCreate(
                    name=name,
                    indicators=doc.spec.get('indicators', {}),
                    adapter_type=doc.spec.get('adapter_type', 'prometheus'),
                    display_name=doc.metadata.get('display_name'),
                    notes=doc.metadata.get('notes'),
                    author=doc.metadata.get('author'),
                    mode=doc.spec.get('mode', 'raw'),
                    query_template=doc.spec.get('query_template'),
                    interval=doc.spec.get('interval'),
                    methods=doc.spec.get('methods'),
                )
            )
        case 'SLO':
            total = doc.spec.get('total_score', {})
            client.slos.create(
                SLODefinitionCreate(
                    name=name,
                    objectives=doc.spec['objectives'],
                    total_score_pass_threshold=total.get('pass_threshold', 90.0),
                    total_score_warning_threshold=total.get('warning_threshold', 75.0),
                    comparison=doc.spec.get('comparison'),
                    display_name=doc.metadata.get('display_name'),
                    notes=doc.metadata.get('notes'),
                    author=doc.metadata.get('author'),
                    sli_name=doc.spec.get('sli_name'),
                    sli_version=doc.spec.get('sli_version'),
                    kind=doc.spec.get('kind', 'standard'),
                    variables=doc.spec.get('variables'),
                    method_criteria=doc.spec.get('method_criteria'),
                )
            )
        case 'SLOAssignment':
            _create_slo_assignment(client, doc.spec)
        case 'SLOGroup':
            _create_slo_group(client, name, doc.spec)
        case 'SLODisplayGroup':
            _create_display_group(client, name, doc.spec, display_name=doc.metadata.get('display_name'))
        case 'SLOGroupAssignment':
            _create_slo_group_assignment(client, doc.spec)
        case 'MetaSnapshot':
            create_meta_snapshots(client, doc)


def _repoint_slo_assignment(client: Any, doc: ManifestDocument, name: str) -> None:
    """Repoint a stale SLO assignment at its SLO's latest version.

    The assignment row is immutable, which is what the upgrade endpoint exists for: it swaps the
    pinned definition while keeping the assignment's identity, so the history attached to it survives.

    Only reached when :func:`_has_diff` found the pinned version behind the latest, so a routine
    apply over an unchanged folder still touches nothing.

    :param Any client: Tropek client.
    :param ManifestDocument doc: The ``SLOAssignment`` document being applied.
    :param str name: The document's name, for error messages.
    :raises ValueError: If the assignment has disappeared since it was looked up.
    """
    existing = _lookup_slo_assignment(client, doc)
    if existing is None:
        raise ValueError(f'could not repoint SLO assignment for {name!r}: it no longer exists')
    latest_id = _resolve_slo_definition_id(client, doc.spec.get('slo_name', ''))
    if doc.spec.get('target_type') == 'asset':
        client.slo_assignments.upgrade(
            doc.spec['target_name'],
            str(existing.id),
            SLOAssignmentUpgrade(new_slo_definition_id=latest_id),
        )
    else:
        # No group-level upgrade endpoint exists, so a group assignment is replaced. Delete first:
        # creating a second assignment for the same SLO would leave the stale one scoring alongside
        # the new one.
        _delete_slo_assignment(client, doc.spec, existing)
        _create_slo_assignment(client, doc.spec)


def _update(client: Any, doc: ManifestDocument) -> None:
    """Update an existing entity via the client."""
    name = doc.metadata.get('name', doc.metadata.get('asset', ''))
    match doc.kind:
        case 'AssetType':
            client.asset_types.set_default(name) if doc.spec.get('is_default') else None
        case 'Asset':
            client.assets.update(
                name,
                AssetUpdate(
                    display_name=doc.metadata.get('display_name'),
                    tags=doc.metadata.get('tags'),
                    variables=doc.metadata.get('variables'),
                ),
            )
        case 'AssetGroup':
            pass
        case 'SLODisplayGroup':
            pass
        case 'DataSource':
            client.datasources.update(
                name,
                DataSourceUpdate(
                    display_name=doc.metadata.get('display_name'),
                    adapter_url=doc.spec.get('adapter_url'),
                    tags=doc.metadata.get('tags'),
                ),
            )
        case 'SLI':
            # Creates new version
            client.slis.create(
                SLIDefinitionCreate(
                    name=name,
                    indicators=doc.spec.get('indicators', {}),
                    adapter_type=doc.spec.get('adapter_type', 'prometheus'),
                    display_name=doc.metadata.get('display_name'),
                    notes=doc.metadata.get('notes'),
                    author=doc.metadata.get('author'),
                    mode=doc.spec.get('mode', 'raw'),
                    query_template=doc.spec.get('query_template'),
                    interval=doc.spec.get('interval'),
                    methods=doc.spec.get('methods'),
                )
            )
        case 'SLO':
            # Creates new version
            total = doc.spec.get('total_score', {})
            client.slos.create(
                SLODefinitionCreate(
                    name=name,
                    objectives=doc.spec['objectives'],
                    total_score_pass_threshold=total.get('pass_threshold', 90.0),
                    total_score_warning_threshold=total.get('warning_threshold', 75.0),
                    comparison=doc.spec.get('comparison'),
                    display_name=doc.metadata.get('display_name'),
                    notes=doc.metadata.get('notes'),
                    author=doc.metadata.get('author'),
                    sli_name=doc.spec.get('sli_name'),
                    sli_version=doc.spec.get('sli_version'),
                    kind=doc.spec.get('kind', 'standard'),
                    variables=doc.spec.get('variables'),
                    method_criteria=doc.spec.get('method_criteria'),
                )
            )
        case 'SLOAssignment':
            _repoint_slo_assignment(client, doc, name)
        case 'SLOGroup':
            client.slo_groups.update(
                name,
                SLOGroupUpdate(
                    template_slo_name=doc.spec.get('template_slo_name'),
                    template_slo_version=doc.spec.get('template_slo_version'),
                    gen_variables=doc.spec.get('gen_variables'),
                    display_name=doc.spec.get('display_name'),
                    tags=doc.spec.get('tags'),
                ),
            )
