"""Bearer-token authentication for the adapter's query endpoints."""

import logging
import secrets

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


def _unauthorized() -> HTTPException:
    """Build the 401 used for every rejection, without disclosing which check failed."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='missing or invalid bearer token',
        headers={'WWW-Authenticate': 'Bearer'},
    )


def require_bearer_token(request: Request) -> None:
    """Reject a request whose ``Authorization`` header does not carry the configured token.

    The query endpoints execute caller-supplied queries against live data, so they must not answer
    anonymously once a token is configured. When ``ADAPTER_AUTH_TOKEN`` is unset the adapter stays
    permissive so that existing deployments keep working; startup logs a warning in that case.

    :param fastapi.Request request: The incoming request, carrying the configured token on
        ``app.state.auth_token``.
    :raises fastapi.HTTPException: 401 if a token is configured and the header does not match it.
    """
    expected: str | None = getattr(request.app.state, 'auth_token', None)
    if not expected:
        return

    scheme, _, presented = request.headers.get('Authorization', '').partition(' ')
    if scheme.lower() != 'bearer' or not presented:
        raise _unauthorized()
    # Constant-time comparison: a length-or-prefix-dependent check leaks the token by timing.
    if not secrets.compare_digest(presented, expected):
        logger.warning('rejected %s %s: invalid bearer token', request.method, request.url.path)
        raise _unauthorized()
