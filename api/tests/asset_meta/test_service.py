"""Unit tests for asset meta snapshot service layer using a fake repository."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from tropek.modules.asset_meta.schemas import (
    MetaClosureInput,
    MetaSnapshotCreate,
    MetaValueInput,
    TimelineResponse,
    TimelineSummaryResponse,
)
from tropek.modules.asset_meta.service import (
    _ensure_asset_exists,
    _validate_payload_has_content,
    _write_snapshot_rows,
    get_timeline,
    get_timeline_summary,
)
from tropek.modules.common.exceptions import DomainValidationError, NotFoundError


@dataclass
class FakeSnapshot:
    """In-memory snapshot record returned by the fake repository."""

    id: uuid.UUID
    asset_id: uuid.UUID
    source: str
    observed_at: datetime


@dataclass
class FakeRepository:
    """Records method calls for assertion instead of hitting a real database."""

    existing_assets: set[uuid.UUID] = field(default_factory=set)
    inserted_snapshots: list[FakeSnapshot] = field(default_factory=list)
    inserted_values: list[tuple[uuid.UUID, list]] = field(default_factory=list)
    inserted_closures: list[tuple[uuid.UUID, list]] = field(default_factory=list)

    async def asset_exists(self, asset_id: uuid.UUID) -> bool:
        return asset_id in self.existing_assets

    async def insert_snapshot(
        self,
        asset_id: uuid.UUID,
        source: str,
        observed_at: datetime,
    ) -> FakeSnapshot:
        snapshot = FakeSnapshot(
            id=uuid.uuid4(),
            asset_id=asset_id,
            source=source,
            observed_at=observed_at,
        )
        self.inserted_snapshots.append(snapshot)
        return snapshot

    async def insert_values(self, snapshot_id: uuid.UUID, entries: list) -> None:
        self.inserted_values.append((snapshot_id, list(entries)))

    async def insert_closures(self, snapshot_id: uuid.UUID, entries: list) -> None:
        self.inserted_closures.append((snapshot_id, list(entries)))


def _make_payload(
    values: list[MetaValueInput] | None = None,
    closed: list[MetaClosureInput] | None = None,
) -> MetaSnapshotCreate:
    return MetaSnapshotCreate(
        source='cicd',
        observed_at=datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC),
        values=values or [],
        closed=closed or [],
    )


# --- _validate_payload_has_content ---


def test_validate_payload_has_content_rejects_empty() -> None:
    payload = _make_payload()
    with pytest.raises(DomainValidationError, match='snapshot must contain values or closed'):
        _validate_payload_has_content(payload)


def test_validate_payload_has_content_accepts_values_only() -> None:
    payload = _make_payload(values=[MetaValueInput(path=['env'], value='prod')])
    _validate_payload_has_content(payload)


def test_validate_payload_has_content_accepts_closed_only() -> None:
    payload = _make_payload(closed=[MetaClosureInput(path=['env'])])
    _validate_payload_has_content(payload)


def test_validate_payload_has_content_accepts_both() -> None:
    payload = _make_payload(
        values=[MetaValueInput(path=['env'], value='prod')],
        closed=[MetaClosureInput(path=['region'])],
    )
    _validate_payload_has_content(payload)


# --- _ensure_asset_exists ---


async def test_ensure_asset_exists_raises_not_found() -> None:
    repository = FakeRepository()
    missing_id = uuid.uuid4()
    with pytest.raises(NotFoundError, match='asset'):
        await _ensure_asset_exists(repository, missing_id)


async def test_ensure_asset_exists_silent_when_present() -> None:
    asset_id = uuid.uuid4()
    repository = FakeRepository(existing_assets={asset_id})
    result = await _ensure_asset_exists(repository, asset_id)
    assert result is None


# --- _write_snapshot_rows ---


async def test_write_snapshot_rows_values_only() -> None:
    repository = FakeRepository()
    asset_id = uuid.uuid4()
    payload = _make_payload(values=[MetaValueInput(path=['env'], value='prod')])

    snapshot_id = await _write_snapshot_rows(repository, asset_id, payload)

    assert len(repository.inserted_snapshots) == 1
    assert repository.inserted_snapshots[0].asset_id == asset_id
    assert repository.inserted_snapshots[0].source == 'cicd'
    assert repository.inserted_snapshots[0].id == snapshot_id

    assert len(repository.inserted_values) == 1
    recorded_snapshot_id, recorded_entries = repository.inserted_values[0]
    assert recorded_snapshot_id == snapshot_id
    assert recorded_entries == [(['env'], 'prod')]

    assert len(repository.inserted_closures) == 0


async def test_write_snapshot_rows_closed_only() -> None:
    repository = FakeRepository()
    asset_id = uuid.uuid4()
    payload = _make_payload(closed=[MetaClosureInput(path=['env'])])

    snapshot_id = await _write_snapshot_rows(repository, asset_id, payload)

    assert len(repository.inserted_snapshots) == 1
    assert repository.inserted_snapshots[0].id == snapshot_id

    assert len(repository.inserted_values) == 0

    assert len(repository.inserted_closures) == 1
    recorded_snapshot_id, recorded_entries = repository.inserted_closures[0]
    assert recorded_snapshot_id == snapshot_id
    assert recorded_entries == [['env']]


async def test_write_snapshot_rows_both() -> None:
    repository = FakeRepository()
    asset_id = uuid.uuid4()
    payload = _make_payload(
        values=[MetaValueInput(path=['env'], value='prod')],
        closed=[MetaClosureInput(path=['region'])],
    )

    snapshot_id = await _write_snapshot_rows(repository, asset_id, payload)

    assert len(repository.inserted_snapshots) == 1
    assert len(repository.inserted_values) == 1
    assert len(repository.inserted_closures) == 1

    recorded_value_snapshot_id, recorded_value_entries = repository.inserted_values[0]
    assert recorded_value_snapshot_id == snapshot_id
    assert recorded_value_entries == [(['env'], 'prod')]

    recorded_closure_snapshot_id, recorded_closure_entries = repository.inserted_closures[0]
    assert recorded_closure_snapshot_id == snapshot_id
    assert recorded_closure_entries == [['region']]


# --- get_timeline ---

T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = datetime(2026, 1, 2, tzinfo=UTC)


async def test_get_timeline_returns_empty_for_no_snapshots() -> None:
    fake_session = AsyncMock()
    asset_id = uuid.uuid4()
    with patch('tropek.modules.asset_meta.service.AssetMetaRepository') as MockRepo:
        mock_repo = MockRepo.return_value
        mock_repo.asset_exists = AsyncMock(return_value=True)
        mock_repo.load_snapshots_for_derivation = AsyncMock(return_value=[])
        result = await get_timeline(fake_session, asset_id, T0, T1)
    assert isinstance(result, TimelineResponse)
    assert result.groups == []
    assert result.items == []


async def test_get_timeline_raises_not_found_for_missing_asset() -> None:
    fake_session = AsyncMock()
    asset_id = uuid.uuid4()
    with patch('tropek.modules.asset_meta.service.AssetMetaRepository') as MockRepo:
        mock_repo = MockRepo.return_value
        mock_repo.asset_exists = AsyncMock(return_value=False)
        with pytest.raises(NotFoundError, match='asset'):
            await get_timeline(fake_session, asset_id, T0, T1)


# --- get_timeline_summary ---


async def test_get_timeline_summary_returns_zero_for_empty_asset() -> None:
    fake_session = AsyncMock()
    asset_id = uuid.uuid4()
    with patch('tropek.modules.asset_meta.service.AssetMetaRepository') as MockRepo:
        mock_repo = MockRepo.return_value
        mock_repo.asset_exists = AsyncMock(return_value=True)
        mock_repo.load_snapshots_for_derivation = AsyncMock(return_value=[])
        result = await get_timeline_summary(fake_session, asset_id, T0, T1)
    assert isinstance(result, TimelineSummaryResponse)
    assert result.item_count == 0


async def test_get_timeline_summary_raises_not_found_for_missing_asset() -> None:
    fake_session = AsyncMock()
    asset_id = uuid.uuid4()
    with patch('tropek.modules.asset_meta.service.AssetMetaRepository') as MockRepo:
        mock_repo = MockRepo.return_value
        mock_repo.asset_exists = AsyncMock(return_value=False)
        with pytest.raises(NotFoundError, match='asset'):
            await get_timeline_summary(fake_session, asset_id, T0, T1)
