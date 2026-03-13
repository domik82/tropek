from __future__ import annotations


def test_db_session_imports() -> None:
    """Verify the db session module is importable and exposes expected names."""
    from app.db.session import get_session, get_session_factory  # noqa: F401


def test_orm_models_importable() -> None:
    """Verify ORM models import and register expected table names."""
    from app.db.models import (  # noqa: F401
        Asset,
        Base,
        Evaluation,
        EvaluationAnnotation,
        SLIValue,
        SLODefinition,
    )

    table_names = set(Base.metadata.tables.keys())
    assert table_names == {
        "assets",
        "slo_definitions",
        "evaluations",
        "evaluation_annotations",
        "sli_values",
    }
