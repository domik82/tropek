"""$VARIABLE placeholder replacement for PromQL templates."""

import math
import re
from datetime import datetime

_VAR_PATTERN = re.compile(r"\$([a-zA-Z_][a-zA-Z0-9_.]*)")


class UnresolvedVariableError(Exception):
    """Raised when a $VARIABLE has no matching value after substitution."""


def substitute(
    template: str,
    variables: dict[str, str],
    *,
    start_iso: str | None = None,
    end_iso: str | None = None,
    interval_override: str | None = None,
) -> str:
    """Replace $VARIABLE placeholders in a PromQL template.

    Args:
        template: PromQL string with $VARIABLE placeholders.
        variables: User-provided variable dict.
        start_iso: Evaluation start (ISO 8601). Used to auto-compute DURATION_SECONDS.
        end_iso: Evaluation end (ISO 8601). Used to auto-compute DURATION_SECONDS.
        interval_override: If set, $interval resolves to this value (not from variables).

    Returns:
        Substituted PromQL string.

    Raises:
        UnresolvedVariableError: If any $VARIABLE in the original template remains unresolved.
    """
    merged = dict(variables)

    if interval_override is not None:
        merged["interval"] = interval_override

    if "DURATION_SECONDS" not in merged and start_iso and end_iso:
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso)
        seconds = math.ceil((end - start).total_seconds())
        merged["DURATION_SECONDS"] = f"{seconds}s"

    # Collect variable names from the original template before any substitution.
    # Only these are checked for unresolved status — variables introduced by substituted
    # values (e.g. $literal appearing because a value contained '$') are not flagged.
    original_vars = set(_VAR_PATTERN.findall(template))

    unresolved = {name for name in original_vars if name not in merged}
    if unresolved:
        raise UnresolvedVariableError(
            f'unresolved variables: {", ".join("$" + v for v in sorted(unresolved))}'
        )

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in merged:
            return merged[name]
        return match.group(0)

    return _VAR_PATTERN.sub(_replace, template)
