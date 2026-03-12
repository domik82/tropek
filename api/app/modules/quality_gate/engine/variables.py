from __future__ import annotations

import re

_VAR_RE = re.compile(r"\$([a-zA-Z_][a-zA-Z0-9_]*)")


class UnresolvedVariableError(ValueError):
    pass


def substitute_variables(template: str, variables: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in variables:
            raise UnresolvedVariableError(
                f"Unresolved variable '${name}'. Available: {sorted(variables)}"
            )
        return variables[name]

    return _VAR_RE.sub(replace, template)


def substitute_slo_variables(slo_yaml: str, variables: dict[str, str]) -> str:
    """Substitute $variables throughout a full SLO YAML string."""
    return substitute_variables(slo_yaml, variables)


def build_variables(
    metadata: dict[str, str],
    asset_name: str | None = None,
    test_name: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, str]:
    """Merge all variable sources into one dict.

    Priority (later overrides earlier):
    - metadata fields from the evaluation request
    - reserved vars derived from the request ($asset_name, $test_name, $start, $end)
    """
    variables: dict[str, str] = dict(metadata)
    if asset_name:
        variables.setdefault("asset_name", asset_name)
    if test_name:
        variables.setdefault("test_name", test_name)
    if start:
        variables.setdefault("start", start)
    if end:
        variables.setdefault("end", end)
    # Convenience alias
    if "ip" in variables:
        variables.setdefault("asset_ip", variables["ip"])
    return variables
