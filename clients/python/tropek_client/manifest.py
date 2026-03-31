"""YAML manifest loader and desired-state reconciler."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

# Processing order — dependencies must come first
_KIND_ORDER = [
    'AssetType',
    'DataSource',
    'Asset',
    'SLI',
    'SLO',
    'AssetGroup',
    'SLOBinding',
    'SLOGroup',
    'TemplateBinding',
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


def _validate_doc_refs(  # noqa: C901, PLR0912
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
    elif doc.kind == 'SLOBinding':
        for ref_field, ref_kind in [('slo_name', 'SLO'), ('data_source_name', 'DataSource')]:
            ref_val = doc.spec.get(ref_field)
            if ref_val and ref_val not in names_by_kind.get(ref_kind, set()):
                errors.append(
                    f"WARNING: SLOBinding '{doc_name}' references {ref_kind} "
                    f"'{ref_val}' not found in manifest (may exist in API)"
                )
    elif doc.kind == 'SLOGroup':
        tpl_name = doc.spec.get('template_slo_name')
        if tpl_name and tpl_name not in names_by_kind.get('SLO', set()):
            errors.append(
                f"WARNING: SLOGroup '{doc_name}' references SLO '{tpl_name}' not found in manifest (may exist in API)"
            )
    elif doc.kind == 'TemplateBinding':
        for ref_field, ref_kind in [
            ('template_group_name', 'SLOGroup'),
            ('data_source_name', 'DataSource'),
        ]:
            ref_val = doc.spec.get(ref_field)
            if ref_val and ref_val not in names_by_kind.get(ref_kind, set()):
                errors.append(
                    f"WARNING: TemplateBinding '{doc_name}' references {ref_kind} "
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
        names_by_kind.setdefault(doc.kind, set()).add(doc.metadata['name'])

    for doc in docs:
        _validate_doc_refs(doc, names_by_kind, errors)

    return errors


def dry_run(client: Any, manifests: list[ManifestDocument]) -> ApplyPlan:
    """Compare manifests against API state and return planned actions."""
    plan = ApplyPlan()
    for doc in manifests:
        name = doc.metadata.get('name', 'unknown')
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
            elif _has_diff(doc, existing):
                reason = _diff_reason(doc, existing)
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
    """Apply manifests using desired-state reconciliation."""
    plan = dry_run(client, manifests)
    result = ApplyResult()
    blocked_kinds: set[str] = set()

    for action, doc in zip(plan.actions, manifests, strict=False):
        name = doc.metadata.get('name', 'unknown')
        if action.operation == 'SKIP':
            result.skipped += 1
            continue
        if doc.kind in blocked_kinds:
            result.failed += 1
            result.errors.append(ApplyError(kind=doc.kind, name=name, error='blocked by prior error'))
            continue
        try:
            if action.operation == 'CREATE':
                _create(client, doc)
                result.created += 1
            elif action.operation == 'UPDATE':
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
    'DataSource': {'SLOBinding', 'TemplateBinding'},
    'Asset': {'AssetGroup', 'SLOBinding', 'TemplateBinding'},
    'SLO': {'SLOBinding', 'SLOGroup'},
    'AssetGroup': {'SLOBinding', 'TemplateBinding'},
    'SLOGroup': {'TemplateBinding'},
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


def _lookup_template_binding(client: Any, doc: ManifestDocument) -> Any | None:
    """Look up an existing template binding."""
    target_type = doc.spec.get('target_type', '')
    target_name = doc.spec.get('target_name', '')
    group_name = doc.spec.get('template_group_name', '')
    if target_type == 'asset':
        bindings = client.template_bindings.list_for_asset(target_name)
    else:
        bindings = client.template_bindings.list_for_group(target_name)
    return next((b for b in bindings if b.template_group_name == group_name), None)


def _lookup_slo_binding(client: Any, doc: ManifestDocument) -> Any | None:
    """Look up an existing SLOBinding via the client."""
    target_type = doc.spec.get('target_type', '')
    target_name = doc.spec.get('target_name', '')
    if target_type == 'asset':
        bindings = client.slo_bindings.list_for_asset(target_name)
    else:
        bindings = client.slo_bindings.list_for_group(target_name)
    return next((b for b in bindings if b.slo_name == doc.spec.get('slo_name')), None)


def _lookup(client: Any, doc: ManifestDocument) -> Any | None:  # noqa: C901, PLR0911
    """Look up an existing entity by name via the client."""
    name = doc.metadata['name']
    try:
        match doc.kind:
            case 'AssetType':
                types = client.asset_types.list()
                return next((t for t in types if t.name == name), None)
            case 'Asset':
                return client.assets.get(name)
            case 'AssetGroup':
                return client.asset_groups.get(name)
            case 'DataSource':
                return client.datasources.get(name)
            case 'SLI':
                return client.sli_definitions.get(name)
            case 'SLO':
                return client.slo_definitions.get(name)
            case 'SLOBinding':
                return _lookup_slo_binding(client, doc)
            case 'SLOGroup':
                return _lookup_slo_group(client, doc)
            case 'TemplateBinding':
                return _lookup_template_binding(client, doc)
            case _:
                return None
    except Exception:  # noqa: BLE001
        return None


def _has_diff(doc: ManifestDocument, existing: Any) -> bool:  # noqa: C901, PLR0911
    """Check if the manifest differs from the existing entity."""
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
            existing_objectives = [
                {k: v for k, v in o.model_dump().items() if k != 'sort_order'}
                for o in (existing.objectives if hasattr(existing, 'objectives') else [])
            ]
            return (
                doc.spec.get('objectives') != existing_objectives
                or doc.spec.get('total_score', {}).get('pass_threshold')
                != getattr(existing, 'total_score_pass_threshold', None)
                or doc.spec.get('total_score', {}).get('warning_threshold')
                != getattr(existing, 'total_score_warning_threshold', None)
                or doc.spec.get('comparison', {}) != getattr(existing, 'comparison', {})
            )
        case 'SLOBinding':
            return doc.spec.get('data_source_name') != getattr(existing, 'data_source_name', None)
        case 'SLOGroup':
            return doc.spec.get('gen_variables') != getattr(existing, 'gen_variables', None) or doc.spec.get(
                'template_slo_version'
            ) != getattr(existing, 'template_slo_version', None)
        case 'TemplateBinding':
            return doc.spec.get('data_source_name') != getattr(existing, 'data_source_name', None)
        case _:
            return False


def _diff_reason(doc: ManifestDocument, existing: Any) -> str:
    """Generate a human-readable diff reason."""
    match doc.kind:
        case 'SLI':
            return 'indicators differ (new version will be created)'
        case 'SLO':
            return 'objectives or score differ (new version will be created)'
        case _:
            return 'fields differ'


def _create_slo_binding(client: Any, spec: dict[str, Any]) -> None:
    """Create an SLO binding for an asset or group."""
    target_type = spec['target_type']
    target_name = spec['target_name']
    if target_type == 'asset':
        client.slo_bindings.create_for_asset(target_name, spec['slo_name'], spec['data_source_name'])
    else:
        client.slo_bindings.create_for_group(target_name, spec['slo_name'], spec['data_source_name'])


def _delete_slo_binding(client: Any, spec: dict[str, Any]) -> None:
    """Delete an SLO binding for an asset or group."""
    target_type = spec['target_type']
    target_name = spec['target_name']
    if target_type == 'asset':
        client.slo_bindings.delete_for_asset(target_name, spec['slo_name'])
    else:
        client.slo_bindings.delete_for_group(target_name, spec['slo_name'])


def _create_slo_group(client: Any, name: str, spec: dict[str, Any]) -> None:
    """Create an SLO group."""
    client.slo_groups.create(
        name,
        template_slo_name=spec['template_slo_name'],
        template_slo_version=spec['template_slo_version'],
        gen_variables=spec['gen_variables'],
        display_name=spec.get('display_name'),
        tags=spec.get('tags'),
        author=spec.get('author'),
    )


def _create_template_binding(client: Any, spec: dict[str, Any]) -> None:
    """Create a template binding."""
    target_type = spec['target_type']
    target_name = spec['target_name']
    if target_type == 'asset':
        client.template_bindings.create_for_asset(target_name, spec['template_group_name'], spec['data_source_name'])
    else:
        client.template_bindings.create_for_group(target_name, spec['template_group_name'], spec['data_source_name'])


def _delete_template_binding(client: Any, spec: dict[str, Any]) -> None:
    """Delete a template binding."""
    target_type = spec['target_type']
    target_name = spec['target_name']
    if target_type == 'asset':
        client.template_bindings.delete_for_asset(target_name, spec['template_group_name'])
    else:
        client.template_bindings.delete_for_group(target_name, spec['template_group_name'])


def _create_asset_group(
    client: Any,
    name: str,
    spec: dict[str, Any],
    *,
    display_name: str | None = None,
) -> None:
    """Create an asset group with members and subgroups."""
    client.asset_groups.create(name, display_name=display_name)
    for member in spec.get('members', []):
        asset = client.assets.get(member['asset_name'])
        client.asset_groups.add_member(name, str(asset.id), weight=member.get('weight', 1.0))
    for subgroup in spec.get('subgroups', []):
        child = client.asset_groups.get(subgroup['group_name'])
        client.asset_groups.add_subgroup(name, str(child.id), weight=subgroup.get('weight', 1.0))


def _create(client: Any, doc: ManifestDocument) -> None:  # noqa: C901
    """Create a new entity via the client."""
    name = doc.metadata['name']
    match doc.kind:
        case 'AssetType':
            client.asset_types.create(name, is_default=doc.spec.get('is_default', False))
        case 'Asset':
            client.assets.create(
                name,
                type_name=doc.spec.get('type_name', 'vm'),
                display_name=doc.metadata.get('display_name'),
                tags=doc.metadata.get('tags'),
                variables=doc.metadata.get('variables'),
            )
        case 'AssetGroup':
            _create_asset_group(client, name, doc.spec, display_name=doc.metadata.get('display_name'))
        case 'DataSource':
            client.datasources.create(
                name,
                adapter_type=doc.spec['adapter_type'],
                adapter_url=doc.spec['adapter_url'],
                display_name=doc.metadata.get('display_name'),
                tags=doc.metadata.get('tags'),
            )
        case 'SLI':
            client.sli_definitions.create(
                name,
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
        case 'SLO':
            total = doc.spec.get('total_score', {})
            client.slo_definitions.create(
                name,
                objectives=doc.spec['objectives'],
                total_score_pass_threshold=total.get('pass_threshold', 90.0),
                total_score_warning_threshold=total.get('warning_threshold', 75.0),
                comparison=doc.spec.get('comparison', {}),
                display_name=doc.metadata.get('display_name'),
                notes=doc.metadata.get('notes'),
                author=doc.metadata.get('author'),
                sli_name=doc.spec.get('sli_name'),
                sli_version=doc.spec.get('sli_version'),
                kind=doc.spec.get('kind', 'standard'),
                variables=doc.spec.get('variables', {}),
                method_criteria=doc.spec.get('method_criteria'),
            )
        case 'SLOBinding':
            _create_slo_binding(client, doc.spec)
        case 'SLOGroup':
            _create_slo_group(client, name, doc.spec)
        case 'TemplateBinding':
            _create_template_binding(client, doc.spec)


def _update(client: Any, doc: ManifestDocument) -> None:  # noqa: C901
    """Update an existing entity via the client."""
    name = doc.metadata['name']
    match doc.kind:
        case 'AssetType':
            client.asset_types.set_default(name) if doc.spec.get('is_default') else None
        case 'Asset':
            client.assets.update(
                name,
                display_name=doc.metadata.get('display_name'),
                tags=doc.metadata.get('tags'),
                variables=doc.metadata.get('variables'),
            )
        case 'AssetGroup':
            # TODO: sync members/subgroups — requires add/remove member API calls
            # For v1, log that group exists but member sync is not yet implemented
            pass
        case 'DataSource':
            client.datasources.update(
                name,
                display_name=doc.metadata.get('display_name'),
                adapter_url=doc.spec.get('adapter_url'),
                tags=doc.metadata.get('tags'),
            )
        case 'SLI':
            # Creates new version
            client.sli_definitions.create(
                name,
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
        case 'SLO':
            # Creates new version
            total = doc.spec.get('total_score', {})
            client.slo_definitions.create(
                name,
                objectives=doc.spec['objectives'],
                total_score_pass_threshold=total.get('pass_threshold', 90.0),
                total_score_warning_threshold=total.get('warning_threshold', 75.0),
                comparison=doc.spec.get('comparison', {}),
                display_name=doc.metadata.get('display_name'),
                notes=doc.metadata.get('notes'),
                author=doc.metadata.get('author'),
                sli_name=doc.spec.get('sli_name'),
                sli_version=doc.spec.get('sli_version'),
                kind=doc.spec.get('kind', 'standard'),
                variables=doc.spec.get('variables', {}),
                method_criteria=doc.spec.get('method_criteria'),
            )
        case 'SLOBinding':
            # Delete + recreate
            _delete_slo_binding(client, doc.spec)
            _create_slo_binding(client, doc.spec)
        case 'SLOGroup':
            client.slo_groups.update(
                name,
                template_slo_name=doc.spec.get('template_slo_name'),
                template_slo_version=doc.spec.get('template_slo_version'),
                gen_variables=doc.spec.get('gen_variables'),
                display_name=doc.spec.get('display_name'),
                tags=doc.spec.get('tags'),
            )
        case 'TemplateBinding':
            _delete_template_binding(client, doc.spec)
            _create_template_binding(client, doc.spec)
