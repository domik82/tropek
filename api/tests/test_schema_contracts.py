"""Schema contract tests -- verify API response shapes match expected field names.

These tests prevent silent API contract breakage when fields are renamed in
Pydantic schemas.  If a field rename happens in the backend but the UI is not
updated, these tests document the expected contract.
"""

from app.modules.assets.schemas import AssetCreate, AssetRead
from app.modules.datasource.schemas import DataSourceRead
from app.modules.quality_gate.schemas import (
    AnnotationRead,
    EvaluationSummary,
    TriggerRequest,
)
from app.modules.sli_registry.schemas import SLIDefinitionRead
from app.modules.slo_registry.schemas import SLODefinitionRead
from pydantic import BaseModel


def _field_names(model: type[BaseModel]) -> set[str]:
    """Return the set of field names declared on a Pydantic model."""
    return set(model.model_fields.keys())


# -- Assets ------------------------------------------------------------------


class TestAssetSchemaContract:
    """Asset API responses must contain 'tags' (not 'labels')."""

    def test_asset_read_has_tags(self) -> None:
        fields = _field_names(AssetRead)
        assert "tags" in fields, "AssetRead missing 'tags' -- was it renamed?"
        assert "labels" not in fields, "AssetRead still has 'labels' -- rename incomplete"

    def test_asset_read_has_variables(self) -> None:
        assert "variables" in _field_names(AssetRead)

    def test_asset_create_has_tags(self) -> None:
        fields = _field_names(AssetCreate)
        assert "tags" in fields
        assert "labels" not in fields


# -- DataSource ---------------------------------------------------------------


class TestDataSourceSchemaContract:
    """DataSource API responses must contain 'tags' and 'has_token'."""

    def test_datasource_read_has_tags(self) -> None:
        fields = _field_names(DataSourceRead)
        assert "tags" in fields
        assert "labels" not in fields

    def test_datasource_read_has_has_token(self) -> None:
        assert "has_token" in _field_names(DataSourceRead)

    def test_datasource_read_excludes_token_value(self) -> None:
        assert "token" not in _field_names(DataSourceRead)


# -- SLI Registry -------------------------------------------------------------


class TestSLISchemaContract:
    """SLI API responses must contain 'tags' (not 'meta')."""

    def test_sli_read_has_tags(self) -> None:
        fields = _field_names(SLIDefinitionRead)
        assert "tags" in fields
        assert "meta" not in fields


# -- SLO Registry -------------------------------------------------------------


class TestSLOSchemaContract:
    """SLO API responses must contain 'tags' and 'variables' (not 'meta')."""

    def test_slo_read_has_tags(self) -> None:
        fields = _field_names(SLODefinitionRead)
        assert "tags" in fields
        assert "meta" not in fields

    def test_slo_read_has_variables(self) -> None:
        assert "variables" in _field_names(SLODefinitionRead)


# -- Evaluations --------------------------------------------------------------


class TestEvaluationSchemaContract:
    """Evaluation API responses must use 'variables' (not 'evaluation_metadata')."""

    def test_evaluation_summary_has_variables(self) -> None:
        fields = _field_names(EvaluationSummary)
        assert "variables" in fields
        assert "evaluation_metadata" not in fields

    def test_trigger_request_has_variables(self) -> None:
        fields = _field_names(TriggerRequest)
        assert "variables" in fields
        assert "metadata" not in fields


# -- Annotations --------------------------------------------------------------


class TestAnnotationSchemaContract:
    """Annotation schemas must use 'tags' (not 'meta')."""

    def test_annotation_read_has_tags(self) -> None:
        fields = _field_names(AnnotationRead)
        assert "tags" in fields
        assert "meta" not in fields
