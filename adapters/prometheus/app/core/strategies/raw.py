"""Raw query strategy — executes complete PromQL as instant query."""

from app.core.prometheus_client import PrometheusClient, PrometheusQueryError
from app.core.variable_substitutor import UnresolvedVariableError, substitute


class RawQueryStrategy:
    """Executes a complete PromQL expression as an instant query at end timestamp."""

    def __init__(self, client: PrometheusClient) -> None:
        self._client = client

    async def execute(
        self,
        *,
        sli_name: str,
        query_spec: dict,
        variables: dict[str, str],
        start: str,
        end: str,
    ) -> tuple[dict[str, float | None], dict[str, str], dict | None]:
        """Execute a raw PromQL query and return (values, errors, metadata)."""
        query_template = query_spec["query"]

        try:
            query = substitute(query_template, variables, start_iso=start, end_iso=end)
        except UnresolvedVariableError as exc:
            return {sli_name: None}, {sli_name: str(exc)}, None

        try:
            value = await self._client.instant_query(query, time=end)
        except PrometheusQueryError as exc:
            return {sli_name: None}, {sli_name: str(exc)}, None

        return {sli_name: value}, {}, None
