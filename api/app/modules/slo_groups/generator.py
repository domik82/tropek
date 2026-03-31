"""Pure SLO generator — template + gen_variables → generated SLO specs.

No I/O. Fully unit-testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol


class TemplateInput(Protocol):
    """Structural protocol for the template SLO fields needed by the generator."""

    name: str
    sli_name: str | None
    sli_version: int | None
    variables: dict[str, Any]
    objectives: list[dict[str, Any]]
    total_score_pass_threshold: float
    total_score_warning_threshold: float
    comparison: dict[str, Any]
    tags: dict[str, Any]


@dataclass
class GeneratedSLOSpec:
    """One generated SLO ready to persist."""

    name: str
    sli_name: str | None
    sli_version: int | None
    variables: dict[str, Any]
    objectives: list[dict[str, Any]]
    total_score_pass_threshold: float
    total_score_warning_threshold: float
    comparison: dict[str, Any]
    tags: dict[str, Any]


@dataclass
class GeneratorResult:
    """Result of generate_slo_specs — specs plus any warnings."""

    specs: list[GeneratedSLOSpec]
    warnings: list[str] = field(default_factory=list)


_GEN_PATTERN = re.compile(r'\$__gen_(\w+)')

_OBJ_KEYS = ('sli', 'display_name', 'weight', 'key_sli', 'pass_threshold', 'warning_threshold')


def _obj_to_dict(obj: Any) -> dict[str, Any]:
    """Convert an objective (dict or ORM object) to a plain dict."""
    if isinstance(obj, dict):
        return dict(obj)
    return {k: getattr(obj, k) for k in _OBJ_KEYS if hasattr(obj, k)}


def _substitute(text: str, substitutions: dict[str, str]) -> str:
    """Replace $__gen_<key> placeholders with values from substitutions."""

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in substitutions:
            return substitutions[key]
        return match.group(0)  # leave unmatched placeholders as-is

    return _GEN_PATTERN.sub(_replace, text)


def validate_gen_variables(gen_variables: dict[str, list[str]]) -> list[str]:
    """Validate gen_variables structure. Returns list of error messages (empty = valid)."""
    errors: list[str] = []
    if not gen_variables:
        errors.append('gen_variables must have at least one key')
        return errors

    lengths = {k: len(v) for k, v in gen_variables.items()}
    unique_lengths = set(lengths.values())

    if 0 in unique_lengths:
        empty_keys = [k for k, v in gen_variables.items() if len(v) == 0]
        errors.append(f'gen_variables lists must not be empty: {empty_keys}')
        return errors

    if len(unique_lengths) > 1:
        errors.append(f'all gen_variables lists must have equal length, got: {lengths}')

    return errors


def generate_slo_specs(
    template: TemplateInput,
    gen_variables: dict[str, list[str]],
    group_name: str,
) -> GeneratorResult:
    """Generate SLO specs from a template and gen_variables.

    Each row index in gen_variables produces one SLO. All lists must be
    the same length. Substitution replaces $__gen_<key> in the template
    name and variable values (not in objectives).
    """
    errors = validate_gen_variables(gen_variables)
    if errors:
        msg = '; '.join(errors)
        raise ValueError(msg)

    warnings: list[str] = []

    # Check if template actually uses $__gen_ placeholders
    all_text = template.name + ' '.join(str(v) for v in template.variables.values())
    if not _GEN_PATTERN.search(all_text):
        warnings.append(
            f"template '{template.name}' has no $__gen_ placeholders — all generated SLOs will be identical copies"
        )

    row_count = len(next(iter(gen_variables.values())))
    specs: list[GeneratedSLOSpec] = []

    for i in range(row_count):
        subs = {key: vals[i] for key, vals in gen_variables.items()}

        # Substitute in name
        gen_name = _substitute(template.name, subs)

        # Substitute in variables values (not keys)
        gen_vars: dict[str, Any] = {}
        for var_key, var_val in template.variables.items():
            if isinstance(var_val, str):
                gen_vars[var_key] = _substitute(var_val, subs)
            else:
                gen_vars[var_key] = var_val

        # Merge tags
        gen_tags = {**template.tags, 'slo_group': group_name, 'generated': 'true'}

        specs.append(
            GeneratedSLOSpec(
                name=gen_name,
                sli_name=template.sli_name,
                sli_version=template.sli_version,
                variables=gen_vars,
                objectives=[_obj_to_dict(obj) for obj in template.objectives],
                total_score_pass_threshold=template.total_score_pass_threshold,
                total_score_warning_threshold=template.total_score_warning_threshold,
                comparison=dict(template.comparison),
                tags=gen_tags,
            )
        )

    return GeneratorResult(specs=specs, warnings=warnings)
