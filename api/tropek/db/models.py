"""SQLAlchemy ORM declarative models for all Phase 1 entities."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    UUID,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# TODO docstring what each value holds?


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


class AssetType(Base):
    """User-extensible asset type vocabulary. One row may be marked as the default."""

    __tablename__ = 'asset_types'
    __table_args__ = (
        Index('idx_asset_types_name', 'name'),
        # Enforces at most one default at the DB level
        Index(
            'uq_asset_types_default',
            'is_default',
            unique=True,
            postgresql_where=text('is_default = true'),
        ),
    )

    # fmt: off
    id:         Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name:       Mapped[str]       = mapped_column(Text, unique=True, nullable=False)
    is_default: Mapped[bool]      = mapped_column(Boolean, nullable=False, server_default=false(), default=False)
    # fmt: on


class Asset(Base):
    """A named entity under test — VM, service, container, or endpoint."""

    __tablename__ = 'assets'

    # fmt: off
    id:           Mapped[uuid.UUID]      = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name:         Mapped[str]            = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str | None]     = mapped_column(Text, nullable=True)
    type_name:    Mapped[str]            = mapped_column(Text, ForeignKey('asset_types.name'), nullable=False, default='vm')
    tags:           Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    variables:      Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    heatmap_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    color:          Mapped[str | None]    = mapped_column(Text, nullable=True)
    created_at:   Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at:   Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    # fmt: on


class AssetMetaSnapshot(Base):
    """Point-in-time snapshot of hierarchical metadata pushed for one asset from one source."""

    __tablename__ = 'asset_meta_snapshots'
    __table_args__ = (
        Index('idx_asset_meta_snapshots_asset_observed', 'asset_id', 'observed_at'),
        Index('idx_asset_meta_snapshots_asset_source_observed', 'asset_id', 'source', 'observed_at'),
    )

    # fmt: off
    id:          Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    asset_id:    Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('assets.id', ondelete='CASCADE'), nullable=False)
    source:      Mapped[str]       = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), nullable=False)
    created_at:  Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # fmt: on


class AssetMetaValue(Base):
    """One key-value leaf in a snapshot — path is a TEXT[] hierarchy, value is the leaf text."""

    __tablename__ = 'asset_meta_values'
    __table_args__ = (
        UniqueConstraint('snapshot_id', 'path', name='uq_asset_meta_values_snapshot_path'),
        Index('idx_asset_meta_values_snapshot', 'snapshot_id'),
    )

    # fmt: off
    id:          Mapped[int]       = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('asset_meta_snapshots.id', ondelete='CASCADE'), nullable=False)
    path:        Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    value:       Mapped[str]       = mapped_column(Text, nullable=False)
    # fmt: on


class AssetMetaClosure(Base):
    """Closure-table row for a snapshot — every ancestor path present in that snapshot."""

    __tablename__ = 'asset_meta_closures'
    __table_args__ = (
        UniqueConstraint('snapshot_id', 'path', name='uq_asset_meta_closures_snapshot_path'),
        Index('idx_asset_meta_closures_snapshot', 'snapshot_id'),
    )

    # fmt: off
    id:          Mapped[int]       = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('asset_meta_snapshots.id', ondelete='CASCADE'), nullable=False)
    path:        Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    # fmt: on


class AssetGroup(Base):
    """Named container of assets or other groups.

    Supports flat groups (linux_boxes = [vm-01, vm-02]) and
    group-of-groups (software_xyz = [linux_boxes, windows_vms]).
    """

    __tablename__ = 'asset_groups'

    # fmt: off

    id:           Mapped[uuid.UUID]  = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name:         Mapped[str]        = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    description:  Mapped[str | None] = mapped_column(Text, nullable=True)
    color:        Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at:   Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at:   Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # fmt: on


class AssetGroupMember(Base):
    """Associates individual assets with an asset group, with optional weight."""

    __tablename__ = 'asset_group_members'
    __table_args__ = (
        Index('idx_asset_group_members_group', 'asset_group_id'),
        Index('idx_asset_group_members_asset', 'asset_id'),
    )

    # fmt: off
    asset_group_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('asset_groups.id', ondelete='CASCADE'), nullable=False, primary_key=True)
    asset_id:       Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('assets.id', ondelete='CASCADE'), nullable=False, primary_key=True)
    weight:         Mapped[float]     = mapped_column(Float, nullable=False, default=1.0)
    # fmt: on


class AssetGroupLink(Base):
    """Links a child group inside a parent group (group-of-groups)."""

    __tablename__ = 'asset_group_links'
    __table_args__ = (Index('idx_asset_group_links_parent', 'parent_asset_group_id'),)

    # fmt: off
    parent_asset_group_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('asset_groups.id', ondelete='CASCADE'), nullable=False, primary_key=True)
    child_asset_group_id:  Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('asset_groups.id', ondelete='CASCADE'), nullable=False, primary_key=True)
    weight:                Mapped[float]     = mapped_column(Float, nullable=False, default=1.0)
    # fmt: on


class DataSource(Base):
    """Named pointer to a running adapter service instance.

    The adapter manages its own connection credentials via env vars.
    TROPEK stores only where to send queries (adapter_url) and free-form
    tags for discovery. Names are unique across the deployment.
    """

    __tablename__ = 'data_sources'
    __table_args__ = (Index('idx_data_sources_name', 'name'),)

    # fmt: off

    id:           Mapped[uuid.UUID]        = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name:         Mapped[str]              = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str | None]       = mapped_column(Text, nullable=True)
    adapter_type: Mapped[str]              = mapped_column(Text, nullable=False)
    adapter_url:  Mapped[str]              = mapped_column(Text, nullable=False)
    tags:         Mapped[dict[str, Any]]   = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    token:        Mapped[str | None]       = mapped_column(Text, nullable=True)
    created_at:   Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at:   Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # fmt: on


class SLIDefinition(Base):
    """Versioned set of indicator queries for one adapter type.

    Rows are immutable after insert — same versioning pattern as SLODefinition.
    Each indicator maps a name to an adapter-specific query string (PromQL, SQL, etc.).
    Variable tokens ($vm_ip, $period_start, etc.) are substituted at evaluation time.
    """

    __tablename__ = 'sli_definitions'
    __table_args__ = (
        UniqueConstraint('name', 'version', name='uq_sli_name_version'),
        Index('idx_sli_definitions_name', 'name'),
        Index('idx_sli_definitions_latest', 'name', text('version DESC')),
    )

    # fmt: off

    id:           Mapped[uuid.UUID]        = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name:         Mapped[str]              = mapped_column(Text, nullable=False)
    adapter_type: Mapped[str]              = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None]       = mapped_column(Text, nullable=True)
    version:                  Mapped[int]              = mapped_column(Integer, nullable=False)
    comparable_from_version:  Mapped[int]              = mapped_column(Integer, nullable=False, server_default=text('1'))
    indicators:               Mapped[dict[str, Any]]   = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    notes:        Mapped[str | None]       = mapped_column(Text, nullable=True)
    author:       Mapped[str | None]       = mapped_column(Text, nullable=True)
    tags:         Mapped[dict[str, Any]]   = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    mode:         Mapped[str]              = mapped_column(Text, nullable=False, server_default=text("'raw'"), default='raw')
    query_template: Mapped[str | None]     = mapped_column(Text, nullable=True)
    interval:     Mapped[str | None]       = mapped_column(Text, nullable=True)
    methods:      Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    active:       Mapped[bool]             = mapped_column(Boolean, nullable=False, server_default=true(), default=True)
    created_at:   Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # fmt: on


class SLOObjective(Base):
    """One objective row per SLO definition version — immutable after insert."""

    __tablename__ = 'slo_objectives'
    __table_args__ = (Index('idx_slo_objectives_definition', 'slo_definition_id'),)

    # fmt: off
    id:                Mapped[uuid.UUID]      = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    slo_definition_id: Mapped[uuid.UUID]      = mapped_column(UUID, ForeignKey('slo_definitions.id', ondelete='CASCADE'), nullable=False)
    sli:               Mapped[str]            = mapped_column(Text, nullable=False)
    display_name:      Mapped[str]            = mapped_column(Text, nullable=False, server_default='')
    weight:            Mapped[int]            = mapped_column(Integer, nullable=False, server_default=text('1'))
    key_sli:           Mapped[bool]           = mapped_column(Boolean, nullable=False, server_default=false())
    sort_order:        Mapped[int]            = mapped_column(Integer, nullable=False)
    pass_threshold:     Mapped[list[str]]      = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    warning_threshold:  Mapped[list[str]]      = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    tab_group:         Mapped[str | None]     = mapped_column(Text, nullable=True)
    # fmt: on


class ChangePointConfig(Base):
    """Per-indicator Otava detection override — SPARSE table.

    Rows exist ONLY to override the hardcoded defaults for a specific
    (slo_name, metric_name). Absence of a row = use defaults = detection
    enabled with standard window_size and min_sample_size.
    """

    __tablename__ = 'change_point_config'
    __table_args__ = (
        UniqueConstraint('slo_name', 'metric_name', name='uq_cp_config_slo_metric'),
    )

    # fmt: off
    id:              Mapped[uuid.UUID]      = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    slo_name:        Mapped[str]            = mapped_column(Text, nullable=False)
    metric_name:     Mapped[str]            = mapped_column(Text, nullable=False)
    enabled:         Mapped[bool]           = mapped_column(Boolean, nullable=False, server_default=text('true'))
    window_size:     Mapped[int]            = mapped_column(Integer, nullable=False, server_default=text('30'))
    max_pvalue:      Mapped[float]          = mapped_column(Float, nullable=False, server_default=text('0.001'))
    min_magnitude:   Mapped[float]          = mapped_column(Float, nullable=False, server_default=text('0.0'))
    min_sample_size: Mapped[int]            = mapped_column(Integer, nullable=False, server_default=text('10'))
    created_at:      Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:      Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # fmt: on


class ChangePoint(Base):
    """Detected distributional shift for a single metric — denormalized identity."""

    __tablename__ = 'change_points'
    __table_args__ = (
        Index('idx_change_points_indicator', 'indicator_result_id'),
        Index('idx_change_points_identity', 'asset_id', 'slo_name', 'metric_name', 'period_start'),
        Index('idx_change_points_unprocessed', 'status', postgresql_where=text("status = 'unprocessed'")),
        Index('idx_change_points_created', 'created_at'),
    )

    # fmt: off
    id:                   Mapped[uuid.UUID]        = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    indicator_result_id:  Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey('indicator_results.id', ondelete='SET NULL'), nullable=True)
    asset_id:             Mapped[uuid.UUID]        = mapped_column(UUID, nullable=False)
    slo_name:             Mapped[str]              = mapped_column(Text, nullable=False)
    metric_name:          Mapped[str]              = mapped_column(Text, nullable=False)
    period_start:         Mapped[datetime]         = mapped_column(DateTime(timezone=True), nullable=False)
    direction:            Mapped[str]              = mapped_column(Text, nullable=False)
    change_relative_pct:  Mapped[float]            = mapped_column(Float, nullable=False)
    change_absolute:      Mapped[float]            = mapped_column(Float, nullable=False)
    t_statistic:          Mapped[float]            = mapped_column(Float, nullable=False)
    pre_segment_mean:     Mapped[float]            = mapped_column(Float, nullable=False)
    post_segment_mean:    Mapped[float]            = mapped_column(Float, nullable=False)
    status:               Mapped[str]              = mapped_column(Text, nullable=False, server_default=text("'unprocessed'"))
    triage_author:        Mapped[str | None]       = mapped_column(Text, nullable=True)
    triage_note:          Mapped[str | None]       = mapped_column(Text, nullable=True)
    triage_at:            Mapped[datetime | None]  = mapped_column(DateTime(timezone=True), nullable=True)
    linked_ticket:        Mapped[str | None]       = mapped_column(Text, nullable=True)
    created_at:           Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:           Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # fmt: on


class IndicatorResultRow(Base):
    """Normalized indicator result — one row per SLI per evaluation."""

    __tablename__ = 'indicator_results'
    __table_args__ = (
        Index('idx_indicator_results_slo_evaluation', 'slo_evaluation_id'),
        Index('idx_indicator_results_objective_status', 'slo_objective_id', 'status'),
        UniqueConstraint(
            'slo_evaluation_id',
            'slo_objective_id',
            name='uq_indicator_results_eval_objective',
        ),
    )

    # fmt: off
    id:                 Mapped[uuid.UUID]    = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    slo_evaluation_id:  Mapped[uuid.UUID]    = mapped_column(UUID, ForeignKey('slo_evaluations.id', ondelete='CASCADE'), nullable=False)
    slo_objective_id:   Mapped[uuid.UUID]    = mapped_column(UUID, ForeignKey('slo_objectives.id', ondelete='CASCADE'), nullable=False)
    value:              Mapped[float | None] = mapped_column(Float, nullable=True)
    compared_value:     Mapped[float | None] = mapped_column(Float, nullable=True)
    change_absolute:    Mapped[float | None] = mapped_column(Float, nullable=True)
    change_relative_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    status:             Mapped[str]          = mapped_column(Text, nullable=False)
    score:              Mapped[float]        = mapped_column(Float, nullable=False, server_default=text('0'))
    targets:            Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # fmt: on

    # Relationships for eager loading
    objective: Mapped[SLOObjective] = relationship('SLOObjective', lazy='joined')


class SLODefinition(Base):
    """Versioned SLO definition — rows are immutable after insert."""

    __tablename__ = 'slo_definitions'
    __table_args__ = (
        UniqueConstraint('name', 'version', name='uq_slo_name_version'),
        Index('idx_slo_definitions_name', 'name'),
        # version DESC so get_latest() queries hit this index efficiently
        Index('idx_slo_definitions_latest', 'name', text('version DESC')),
    )

    # fmt: off

    id:                      Mapped[uuid.UUID]              = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name:                    Mapped[str]                    = mapped_column(Text, nullable=False)
    display_name:            Mapped[str | None]             = mapped_column(Text, nullable=True)
    version:                 Mapped[int]                    = mapped_column(Integer, nullable=False)
    comparable_from_version: Mapped[int]                    = mapped_column(Integer, nullable=False, server_default=text('1'))
    total_score_pass_threshold:    Mapped[float]                  = mapped_column(Float, nullable=False, server_default=text('90.0'))
    total_score_warning_threshold: Mapped[float]                  = mapped_column(Float, nullable=False, server_default=text('75.0'))
    comparison:              Mapped[dict[str, Any]]         = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)
    notes:                   Mapped[str | None]             = mapped_column(Text, nullable=True)
    author:                  Mapped[str | None]             = mapped_column(Text, nullable=True)
    tags:                    Mapped[dict[str, Any]]         = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    variables:               Mapped[dict[str, Any]]         = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    kind:                    Mapped[str]                    = mapped_column(Text, nullable=False, server_default=text("'standard'"), default='standard')
    sli_definition_id:       Mapped[uuid.UUID | None]       = mapped_column(UUID, ForeignKey('sli_definitions.id'), nullable=True)
    sli_definition:          Mapped[SLIDefinition | None] = relationship('SLIDefinition', lazy='joined', foreign_keys=[sli_definition_id])
    method_criteria:         Mapped[dict[str, Any] | None]  = mapped_column(JSONB, nullable=True)
    generated_by_group_id:   Mapped[uuid.UUID | None]       = mapped_column(UUID, ForeignKey("slo_groups.id"), nullable=True)
    active:                  Mapped[bool]                   = mapped_column(Boolean, nullable=False, server_default=true(), default=True)
    created_at:              Mapped[datetime]               = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    objectives:              Mapped[list[SLOObjective]]     = relationship(
        'SLOObjective',
        order_by='SLOObjective.sort_order',
        cascade='all, delete-orphan',
        lazy='selectin',
    )

    # fmt: on

    @property
    def sli_name(self) -> str | None:
        """Denormalized SLI name from the linked definition."""
        if self.sli_definition is None:
            return None
        return self.sli_definition.name

    @property
    def sli_version(self) -> int | None:
        """Denormalized SLI version from the linked definition."""
        if self.sli_definition is None:
            return None
        return self.sli_definition.version


class AnnotationCategory(Base):
    """Category taxonomy for evaluation annotations.

    System rows (is_system=True) cannot be deleted; their name is immutable,
    but show_on_graph remains toggleable.
    """

    __tablename__ = 'annotation_categories'

    # fmt: off
    id:             Mapped[uuid.UUID]  = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name:           Mapped[str]        = mapped_column(Text, unique=True, nullable=False)
    label:          Mapped[str]        = mapped_column(Text, nullable=False)
    color:          Mapped[str]        = mapped_column(Text, nullable=False)
    show_on_graph:  Mapped[bool]       = mapped_column(Boolean, nullable=False, server_default=text('true'))
    is_system:      Mapped[bool]       = mapped_column(Boolean, nullable=False, server_default=text('false'))
    created_at:     Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at:     Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    # fmt: on


class EvaluationAnnotation(Base):
    """Append-only contextual note on an evaluation.

    Attaches to exactly one parent — either an SLOEvaluation (per-SLO notes, e.g. re-eval
    deltas) or an EvaluationRun (column-level notes from the UI). The XOR is enforced at
    the DB level by a check constraint.
    """

    __tablename__ = 'evaluation_annotations'
    __table_args__ = (
        Index('idx_annotations_slo_evaluation', 'slo_evaluation_id'),
        Index('idx_annotations_evaluation_run', 'evaluation_run_id'),
        CheckConstraint(
            '(slo_evaluation_id IS NULL) <> (evaluation_run_id IS NULL)',
            name='ck_annotation_exactly_one_parent',
        ),
    )

    # fmt: off

    id:                Mapped[uuid.UUID]        = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    slo_evaluation_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey('slo_evaluations.id', ondelete='CASCADE'), nullable=True)
    evaluation_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey('evaluations.id', ondelete='CASCADE'), nullable=True)
    content:           Mapped[str]              = mapped_column(Text, nullable=False)
    author:            Mapped[str | None]       = mapped_column(Text, nullable=True)
    category_id:       Mapped[uuid.UUID]        = mapped_column(UUID, ForeignKey('annotation_categories.id'), nullable=False)
    category:          Mapped[AnnotationCategory] = relationship('AnnotationCategory')
    tags:              Mapped[dict[str, Any]]   = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    note_group_id:     Mapped[uuid.UUID | None] = mapped_column(UUID, nullable=True, index=True)
    note_group_name:   Mapped[str | None]       = mapped_column(Text, nullable=True)
    hidden_at:         Mapped[datetime | None]  = mapped_column(DateTime(timezone=True), nullable=True)
    hidden_by:         Mapped[str | None]       = mapped_column(Text, nullable=True)
    hidden_reason:     Mapped[str | None]       = mapped_column(Text, nullable=True)
    created_at:        Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at:        Mapped[datetime | None]  = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    slo_evaluation:    Mapped[SLOEvaluation | None] = relationship('SLOEvaluation', back_populates='annotations')
    evaluation_run:    Mapped[EvaluationRun | None] = relationship('EvaluationRun', back_populates='annotations')

    # fmt: on


class SLIValue(Base):
    """TimescaleDB hypertable — one aggregated metric value per evaluation.

    Partitioned by eval_start for efficient time-range queries in Grafana.
    Composite PK required: TimescaleDB needs the partition key in the PK.
    Denormalised columns (asset_name, evaluation_name, os_tag) avoid joins in Grafana SQL.
    No ORM relationship to SLOEvaluation is intentional — prevents accidental lazy-loading
    of potentially thousands of hypertable rows.
    """

    __tablename__ = 'sli_values'
    __table_args__ = (Index('idx_sli_values_lookup', 'evaluation_name', 'metric_name', 'eval_start'),)

    # fmt: off
    # TODO : probably to flat stucture - joins should probably be used in Grafana - not convinced this is good

    slo_evaluation_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('slo_evaluations.id'), nullable=False, primary_key=True)
    eval_start:        Mapped[datetime]  = mapped_column(DateTime(timezone=True), nullable=False, primary_key=True)
    metric_name:       Mapped[str]       = mapped_column(Text, nullable=False, primary_key=True)
    aggregation:       Mapped[str]       = mapped_column(Text, nullable=False, primary_key=True)
    value:             Mapped[float]     = mapped_column(Float, nullable=False)
    asset_name:        Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluation_name:   Mapped[str | None] = mapped_column(Text, nullable=True)
    os_tag:            Mapped[str | None] = mapped_column(Text, nullable=True)

    # fmt: on


class SLOGroup(Base):
    """SLO group — generates SLO instances from a template via variable expansion."""

    __tablename__ = 'slo_groups'
    __table_args__ = (
        Index('idx_slo_groups_name', 'name'),
        Index('uq_slo_groups_name_active', 'name', unique=True, postgresql_where=text('active = true')),
    )

    # fmt: off

    id:                   Mapped[uuid.UUID]  = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name:                 Mapped[str]        = mapped_column(Text, nullable=False)
    display_name:         Mapped[str | None] = mapped_column(Text, nullable=True)
    template_slo_definition_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('slo_definitions.id', use_alter=True, name='fk_slo_groups_template_slo_definition_id'), nullable=False)
    gen_variables:        Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)
    tags:                 Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    author:               Mapped[str | None]     = mapped_column(Text, nullable=True)
    version:              Mapped[int]            = mapped_column(Integer, nullable=False, server_default=text("1"), default=1)
    active:               Mapped[bool]           = mapped_column(Boolean, nullable=False, server_default=true(), default=True)
    created_at:           Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at:           Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # fmt: on


class SLOAssignment(Base):
    """Version-pinned assignment of a specific SLO definition to an asset or asset group."""

    __tablename__ = 'slo_assignments'
    __table_args__ = (
        Index(
            'uq_slo_assignments_asset_slo',
            'asset_id',
            'slo_name',
            unique=True,
            postgresql_where=text('asset_id IS NOT NULL'),
        ),
        Index(
            'uq_slo_assignments_group_slo',
            'asset_group_id',
            'slo_name',
            unique=True,
            postgresql_where=text('asset_group_id IS NOT NULL'),
        ),
        CheckConstraint(
            '(asset_id IS NULL) != (asset_group_id IS NULL)',
            name='ck_slo_assignments_target',
        ),
        Index('idx_slo_assignments_asset', 'asset_id'),
        Index('idx_slo_assignments_group', 'asset_group_id'),
    )

    # fmt: off
    id:                Mapped[uuid.UUID]                    = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    asset_id:          Mapped[uuid.UUID | None]              = mapped_column(UUID, ForeignKey('assets.id', ondelete='CASCADE'), nullable=True)
    asset_group_id:    Mapped[uuid.UUID | None]              = mapped_column(UUID, ForeignKey('asset_groups.id', ondelete='CASCADE'), nullable=True)
    slo_definition_id: Mapped[uuid.UUID]                    = mapped_column(UUID, ForeignKey('slo_definitions.id'), nullable=False)
    slo_name:          Mapped[str]                          = mapped_column(Text, nullable=False)
    data_source_id:    Mapped[uuid.UUID]                    = mapped_column(UUID, ForeignKey('data_sources.id'), nullable=False)
    comparison_rules:  Mapped[list[dict[str, Any]] | None]  = mapped_column(JSONB, nullable=True)
    created_at:        Mapped[datetime]                     = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # fmt: on

    slo_definition: Mapped[SLODefinition] = relationship(lazy='raise')
    data_source: Mapped[DataSource] = relationship(lazy='raise')


class SLOGroupAssignment(Base):
    """Always-latest assignment of an SLO group to an asset or asset group."""

    __tablename__ = 'slo_group_assignments'
    __table_args__ = (
        Index(
            'uq_slo_group_assignments_asset',
            'asset_id',
            'slo_group_id',
            unique=True,
            postgresql_where=text('asset_id IS NOT NULL'),
        ),
        Index(
            'uq_slo_group_assignments_group',
            'asset_group_id',
            'slo_group_id',
            unique=True,
            postgresql_where=text('asset_group_id IS NOT NULL'),
        ),
        CheckConstraint(
            '(asset_id IS NULL) != (asset_group_id IS NULL)',
            name='ck_slo_group_assignments_target',
        ),
        Index('idx_slo_group_assignments_asset', 'asset_id'),
        Index('idx_slo_group_assignments_asset_group', 'asset_group_id'),
    )

    # fmt: off
    id:             Mapped[uuid.UUID]        = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    asset_id:       Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey('assets.id', ondelete='CASCADE'), nullable=True)
    asset_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey('asset_groups.id', ondelete='CASCADE'), nullable=True)
    slo_group_id:   Mapped[uuid.UUID]        = mapped_column(UUID, ForeignKey('slo_groups.id'), nullable=False)
    data_source_id: Mapped[uuid.UUID]        = mapped_column(UUID, ForeignKey('data_sources.id'), nullable=False)
    created_at:     Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # fmt: on

    slo_group: Mapped[SLOGroup] = relationship(lazy='raise')
    data_source: Mapped[DataSource] = relationship(lazy='raise')


class SLODisplayGroup(Base):
    """UI navigation bucket — organises SLO concepts into a collapsible hierarchy."""

    __tablename__ = 'slo_display_groups'

    # fmt: off
    id:           Mapped[uuid.UUID]        = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name:         Mapped[str]              = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str | None]       = mapped_column(Text, nullable=True)
    parent_id:    Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey('slo_display_groups.id'), nullable=True)
    sort_order:   Mapped[int]              = mapped_column(Integer, nullable=False, server_default=text('0'), default=0)
    created_at:   Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    members: Mapped[list[SLODisplayGroupMember]] = relationship('SLODisplayGroupMember', cascade='all, delete-orphan')
    # fmt: on


class SLODisplayGroupMember(Base):
    """Membership of an SLO concept (by name) in a display group."""

    __tablename__ = 'slo_display_group_members'
    __table_args__ = (Index('idx_slo_display_group_members_slo', 'slo_name'),)

    # fmt: off
    group_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('slo_display_groups.id', ondelete='CASCADE'), primary_key=True)
    slo_name: Mapped[str]       = mapped_column(Text, primary_key=True)
    # fmt: on


class SLOEvaluation(Base):
    """One SLO evaluation — one per SLO bound to an asset for a given evaluation run."""

    __tablename__ = 'slo_evaluations'
    __table_args__ = (
        Index('idx_slo_evaluations_evaluation_name', 'evaluation_name'),
        Index('idx_slo_evaluations_asset', 'asset_id'),
        Index('idx_slo_evaluations_result', 'result'),
        Index('idx_slo_evaluations_start', 'period_start'),
        Index('idx_slo_evaluations_status', 'status'),
        Index('idx_slo_evaluations_slo', 'slo_name', 'slo_version'),
        Index(
            'idx_slo_evaluations_baseline_lookup',
            'asset_id',
            'slo_name',
            text('period_start DESC'),
            postgresql_where=text("status = 'completed' AND invalidated = false"),
        ),
        # Partial index for watchdog: find stuck running jobs efficiently
        Index(
            'idx_slo_evaluations_stuck',
            'status',
            'started_at',
            postgresql_where=text("status = 'running'"),
        ),
        # Duplicate prevention: at most one non-failed evaluation per identity tuple.
        # Failed evaluations are excluded so retries can create a new row.
        Index(
            'uq_slo_evaluations_identity',
            'asset_id',
            'slo_name',
            'evaluation_name',
            'period_start',
            'period_end',
            unique=True,
            postgresql_where=text("status != 'failed'"),
        ),
        CheckConstraint(
            "status IN ('pending','running','completed','failed','partial')",
            name='ck_slo_evaluations_status',
        ),
        CheckConstraint(
            "ingestion_mode IN ('pull','push','file')",
            name='ck_slo_evaluations_ingestion_mode',
        ),
        CheckConstraint(
            "result IN ('pass','warning','fail','error') OR result IS NULL",
            name='ck_slo_evaluations_result',
        ),
    )

    # fmt: off

    id:                   Mapped[uuid.UUID]      = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    evaluation_id:        Mapped[uuid.UUID]      = mapped_column(UUID, ForeignKey('evaluations.id', ondelete='CASCADE'), nullable=False)
    evaluation_name:      Mapped[str]            = mapped_column(Text, nullable=False)
    asset_id:             Mapped[uuid.UUID]      = mapped_column(UUID, ForeignKey('assets.id', ondelete='RESTRICT'), nullable=False)
    asset_snapshot:       Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    period_start:         Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=False)
    period_end:           Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=False)
    result:               Mapped[str | None]     = mapped_column(Text, nullable=True)
    score:                Mapped[float | None]   = mapped_column(Float, nullable=True)
    achieved_points:      Mapped[int | None]     = mapped_column(Integer, nullable=True)
    total_points:         Mapped[int | None]     = mapped_column(Integer, nullable=True)
    slo_name:             Mapped[str]            = mapped_column(Text, nullable=False)
    slo_version:          Mapped[int | None]     = mapped_column(Integer, nullable=True)
    sli_name:             Mapped[str | None]     = mapped_column(Text, nullable=True)
    sli_version:          Mapped[int | None]     = mapped_column(Integer, nullable=True)
    data_source_name:     Mapped[str | None]     = mapped_column(Text, nullable=True)
    slo_definition_id:    Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey('slo_definitions.id'), nullable=True)
    sli_definition_id:    Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey('sli_definitions.id'), nullable=True)
    variables:            Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    ingestion_mode:       Mapped[str]            = mapped_column(Text, nullable=False)
    adapter_used:         Mapped[str | None]     = mapped_column(Text, nullable=True)
    invalidated:          Mapped[bool]           = mapped_column(Boolean, nullable=False, server_default=false(), default=False)
    invalidation_note:    Mapped[str | None]     = mapped_column(Text, nullable=True)
    baseline_pinned_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    baseline_unpinned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    baseline_pin_reason:  Mapped[str | None]     = mapped_column(Text, nullable=True)
    baseline_pin_author:  Mapped[str | None]     = mapped_column(Text, nullable=True)
    original_result:      Mapped[str | None]     = mapped_column(Text, nullable=True)
    override_reason:      Mapped[str | None]     = mapped_column(Text, nullable=True)
    override_author:      Mapped[str | None]     = mapped_column(Text, nullable=True)
    status:               Mapped[str]            = mapped_column(Text, nullable=False, server_default=text("'pending'"), default='pending')
    started_at:           Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    job_stats:            Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    created_at:           Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    annotations:          Mapped[list[EvaluationAnnotation]] = relationship('EvaluationAnnotation', back_populates='slo_evaluation', cascade='all, delete-orphan')
    indicator_rows:       Mapped[list[IndicatorResultRow]]   = relationship('IndicatorResultRow', cascade='all, delete-orphan', lazy='selectin')
    evaluation_run:       Mapped[EvaluationRun]            = relationship('EvaluationRun', back_populates='slo_evaluations')

    # fmt: on


class EvaluationRun(Base):
    """Parent evaluation run — one per asset x eval_name x period.

    Aggregates N child SLOEvaluation rows (one per SLO bound to the asset).
    result = worst-case of children; achieved/total points = sum of children.
    """

    __tablename__ = 'evaluations'
    __table_args__ = (
        Index('idx_evaluations_asset', 'asset_id'),
        Index('idx_evaluations_status', 'status'),
        Index('idx_evaluations_period', 'asset_id', text('period_start DESC')),
        Index(
            'idx_evaluations_incomplete_period_end',
            'period_end',
            postgresql_where=text("status != 'completed'"),
        ),
        CheckConstraint(
            "status IN ('pending','running','completed','failed')",
            name='ck_evaluations_status',
        ),
        CheckConstraint(
            "result IN ('pass','warning','fail','error') OR result IS NULL",
            name='ck_evaluations_result',
        ),
    )

    # fmt: off
    id:              Mapped[uuid.UUID]      = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    asset_id:        Mapped[uuid.UUID]      = mapped_column(UUID, ForeignKey('assets.id', ondelete='RESTRICT'), nullable=False)
    eval_name:       Mapped[str]            = mapped_column(Text, nullable=False)
    period_start:    Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=False)
    period_end:      Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=False)
    status:          Mapped[str]            = mapped_column(Text, nullable=False, server_default=text("'pending'"), default='pending')
    result:          Mapped[str | None]     = mapped_column(Text, nullable=True)
    achieved_points: Mapped[int | None]     = mapped_column(Integer, nullable=True)
    total_points:    Mapped[int | None]     = mapped_column(Integer, nullable=True)
    created_at:      Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    slo_evaluations: Mapped[list[SLOEvaluation]] = relationship('SLOEvaluation', back_populates='evaluation_run', cascade='all, delete-orphan')
    annotations:     Mapped[list[EvaluationAnnotation]] = relationship('EvaluationAnnotation', back_populates='evaluation_run', cascade='all, delete-orphan')
    # fmt: on
