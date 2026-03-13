"""SQLAlchemy ORM declarative models for all Phase 1 entities."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


class Asset(Base):
    """A named entity under test — VM, service, container, or endpoint."""

    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    tags: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SLODefinition(Base):
    """Versioned SLO definition — rows are immutable after insert."""

    __tablename__ = "slo_definitions"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_slo_name_version"),
        Index("idx_slo_definitions_name", "name"),
        Index("idx_slo_definitions_latest", "name", "version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    slo_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Evaluation(Base):
    """One evaluation run — triggered, executed, stored."""

    __tablename__ = "evaluations"
    __table_args__ = (
        Index("idx_evaluations_name", "name"),
        Index("idx_evaluations_asset", "asset_id"),
        Index("idx_evaluations_result", "result"),
        Index("idx_evaluations_start", "start_time"),
        Index("idx_evaluations_status", "status"),
        Index("idx_evaluations_slo", "slo_name", "slo_version"),
        # Partial index for watchdog: find stuck running jobs efficiently
        Index(
            "idx_evaluations_stuck",
            "status",
            "started_at",
            postgresql_where="status = 'running'",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), nullable=True
    )
    asset_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)  # null while pending
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    slo_yaml: Mapped[str | None] = mapped_column(Text, nullable=True)
    slo_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    slo_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    indicator_results: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    # Column named 'metadata' in DB; metadata_ avoids conflict with SQLAlchemy internals
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    ingestion_mode: Mapped[str] = mapped_column(Text, nullable=False)  # pull | push | file
    adapter_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    invalidated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    invalidation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Job lifecycle
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    job_stats: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    annotations: Mapped[list[EvaluationAnnotation]] = relationship(
        "EvaluationAnnotation", back_populates="evaluation", cascade="all, delete-orphan"
    )


class EvaluationAnnotation(Base):
    """Append-only contextual note on an evaluation."""

    __tablename__ = "evaluation_annotations"
    __table_args__ = (Index("idx_annotations_evaluation", "evaluation_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluations.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    evaluation: Mapped[Evaluation] = relationship("Evaluation", back_populates="annotations")


class SLIValue(Base):
    """TimescaleDB hypertable — one aggregated metric value per evaluation.

    Partitioned by eval_start for efficient time-range queries in Grafana.
    Composite PK required: TimescaleDB needs the partition key in the PK.
    Denormalised columns (asset_name, test_name, os_tag) avoid joins in Grafana SQL.
    """

    __tablename__ = "sli_values"
    __table_args__ = (Index("idx_sli_values_lookup", "test_name", "metric_name", "eval_start"),)

    eval_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluations.id"), nullable=False, primary_key=True
    )
    eval_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, primary_key=True
    )
    metric_name: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    aggregation: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    asset_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    os_tag: Mapped[str | None] = mapped_column(Text, nullable=True)
