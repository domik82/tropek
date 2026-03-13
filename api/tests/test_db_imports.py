from __future__ import annotations


def test_db_session_imports() -> None:
    """Verify the db session module is importable and exposes expected names."""
    from app.db.session import get_session, get_session_factory  # noqa: F401
