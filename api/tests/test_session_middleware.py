"""Tests for the session commit middleware."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.db.middleware import SessionMiddleware


def _make_mock_session():
    """Build a mock AsyncSession with commit/rollback/close."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


def _make_mock_factory(session):
    """Return a callable that returns the mock session."""
    return lambda: session


async def _make_asgi_app(*, raise_error: Exception | None = None):
    """Build a trivial ASGI app that sends a complete HTTP response.

    If raise_error is set, the app raises that exception instead of responding.
    """

    async def app(scope, receive, send):
        if raise_error is not None:
            raise raise_error
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'ok'})

    return app


async def test_commit_called_before_response_headers():
    """Session is committed before http.response.start reaches the client."""
    session = _make_mock_session()
    inner_app = await _make_asgi_app()
    middleware = SessionMiddleware(inner_app, session_factory=_make_mock_factory(session))

    sent_messages: list[dict] = []

    async def mock_send(message):
        sent_messages.append(message)

    scope = {'type': 'http', 'state': {}}
    await middleware(scope, AsyncMock(), mock_send)

    session.commit.assert_awaited_once()
    session.close.assert_awaited_once()
    session.rollback.assert_not_awaited()
    assert len(sent_messages) == 2
    assert sent_messages[0]['type'] == 'http.response.start'


async def test_rollback_on_endpoint_error():
    """Session is rolled back when the inner app raises an exception."""
    session = _make_mock_session()
    inner_app = await _make_asgi_app(raise_error=ValueError('boom'))
    middleware = SessionMiddleware(inner_app, session_factory=_make_mock_factory(session))

    scope = {'type': 'http', 'state': {}}
    with pytest.raises(ValueError, match='boom'):
        await middleware(scope, AsyncMock(), AsyncMock())

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
    session.close.assert_awaited_once()


async def test_session_stored_in_scope_state():
    """Middleware stores the session in scope['state']['session']."""
    session = _make_mock_session()
    captured_scope: dict = {}

    async def capturing_app(scope, receive, send):
        captured_scope.update(scope)
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})

    middleware = SessionMiddleware(capturing_app, session_factory=_make_mock_factory(session))
    scope = {'type': 'http', 'state': {}}
    await middleware(scope, AsyncMock(), AsyncMock())

    assert captured_scope['state']['session'] is session


async def test_non_http_requests_pass_through():
    """Non-HTTP scopes (websocket, lifespan) skip session creation entirely."""
    session = _make_mock_session()
    inner_called = False

    async def inner_app(scope, receive, send):
        nonlocal inner_called
        inner_called = True

    middleware = SessionMiddleware(inner_app, session_factory=_make_mock_factory(session))
    scope = {'type': 'lifespan'}
    await middleware(scope, AsyncMock(), AsyncMock())

    assert inner_called
    session.commit.assert_not_awaited()
    session.close.assert_not_awaited()


async def test_session_closed_even_on_commit_failure():
    """Session is always closed, even if commit raises."""
    session = _make_mock_session()
    session.commit = AsyncMock(side_effect=RuntimeError('db gone'))

    async def app(scope, receive, send):
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})

    middleware = SessionMiddleware(app, session_factory=_make_mock_factory(session))
    scope = {'type': 'http', 'state': {}}

    with pytest.raises(RuntimeError, match='db gone'):
        await middleware(scope, AsyncMock(), AsyncMock())

    session.close.assert_awaited_once()
