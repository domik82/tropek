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


class Asset(Base):
    """A named entity under test — VM, service, container, or endpoint."""

    __tablename__ = "assets"

    # fmt: off

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    tags: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

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
        Index("idx_evaluations_start", "start_time"),
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
    # TODO evaluation_start_time / end_time | evaluation_period?
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)  # null while pending
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # TODO why we would keep the yaml? maybe only link to ID if history is preserved
    slo_yaml: Mapped[str | None] = mapped_column(Text, nullable=True)
    slo_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    slo_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    indicator_results: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'"), default=list)
    evaluation_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"), default=dict)
    ingestion_mode: Mapped[str] = mapped_column(Text, nullable=False)
    adapter_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    invalidated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false(), default=False)
    invalidation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Job lifecycle
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"), default="pending")
    # TODO a bit confusing evaluation_start_time and started_at - migt get wrongly used
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
    # TODO: updated_at
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
