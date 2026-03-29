"""Raw query strategy — executes complete PromQL as instant query."""

from __future__ import annotations

import logging
from typing import Any

from app.core.prometheus_client import PrometheusClient, PrometheusQueryError
from app.core.variable_substitutor import UnresolvedVariableError, substitute

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
    ) -> tuple[dict[str, float | None], dict[str, str], dict[str, Any] | None]:
        """Execute a raw PromQL query and return (values, errors, metadata)."""
        query_template = query_spec['query']

        try:
            query = substitute(query_template, variables, start_iso=start, end_iso=end)
        except UnresolvedVariableError as exc:
            logger.warning('variable substitution failed: sli=%s error=%s', sli_name, exc)
            return {sli_name: None}, {sli_name: str(exc)}, None

        logger.info('executing query: sli=%s query=%s time=%s', sli_name, query, end)

        try:
            value = await self._client.instant_query(query, time=end)
        except PrometheusQueryError as exc:
            logger.exception('query failed: sli=%s', sli_name)
            return {sli_name: None}, {sli_name: str(exc)}, None

        logger.info('query result: sli=%s value=%s', sli_name, value)
        return {sli_name: value}, {}, None
