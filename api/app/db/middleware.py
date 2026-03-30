"""ASGI middleware for per-request database session lifecycle."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class SessionMiddleware:
    """Create a DB session per HTTP request, commit before the response is sent.

    Wraps the ASGI ``send`` callable so that ``session.commit()`` runs before
    ``http.response.start`` reaches the client.  On error the session is rolled
    back instead.  The session is always closed in a ``finally`` block.

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
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        session: AsyncSession = self.factory()
        scope.setdefault('state', {})['session'] = session

        async def _commit_then_send(message: Message) -> None:
            if message['type'] == 'http.response.start':
                await session.commit()
            await send(message)

        try:
            await self.app(scope, receive, _commit_then_send)
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
