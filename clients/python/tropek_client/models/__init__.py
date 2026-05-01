"""Models package — common types, enums, and pagination."""

from tropek_client.models.asset_groups import (
    AddMemberRequest,
    AddSubgroupRequest,
    AssetGroupCreate,
    AssetGroupMemberCreate,
    AssetGroupMemberRead,
    AssetGroupRead,
    AssetGroupSubgroupCreate,
    AssetGroupSubgroupRead,
    AssetGroupTreeResponse,
    AssetGroupUpdate,
    AssetScope,
)
from tropek_client.models.asset_types import (
    AssetTypeCreate,
    AssetTypeRead,
    AssetTypeUpdate,
)
from tropek_client.models.assets import (
    AssetCreate,
    AssetRead,
    AssetSnapshot,
    AssetUpdate,
)
from tropek_client.models.common import (
    AggregateFunction,
    AggregationMethod,
    CategoryColor,
    Direction,
    ErrorMessage,
    TagKeyCount,
    TagValueCount,
)
from tropek_client.models.pagination import PagedResponse

# Legacy models from models.py (to be migrated to structured model files)
# Import temporarily for client.py compatibility
try:
    from tropek_client import models as _legacy_models

    Annotation = getattr(_legacy_models, 'Annotation', None)
    Asset = getattr(_legacy_models, 'Asset', None)
    AssetGroup = getattr(_legacy_models, 'AssetGroup', None)
    AssetGroupTree = getattr(_legacy_models, 'AssetGroupTree', None)
    AssetType = getattr(_legacy_models, 'AssetType', None)
    DataSource = getattr(_legacy_models, 'DataSource', None)
    EvaluationDetail = getattr(_legacy_models, 'EvaluationDetail', None)
    EvaluationSummary = getattr(_legacy_models, 'EvaluationSummary', None)
    SLIDefinition = getattr(_legacy_models, 'SLIDefinition', None)
    SLOAssignment = getattr(_legacy_models, 'SLOAssignment', None)
    SLODefinition = getattr(_legacy_models, 'SLODefinition', None)
    SLOGroup = getattr(_legacy_models, 'SLOGroup', None)
    SLOGroupAssignment = getattr(_legacy_models, 'SLOGroupAssignment', None)
    SLOTestResult = getattr(_legacy_models, 'SLOTestResult', None)
    SLOValidationResult = getattr(_legacy_models, 'SLOValidationResult', None)
    TrendPoint = getattr(_legacy_models, 'TrendPoint', None)
except (ImportError, AttributeError):
    pass

__all__ = [
    'AddMemberRequest',
    'AddSubgroupRequest',
    'AggregateFunction',
    'AggregationMethod',
    'Annotation',
    'Asset',
    'AssetCreate',
    'AssetGroup',
    'AssetGroupCreate',
    'AssetGroupMemberCreate',
    'AssetGroupMemberRead',
    'AssetGroupRead',
    'AssetGroupSubgroupCreate',
    'AssetGroupSubgroupRead',
    'AssetGroupTree',
    'AssetGroupTreeResponse',
    'AssetGroupUpdate',
    'AssetRead',
    'AssetScope',
    'AssetSnapshot',
    'AssetType',
    'AssetTypeCreate',
    'AssetTypeRead',
    'AssetTypeUpdate',
    'AssetUpdate',
    'CategoryColor',
    'DataSource',
    'Direction',
    'ErrorMessage',
    'EvaluationDetail',
    'EvaluationSummary',
    'PagedResponse',
    'SLIDefinition',
    'SLOAssignment',
    'SLODefinition',
    'SLOGroup',
    'SLOGroupAssignment',
    'SLOTestResult',
    'SLOValidationResult',
    'TagKeyCount',
    'TagValueCount',
    'TrendPoint',
]
