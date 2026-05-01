"""ASGI middleware for per-request database session lifecycle."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_HTTP_OK_MIN = 200
_HTTP_OK_MAX = 300


class SessionMiddleware:
    """Create a DB session per HTTP request, commit before the response is sent.

    Wraps the ASGI ``send`` callable so that ``session.commit()`` runs before
    ``http.response.start`` reaches the client — but only for 2xx responses.
    On 4xx/5xx (including framework-converted exceptions like an IntegrityError
    turned into a 409), the session is rolled back so a poisoned transaction
    never leaks back into the outer context. On a raised exception the session
    is also rolled back. The session is always closed in a ``finally`` block.

    Non-HTTP scopes (WebSocket, lifespan) pass through untouched.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.app = app
        self.factory = session_factory

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Wrap the request: create session, commit/rollback before response."""
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        session: AsyncSession = self.factory()
        scope.setdefault('state', {})['session'] = session

        async def _finalise_then_send(message: Message) -> None:
            if message['type'] == 'http.response.start':
                if _HTTP_OK_MIN <= message['status'] < _HTTP_OK_MAX:
                    await session.commit()
                else:
                    await session.rollback()
            await send(message)

        try:
            await self.app(scope, receive, _finalise_then_send)
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
