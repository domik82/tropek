from __future__ import annotations

from tropek.db import models
from tropek.db.models import (
    Asset,  # noqa: F401
    AssetGroup,  # noqa: F401
    AssetGroupLink,
    AssetGroupMember,
    AssetMetaClosure,  # noqa: F401
    AssetMetaSnapshot,  # noqa: F401
    AssetMetaValue,  # noqa: F401
    AssetType,  # noqa: F401
    Base,
    DataSource,  # noqa: F401
    EvaluationAnnotation,
    EvaluationRun,
    IndicatorResultRow,
    SLIDefinition,  # noqa: F401
    SLIValue,
    SLODefinition,  # noqa: F401
    SLOEvaluation,
    SLOGroup,  # noqa: F401
    SLOObjective,  # noqa: F401
)
from tropek.db.session import get_session, get_session_factory


def test_db_session_imports() -> None:
    """Verify the db session module is importable and exposes expected names."""
    assert callable(get_session)
    assert callable(get_session_factory)


def test_orm_models_importable() -> None:
    """Verify ORM models import and register expected table names."""
    table_names = set(Base.metadata.tables.keys())
    assert table_names == {
        'assets',
        'asset_meta_closures',
        'asset_meta_snapshots',
        'asset_meta_values',
        'asset_types',
        'asset_groups',
        'asset_group_members',
        'asset_group_links',
        'data_sources',
        'sli_definitions',
        'slo_assignments',
        'slo_definitions',
        'slo_display_group_members',
        'slo_display_groups',
        'slo_group_assignments',
        'slo_groups',
        'slo_objectives',
        'evaluations',
        'slo_evaluations',
        'evaluation_annotations',
        'indicator_results',
        'sli_values',
    }


def test_slo_evaluation_model_exists() -> None:
    col_names = {c.name for c in SLOEvaluation.__table__.columns}
    assert 'evaluation_id' in col_names
    assert 'evaluation_name' in col_names
    assert 'slo_name' in col_names
    assert 'achieved_points' in col_names
    assert 'total_points' in col_names
    assert SLOEvaluation.__tablename__ == 'slo_evaluations'


def test_evaluation_run_model_exists() -> None:
    col_names = {c.name for c in EvaluationRun.__table__.columns}
    assert 'id' in col_names
    assert 'asset_id' in col_names
    assert 'eval_name' in col_names
    assert 'status' in col_names
    assert 'result' in col_names
    assert 'achieved_points' in col_names
    assert 'total_points' in col_names
    assert EvaluationRun.__tablename__ == 'evaluations'


def test_evaluation_batch_removed() -> None:
    assert not hasattr(models, 'EvaluationBatch')


def test_indicator_result_uses_slo_evaluation_id() -> None:
    col_names = {c.name for c in IndicatorResultRow.__table__.columns}
    assert 'slo_evaluation_id' in col_names
    assert 'evaluation_id' not in col_names


def test_sli_value_uses_slo_evaluation_id() -> None:
    col_names = {c.name for c in SLIValue.__table__.columns}
    assert 'slo_evaluation_id' in col_names
    assert 'eval_id' not in col_names


def test_annotation_uses_slo_evaluation_id() -> None:
    col_names = {c.name for c in EvaluationAnnotation.__table__.columns}
    assert 'slo_evaluation_id' in col_names
    assert 'evaluation_id' not in col_names


def test_asset_group_member_uses_asset_group_id() -> None:
    col_names = {c.name for c in AssetGroupMember.__table__.columns}
    assert 'asset_group_id' in col_names
    assert 'group_id' not in col_names


def test_asset_group_link_uses_renamed_fk_cols() -> None:
    col_names = {c.name for c in AssetGroupLink.__table__.columns}
    assert 'parent_asset_group_id' in col_names
    assert 'child_asset_group_id' in col_names
    assert 'parent_group_id' not in col_names
    assert 'child_group_id' not in col_names
