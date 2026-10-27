"""Raw query strategy — executes complete PromQL as instant query."""

from __future__ import annotations

import logging
from typing import Any

from tropek_prometheus.core.prometheus_client import PrometheusClient, PrometheusQueryError
from tropek_prometheus.core.strategies.models import ErrorKind, IndicatorOutcome, StrategyResult
from tropek_prometheus.core.variable_substitutor import UnresolvedVariableError, substitute

logger = logging.getLogger(__name__)


class RawQueryStrategy:
    """Executes a complete PromQL expression as an instant query at end timestamp."""

    def __init__(self, client: PrometheusClient) -> None:
        self._client = client

    async def execute(
        self,
        *,
        sli_name: str,
        query_spec: dict[str, Any],
        variables: dict[str, str],
        start: str,
        end: str,
    ) -> StrategyResult:
        """Execute a raw PromQL query and return its single indicator outcome."""
        query_template = query_spec['query']

        try:
            query = substitute(query_template, variables, start_iso=start, end_iso=end)
        except UnresolvedVariableError as substitution_error:
            logger.warning('variable substitution failed: sli=%s error=%s', sli_name, substitution_error)
            return StrategyResult(
                indicators={sli_name: IndicatorOutcome(value=None, error=str(substitution_error), error_kind='data')}
            )

        logger.info('executing query: sli=%s query=%s time=%s', sli_name, query, end)

        try:
            value = await self._client.instant_query(query, time=end)
        except PrometheusQueryError as query_error:
            logger.warning(
                'query returned no data: sli=%s error=%s query=%s time=%s', sli_name, query_error, query, end
            )
            kind: ErrorKind = 'transient' if query_error.transient else 'data'
            return StrategyResult(
                indicators={sli_name: IndicatorOutcome(value=None, error=str(query_error), error_kind=kind)}
            )

        logger.info('query result: sli=%s value=%s', sli_name, value)
        return StrategyResult(indicators={sli_name: IndicatorOutcome(value=value)})
