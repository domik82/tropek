"""Derive metric polarity from SLO pass_threshold criteria.

Used by the change point detector to determine whether an increase
in metric value is a regression or improvement.
"""

from __future__ import annotations

import re


def is_higher_better(pass_threshold: list[str]) -> bool:
    """Determine if higher values are better based on the first criterion.

    Args:
        pass_threshold: List of criteria strings from the SLO objective,
            e.g. ['<600'], ['>=99.9'], ['<=+10%'].

    Returns:
        True if higher is better (throughput, availability).
        False if lower is better (latency, error rate) or cannot determine.
    """
    if not pass_threshold:
        return False

    first = pass_threshold[0].strip()
    match = re.match(r'^(<=|>=|<|>)', first)
    if not match:
        return False

    operator = match.group(1)
    return operator in ('>', '>=')
