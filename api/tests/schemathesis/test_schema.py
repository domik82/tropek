"""Single Schemathesis entry point — expands into hundreds of generated cases."""

from __future__ import annotations

import pytest
from schemathesis import Case, checks

from tests.schemathesis.conftest import schema

# Activate the full check set — conformance (status code, content type, schema)
# plus security-oriented checks: ``negative_data_rejection`` and
# ``positive_data_acceptance`` fuzz string params with SQLi / path-traversal /
# XSS payloads, while ``not_a_server_error`` catches unhandled 500s that reveal
# validation gaps. ``validate_response`` uses the registered set when invoked
# without an explicit ``checks=`` argument.
checks.load_all_checks()

# Endpoints excluded from fuzzing because they have production-style side effects
# that should not be triggered by property-based synthetic inputs.
#   - POST /api/evaluations: enqueues arq worker jobs
#   - POST /api/evaluations/re-evaluate: enqueues re-evaluation jobs
EXCLUDED_OPERATIONS: set[tuple[str, str]] = {
    ('POST', '/api/evaluations'),
    ('POST', '/api/evaluations/re-evaluate'),
}


@pytest.mark.schemathesis
@schema.parametrize()
def test_api_conforms_to_schema(case: Case) -> None:
    """Verify every (method, path) pair returns responses conforming to the spec."""
    if (case.method.upper(), case.path) in EXCLUDED_OPERATIONS:
        pytest.skip('excluded from fuzzing (side-effect-heavy endpoint)')

    response = case.call()
    case.validate_response(response)
