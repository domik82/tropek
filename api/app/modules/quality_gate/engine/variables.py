"""SLO variable substitution — replaces $placeholders with evaluation metadata."""

from __future__ import annotations

import re

# Matches $variable_name tokens in SLI query strings and SLO YAML.
# Group 1 captures the name (without $) following Python identifier rules:
#   first char: letter or underscore
#   subsequent chars: letters, digits, or underscores
_VAR_RE = re.compile(
    r"""
    \$                      # literal dollar sign — variable prefix
    (                       # capture group 1: the variable name
        [a-zA-Z_]           # first character: letter or underscore (not a digit)
        [a-zA-Z0-9_]*       # subsequent characters: letters, digits, underscores
    )
    """,
    re.VERBOSE,
)


class UnresolvedVariableError(ValueError):
    """Raised when a $variable in an SLI query has no corresponding value."""


def substitute_variables(template: str, variables: dict[str, str]) -> str:
    """Replace all $variable tokens in a template string.

    Args:
        template: String containing $variable placeholders.
        variables: Mapping of variable names (without $) to their values.

    Returns:
        Template with all $variables replaced.

    Raises:
        UnresolvedVariableError: If any $variable has no corresponding key in variables.
    """

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in variables:
            raise UnresolvedVariableError(f"Unresolved variable '${name}'. Available: {sorted(variables)}")
        return variables[name]

    return _VAR_RE.sub(replace, template)


def substitute_slo_variables(slo_yaml: str, variables: dict[str, str]) -> str:
    """Substitute $variables throughout a full SLO YAML string.

    Args:
        slo_yaml: Raw SLO YAML text, possibly containing $variable tokens.
        variables: Variable name → value mapping.

    Returns:
        SLO YAML with all $variables replaced.

    Raises:
        UnresolvedVariableError: If any $variable remains unresolved.
    """
    return substitute_variables(slo_yaml, variables)


def build_variables(
    metadata: dict[str, str],
    asset_name: str | None = None,
    evaluation_name: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, str]:
    """Merge all variable sources into a single substitution dict.

    Metadata fields take the lowest priority; reserved variables derived from
    the request ($asset_name, $evaluation_name, $start, $end) are added if not already
    present in metadata.

    Args:
        metadata: Caller-provided key-value pairs from the evaluation request.
        asset_name: Primary asset name — sets $asset_name if not in metadata.
        evaluation_name: Evaluation identifier — sets $evaluation_name and $test_name alias.
        start: ISO timestamp — sets $start if not in metadata.
        end: ISO timestamp — sets $end if not in metadata.

    Returns:
        Merged variable dict ready for use with substitute_variables().
    """
    variables: dict[str, str] = dict(metadata)
    if asset_name:
        variables.setdefault('asset_name', asset_name)
    if evaluation_name:
        variables.setdefault('evaluation_name', evaluation_name)
        variables.setdefault('test_name', evaluation_name)  # backward compat alias
    if start:
        variables.setdefault('start', start)
    if end:
        variables.setdefault('end', end)
    return variables
