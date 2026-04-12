"""Schema contract tests -- verify API response shapes match expected field names.

These tests prevent silent API contract breakage when fields are renamed in
Pydantic schemas.  If a field rename happens in the backend but the UI is not
updated, these tests document the expected contract.
"""

import inspect

from fastapi.routing import APIRoute
from pydantic import BaseModel
from tropek.main import app
from tropek.modules.assets.schemas import AssetCreate, AssetRead
from tropek.modules.common.schemas import StrictInput
from tropek.modules.datasource.schemas import DataSourceRead
from tropek.modules.quality_gate.schemas import (
    AnnotationRead,
    EvaluateSingleRequest,
    EvaluationSummary,
)
from tropek.modules.quality_gate.schemas.evaluations import (
    AssetSnapshot,
    EvaluationDetail,
    IndicatorResult,
    PassTarget,
    SliMetadata,
)
from tropek.modules.quality_gate.schemas import heatmap as heatmap_module
from tropek.modules.quality_gate.schemas.heatmap import (
    HeatmapCellGrouped,
    HeatmapSloGroupSection,
    HeatmapSummaryCell,
)
from tropek.modules.sli_registry.schemas import SLIDefinitionRead
from tropek.modules.slo_registry.schemas import (
    ComparisonConfig,
    MethodCriteriaOverride,
    SLODefinitionCreate,
    SLODefinitionRead,
)


def _field_names(model: type[BaseModel]) -> set[str]:
    """Return the set of field names declared on a Pydantic model."""
    return set(model.model_fields.keys())


# -- Assets ------------------------------------------------------------------


class TestAssetSchemaContract:
    """Asset API responses must contain 'tags' (not 'labels')."""

    def test_asset_read_has_tags(self) -> None:
        fields = _field_names(AssetRead)
        assert 'tags' in fields, "AssetRead missing 'tags' -- was it renamed?"
        assert 'labels' not in fields, "AssetRead still has 'labels' -- rename incomplete"

    def test_asset_read_has_variables(self) -> None:
        assert 'variables' in _field_names(AssetRead)

    def test_asset_create_has_tags(self) -> None:
        fields = _field_names(AssetCreate)
        assert 'tags' in fields
        assert 'labels' not in fields


# -- DataSource ---------------------------------------------------------------


class TestDataSourceSchemaContract:
    """DataSource API responses must contain 'tags' and 'has_token'."""

    def test_datasource_read_has_tags(self) -> None:
        fields = _field_names(DataSourceRead)
        assert 'tags' in fields
        assert 'labels' not in fields

    def test_datasource_read_has_has_token(self) -> None:
        assert 'has_token' in _field_names(DataSourceRead)

    def test_datasource_read_excludes_token_value(self) -> None:
        assert 'token' not in _field_names(DataSourceRead)


# -- SLI Registry -------------------------------------------------------------


class TestSLISchemaContract:
    """SLI API responses must contain 'tags' (not 'meta')."""

    def test_sli_read_has_tags(self) -> None:
        fields = _field_names(SLIDefinitionRead)
        assert 'tags' in fields
        assert 'meta' not in fields


# -- SLO Registry -------------------------------------------------------------


class TestSLOSchemaContract:
    """SLO API responses must contain 'tags' and 'variables' (not 'meta')."""

    def test_slo_read_has_tags(self) -> None:
        fields = _field_names(SLODefinitionRead)
        assert 'tags' in fields
        assert 'meta' not in fields

    def test_slo_read_has_variables(self) -> None:
        assert 'variables' in _field_names(SLODefinitionRead)


# -- Evaluations --------------------------------------------------------------


class TestEvaluationSchemaContract:
    """Evaluation API responses must use 'variables' (not 'evaluation_metadata')."""

    def test_evaluation_summary_has_variables(self) -> None:
        fields = _field_names(EvaluationSummary)
        assert 'variables' in fields
        assert 'evaluation_metadata' not in fields

    def test_evaluate_request_has_variables(self) -> None:
        fields = _field_names(EvaluateSingleRequest)
        assert 'variables' in fields
        assert 'metadata' not in fields


# -- Evaluation nested model types (Chunk A §15.1 bugs #1-#4) -----------------


class TestEvaluationNestedTypes:
    """Nested types must be concrete Pydantic models, not dict[str, Any]."""

    def test_asset_snapshot_is_typed_model(self) -> None:
        field = EvaluationSummary.model_fields['asset_snapshot']
        assert field.annotation is AssetSnapshot

    def test_variables_is_str_map(self) -> None:
        field = EvaluationSummary.model_fields['variables']
        assert field.annotation == dict[str, str]

    def test_sli_metadata_value_type_is_typed(self) -> None:
        field = EvaluationDetail.model_fields['sli_metadata']
        assert field.annotation == dict[str, SliMetadata] | None

    def test_pass_targets_is_typed_list(self) -> None:
        field = IndicatorResult.model_fields['pass_targets']
        assert field.annotation == list[PassTarget] | None

    def test_warning_targets_is_typed_list(self) -> None:
        field = IndicatorResult.model_fields['warning_targets']
        assert field.annotation == list[PassTarget] | None


# -- Heatmap nested model types (bugs #5, #7) ---------------------------------


class TestHeatmapNestedTypes:
    def test_heatmap_cell_pass_targets_is_typed(self) -> None:
        field = HeatmapCellGrouped.model_fields['pass_targets']
        assert field.annotation == list[PassTarget] | None

    def test_heatmap_cell_warning_targets_is_typed(self) -> None:
        field = HeatmapCellGrouped.model_fields['warning_targets']
        assert field.annotation == list[PassTarget] | None

    def test_heatmap_summary_sli_metadata_is_typed(self) -> None:
        field = HeatmapSummaryCell.model_fields['sli_metadata']
        assert field.annotation == dict[str, SliMetadata] | None

    def test_sloshim_renamed_to_avoid_collision(self) -> None:
        assert not hasattr(heatmap_module, 'SloGroup')
        assert hasattr(heatmap_module, 'HeatmapSloGroupSection')


# -- SLO registry tightened types (bugs #8, #9 + 2 bonus) --------------------


class TestSloRegistryNestedTypes:
    """SLO registry fields must be typed, not dict[str, Any]."""

    def test_read_variables_is_str_map(self) -> None:
        field = SLODefinitionRead.model_fields['variables']
        assert field.annotation == dict[str, str]

    def test_create_variables_is_str_map(self) -> None:
        field = SLODefinitionCreate.model_fields['variables']
        assert field.annotation == dict[str, str]

    def test_read_tags_is_str_map(self) -> None:
        field = SLODefinitionRead.model_fields['tags']
        assert field.annotation == dict[str, str]

    def test_create_tags_is_str_map(self) -> None:
        field = SLODefinitionCreate.model_fields['tags']
        assert field.annotation == dict[str, str]

    def test_read_comparison_is_typed(self) -> None:
        field = SLODefinitionRead.model_fields['comparison']
        assert field.annotation is ComparisonConfig

    def test_create_comparison_is_typed(self) -> None:
        field = SLODefinitionCreate.model_fields['comparison']
        assert field.annotation is ComparisonConfig

    def test_read_method_criteria_is_typed(self) -> None:
        field = SLODefinitionRead.model_fields['method_criteria']
        assert field.annotation == dict[str, MethodCriteriaOverride] | None

    def test_create_method_criteria_is_typed(self) -> None:
        field = SLODefinitionCreate.model_fields['method_criteria']
        assert field.annotation == dict[str, MethodCriteriaOverride] | None


# -- Annotations --------------------------------------------------------------


class TestAnnotationSchemaContract:
    """Annotation schemas must use 'tags' (not 'meta')."""

    def test_annotation_read_has_tags(self) -> None:
        fields = _field_names(AnnotationRead)
        assert 'tags' in fields
        assert 'meta' not in fields


# -- StrictInput enforcement ---------------------------------------------------


def _collect_body_models() -> list[tuple[str, type[BaseModel]]]:
    """Walk all API routes and collect Pydantic models used as request bodies."""
    models: list[tuple[str, type[BaseModel]]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        sig = inspect.signature(route.endpoint)
        for name, param in sig.parameters.items():
            annotation = param.annotation
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                models.append((f'{route.path} param={name}', annotation))
    return models


def _collect_nested_models(model: type[BaseModel]) -> list[type[BaseModel]]:
    """Recursively collect nested Pydantic models from field annotations."""
    nested: list[type[BaseModel]] = []
    for field_info in model.model_fields.values():
        annotation = field_info.annotation
        # Unwrap generic types (list[X], X | None, etc.)
        args = getattr(annotation, '__args__', None)
        candidates = list(args) if args else [annotation]
        for candidate in candidates:
            if isinstance(candidate, type) and issubclass(candidate, BaseModel):
                nested.append(candidate)
                nested.extend(_collect_nested_models(candidate))
    return nested


class TestStrictInputEnforcement:
    """Every Pydantic model used as a request body must inherit StrictInput."""

    def test_all_body_models_inherit_strict_input(self) -> None:
        violations: list[str] = []
        for route_label, model in _collect_body_models():
            all_models = [model, *_collect_nested_models(model)]
            violations.extend(
                f'{m.__name__} (used in {route_label})' for m in all_models if not issubclass(m, StrictInput)
            )
        assert not violations, f'body models must inherit StrictInput: {", ".join(sorted(set(violations)))}'
