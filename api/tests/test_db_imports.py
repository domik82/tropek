from __future__ import annotations


def test_db_session_imports() -> None:
    """Verify the db session module is importable and exposes expected names."""
    from app.db.session import get_session, get_session_factory  # noqa: F401


def test_orm_models_importable() -> None:
    """Verify ORM models import and register expected table names."""
    from app.db.models import (  # noqa: F401
        Asset,
        AssetGroup,
        AssetGroupLink,
        AssetGroupMember,
        AssetGroupSLOLink,
        AssetSLOLink,
        AssetType,
        Base,
        DataSource,
        Evaluation,
        EvaluationAnnotation,
        EvaluationBatch,
        SLIDefinition,
        SLIValue,
        SLODefinition,
        SLOObjective,
    )

    table_names = set(Base.metadata.tables.keys())
    assert table_names == {
        "assets",
        "asset_types",
        "asset_groups",
        "asset_group_members",
        "asset_group_links",
        "asset_slo_links",
        "asset_group_slo_links",
        "data_sources",
        "sli_definitions",
        "slo_definitions",
        "slo_objectives",
        "evaluations",
        "evaluation_annotations",
        "evaluation_batches",
        "sli_values",
    }
