"""Adapter spec keys and metric names derived from an SLI definition.

Two things must agree about the names an SLI produces:

* SLO objective validation, which *predicts* the metric names before any query runs
  (an objective's ``sli`` field must name a metric the bound SLI can produce).
* The evaluation worker's query-spec construction, which *causes* those names by
  choosing the keys of ``AdapterQueryRequest.queries``.

:func:`build_aggregated_templates` is the single place the aggregated-mode spec keys
are decided, so both sides derive them rather than restating them. Adapters key each
result ``<spec_key>.<method>`` (see ``adapters/protocol`` for the contract), which is
the suffix :func:`build_indicator_keys` adds on top.

Both functions are pure: they read an SLI definition row's columns and touch no
session, so an unsaved ``SLIDefinition`` is enough to exercise them.
"""

from __future__ import annotations

from tropek.db.models import SLIDefinition


def build_aggregated_templates(sli_def: SLIDefinition) -> dict[str, str]:
    """Return adapter spec key -> query template for an aggregated-mode SLI.

    A multi-indicator SLI produces one spec per indicator, keyed by indicator name.
    The single-``query_template`` form produces one spec keyed by the SLI name.

    :param SLIDefinition sli_def: Aggregated-mode SLI definition.
    :returns: Spec key -> query template, never empty.
    :rtype: dict[str, str]
    :raises ValueError: If the row has neither ``indicators`` nor ``query_template``
        — a state ``SLIDefinitionCreate`` rejects, so it means corrupt data rather
        than bad input.
    """
    if sli_def.indicators:
        return dict(sli_def.indicators)
    if not sli_def.query_template:
        msg = f"could not build queries for aggregated sli '{sli_def.name}': no indicators and no query_template"
        raise ValueError(msg)
    return {sli_def.name: sli_def.query_template}


def build_indicator_keys(sli_def: SLIDefinition) -> set[str]:
    """Return every metric name the SLI definition can produce.

    Raw-mode SLIs produce their indicator names verbatim. Aggregated-mode SLIs
    produce one ``<spec_key>.<method>`` name per requested statistic.

    :param SLIDefinition sli_def: SLI definition to derive names from.
    :returns: Metric names valid as an SLO objective's ``sli`` field.
    :rtype: set[str]
    :raises ValueError: If an aggregated-mode row has no ``methods`` — required by
        ``SLIDefinitionCreate`` and by both shipped adapters, so its absence would
        make the predicted names disagree with the ones an evaluation yields.
    """
    if sli_def.mode != 'aggregated':
        return set(sli_def.indicators)
    if not sli_def.methods:
        msg = f"could not derive metric names for aggregated sli '{sli_def.name}': methods is empty"
        raise ValueError(msg)
    spec_keys = build_aggregated_templates(sli_def)
    return {f'{spec_key}.{method}' for spec_key in spec_keys for method in sli_def.methods}
