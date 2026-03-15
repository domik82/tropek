"""SQLAlchemy ORM declarative models for all Phase 1 entities."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    UUID,
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

    __tablename__ = "asset_types"
    __table_args__ = (
        Index("idx_asset_types_name", "name"),
        # Enforces at most one default at the DB level
        Index(
            "uq_asset_types_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
    )

    # fmt: off
    id:         Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name:       Mapped[str]       = mapped_column(Text, unique=True, nullable=False)
    is_default: Mapped[bool]      = mapped_column(Boolean, nullable=False, server_default=false(), default=False)
    # fmt: on


class Asset(Base):
    """A named entity under test — VM, service, container, or endpoint."""

    __tablename__ = "assets"

    # fmt: off
    id:           Mapped[uuid.UUID]      = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name:         Mapped[str]            = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str | None]     = mapped_column(Text, nullable=True)
    type_name:    Mapped[str]            = mapped_column(Text, ForeignKey("asset_types.name"), nullable=False, default="vm")
    labels:       Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    created_at:   Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at:   Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    # fmt: on


class AssetGroup(Base):
    """Named container of assets or other groups.

    Supports flat groups (linux_boxes = [vm-01, vm-02]) and
    group-of-groups (software_xyz = [linux_boxes, windows_vms]).
    """

    __tablename__ = "asset_groups"

    # fmt: off

    id:           Mapped[uuid.UUID]  = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name:         Mapped[str]        = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    description:  Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at:   Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at:   Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # fmt: on


class AssetGroupMember(Base):
    """Associates individual assets with an asset group, with optional weight."""

    __tablename__ = "asset_group_members"
    __table_args__ = (
        Index("idx_asset_group_members_group", "group_id"),
        Index("idx_asset_group_members_asset", "asset_id"),
    )

    # fmt: off

    group_id:  Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("asset_groups.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    asset_id:  Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    weight:    Mapped[float]     = mapped_column(Float, nullable=False, default=1.0)

    # fmt: on


class AssetGroupLink(Base):
    """Links a child group inside a parent group (group-of-groups)."""

    __tablename__ = "asset_group_links"
    __table_args__ = (Index("idx_asset_group_links_parent", "parent_group_id"),)

    # fmt: off

    parent_group_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("asset_groups.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    child_group_id:  Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("asset_groups.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    weight:          Mapped[float]     = mapped_column(Float, nullable=False, default=1.0)

    # fmt: on


class DataSource(Base):
    """Named pointer to a running adapter service instance.

    The adapter manages its own connection credentials via env vars.
    TROPEK stores only where to send queries (adapter_url) and free-form
    labels for discovery. Names are unique across the deployment.
    """

    __tablename__ = "data_sources"
    __table_args__ = (Index("idx_data_sources_name", "name"),)

    # fmt: off

    id:           Mapped[uuid.UUID]        = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name:         Mapped[str]              = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str | None]       = mapped_column(Text, nullable=True)
    adapter_type: Mapped[str]              = mapped_column(Text, nullable=False)
    adapter_url:  Mapped[str]              = mapped_column(Text, nullable=False)
    labels:       Mapped[dict[str, Any]]   = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    created_at:   Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at:   Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # fmt: on


class SLIDefinition(Base):
    """Versioned set of indicator queries for one adapter type.

    Rows are immutable after insert — same versioning pattern as SLODefinition.
    Each indicator maps a name to an adapter-specific query string (PromQL, SQL, etc.).
    Variable tokens ($vm_ip, $period_start, etc.) are substituted at evaluation time.
    """

    __tablename__ = "sli_definitions"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_sli_name_version"),
        Index("idx_sli_definitions_name", "name"),
        Index("idx_sli_definitions_latest", "name", text("version DESC")),
    )

    # fmt: off

    id:           Mapped[uuid.UUID]        = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name:         Mapped[str]              = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None]       = mapped_column(Text, nullable=True)
    version:      Mapped[int]              = mapped_column(Integer, nullable=False)
    indicators:   Mapped[dict[str, Any]]   = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    notes:        Mapped[str | None]       = mapped_column(Text, nullable=True)
    author:       Mapped[str | None]       = mapped_column(Text, nullable=True)
    meta:         Mapped[dict[str, Any]]   = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    active:       Mapped[bool]             = mapped_column(Boolean, nullable=False, server_default=true(), default=True)
    created_at:   Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # fmt: on


class SLODefinition(Base):
    """Versioned SLO definition — rows are immutable after insert."""

    __tablename__ = "slo_definitions"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_slo_name_version"),
        Index("idx_slo_definitions_name", "name"),
        # version DESC so get_latest() queries hit this index efficiently
        Index("idx_slo_definitions_latest", "name", text("version DESC")),
    )

    # fmt: off

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    slo_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true(), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # fmt: on


class Evaluation(Base):
    """One evaluation run — triggered, executed, stored."""

    __tablename__ = "evaluations"
    __table_args__ = (
        Index("idx_evaluations_name", "name"),
        Index("idx_evaluations_asset", "asset_id"),
        Index("idx_evaluations_result", "result"),
        Index("idx_evaluations_start", "period_start"),
        Index("idx_evaluations_status", "status"),
        Index("idx_evaluations_slo", "slo_name", "slo_version"),
        # Partial index for watchdog: find stuck running jobs efficiently
        Index(
            "idx_evaluations_stuck",
            "status",
            "started_at",
            postgresql_where=text("status = 'running'"),
        ),
        CheckConstraint(
            "status IN ('pending','running','completed','failed','partial')",
            name="ck_evaluations_status",
        ),
        CheckConstraint(
            "ingestion_mode IN ('pull','push','file')",
            name="ck_evaluations_ingestion_mode",
        ),
        CheckConstraint(
            "result IN ('pass','warning','fail','error') OR result IS NULL",
            name="ck_evaluations_result",
        ),
    )

    # fmt: off

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey("assets.id"), nullable=True)
    asset_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end:   Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)  # null while pending
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    slo_yaml: Mapped[str | None] = mapped_column(Text, nullable=True)
    slo_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    slo_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sli_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    sli_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_source_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    indicator_results: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'"), default=list)
    evaluation_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    ingestion_mode: Mapped[str] = mapped_column(Text, nullable=False)
    adapter_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    invalidated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false(), default=False)
    invalidation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Job lifecycle
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    job_stats: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    annotations: Mapped[list[EvaluationAnnotation]] = relationship("EvaluationAnnotation", back_populates="evaluation", cascade="all, delete-orphan")

    # fmt: on


class EvaluationAnnotation(Base):
    """Append-only contextual note on an evaluation."""

    __tablename__ = "evaluation_annotations"
    __table_args__ = (Index("idx_annotations_evaluation", "evaluation_id"),)

    # fmt: off

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False, )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
    evaluation: Mapped[Evaluation] = relationship("Evaluation", back_populates="annotations")

    # fmt: on


class SLIValue(Base):
    """TimescaleDB hypertable — one aggregated metric value per evaluation.

    Partitioned by eval_start for efficient time-range queries in Grafana.
    Composite PK required: TimescaleDB needs the partition key in the PK.
    Denormalised columns (asset_name, test_name, os_tag) avoid joins in Grafana SQL.
    No ORM relationship to Evaluation is intentional — prevents accidental lazy-loading
    of potentially thousands of hypertable rows.
    """

    __tablename__ = "sli_values"
    __table_args__ = (Index("idx_sli_values_lookup", "test_name", "metric_name", "eval_start"),)

    # fmt: off
    # TODO : probably to flat stucture - joins should probably be used in Grafana - not convinced this is good

    eval_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("evaluations.id"), nullable=False, primary_key=True)
    eval_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, primary_key=True)
    metric_name: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    aggregation: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    asset_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    os_tag: Mapped[str | None] = mapped_column(Text, nullable=True)

    # fmt: on


class AssetSLOLink(Base):
    """Permanent named binding of an asset to a SLO + SLI + DataSource triple.

    Callers trigger evaluations by group/asset name — the system resolves which
    SLO, SLI, and DataSource to use from these bindings at trigger time.
    SLO, SLI, and DataSource names resolve to their latest active version.
    """

    __tablename__ = "asset_slo_links"
    __table_args__ = (
        Index("idx_asset_slo_links_asset", "asset_id"),
        UniqueConstraint("asset_id", "link_name", name="uq_asset_slo_link_name"),
    )

    # fmt: off

    id:               Mapped[uuid.UUID]  = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    link_name:        Mapped[str]        = mapped_column(Text, nullable=False)
    asset_id:         Mapped[uuid.UUID]  = mapped_column(UUID, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    slo_name:         Mapped[str]        = mapped_column(Text, nullable=False)
    sli_name:         Mapped[str]        = mapped_column(Text, nullable=False)
    data_source_name: Mapped[str]        = mapped_column(Text, nullable=False)
    created_at:       Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # fmt: on


class AssetGroupSLOLink(Base):
    """Same as AssetSLOLink but bound to an asset group instead of a single asset."""

    __tablename__ = "asset_group_slo_links"
    __table_args__ = (
        Index("idx_asset_group_slo_links_group", "group_id"),
        UniqueConstraint("group_id", "link_name", name="uq_asset_group_slo_link_name"),
    )

    # fmt: off

    id:               Mapped[uuid.UUID]  = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    link_name:        Mapped[str]        = mapped_column(Text, nullable=False)
    group_id:         Mapped[uuid.UUID]  = mapped_column(UUID, ForeignKey("asset_groups.id", ondelete="CASCADE"), nullable=False)
    slo_name:         Mapped[str]        = mapped_column(Text, nullable=False)
    sli_name:         Mapped[str]        = mapped_column(Text, nullable=False)
    data_source_name: Mapped[str]        = mapped_column(Text, nullable=False)
    created_at:       Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # fmt: on


class EvaluationBatch(Base):
    """Groups all evaluations spawned by a single trigger call.

    When a group with N bindings across M assets is triggered, one batch is
    created containing up to NxM evaluation IDs. Callers poll batch status
    instead of tracking individual evaluation IDs.
    """

    __tablename__ = "evaluation_batches"
    __table_args__ = (Index("idx_evaluation_batches_status", "status"),)

    # fmt: off

    id:             Mapped[uuid.UUID]        = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    status:         Mapped[str]              = mapped_column(Text, nullable=False, server_default=text("'pending'"), default="pending")
    trigger_params: Mapped[dict[str, Any]]   = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    evaluation_ids: Mapped[list[Any]]        = mapped_column(JSONB, nullable=False, server_default=text("'[]'"), default=list)
    created_at:     Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # fmt: on
