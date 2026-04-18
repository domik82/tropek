"""Tests for asset meta ingest schema validation rules (§5.2)."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from tropek.modules.asset_meta.schemas import MetaClosureInput, MetaSnapshotCreate, MetaValueInput

# ---------------------------------------------------------------------------
# source validation
# ---------------------------------------------------------------------------


class TestSourceValidation:
    def test_valid_source_accepted(self) -> None:
        snapshot = MetaSnapshotCreate(
            source='cicd',
            observed_at=datetime(2026, 1, 1, tzinfo=UTC),
            values=[MetaValueInput(path=['app'], value='1.0')],
        )
        assert snapshot.source == 'cicd'

    def test_empty_source_rejected(self) -> None:
        with pytest.raises(ValidationError, match='source'):
            MetaSnapshotCreate(
                source='',
                observed_at=datetime(2026, 1, 1, tzinfo=UTC),
            )

    def test_source_exceeding_64_chars_rejected(self) -> None:
        with pytest.raises(ValidationError, match='source'):
            MetaSnapshotCreate(
                source='a' * 65,
                observed_at=datetime(2026, 1, 1, tzinfo=UTC),
            )

    def test_source_with_space_rejected(self) -> None:
        with pytest.raises(ValidationError, match='source'):
            MetaSnapshotCreate(
                source='has space',
                observed_at=datetime(2026, 1, 1, tzinfo=UTC),
            )

    def test_source_with_exclamation_rejected(self) -> None:
        with pytest.raises(ValidationError, match='source'):
            MetaSnapshotCreate(
                source='bad!',
                observed_at=datetime(2026, 1, 1, tzinfo=UTC),
            )

    def test_source_with_dots_dashes_underscores_accepted(self) -> None:
        snapshot = MetaSnapshotCreate(
            source='my.source_name-1',
            observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert snapshot.source == 'my.source_name-1'


# ---------------------------------------------------------------------------
# observed_at validation
# ---------------------------------------------------------------------------


class TestObservedAtValidation:
    def test_timezone_aware_datetime_accepted(self) -> None:
        snapshot = MetaSnapshotCreate(
            source='cicd',
            observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert snapshot.observed_at.tzinfo is not None

    def test_naive_datetime_rejected(self) -> None:
        naive_datetime = datetime.fromisoformat('2026-01-01T00:00:00')
        with pytest.raises(ValidationError, match='observed_at'):
            MetaSnapshotCreate(
                source='cicd',
                observed_at=naive_datetime,
            )


# ---------------------------------------------------------------------------
# values[].path validation
# ---------------------------------------------------------------------------


class TestValuesPathValidation:
    def test_empty_path_rejected(self) -> None:
        with pytest.raises(ValidationError, match='path'):
            MetaValueInput(path=[], value='1.0')

    def test_seven_entry_path_rejected(self) -> None:
        with pytest.raises(ValidationError, match='path'):
            MetaValueInput(path=['a', 'b', 'c', 'd', 'e', 'f', 'g'], value='1.0')

    def test_empty_string_entry_rejected(self) -> None:
        with pytest.raises(ValidationError, match='at least 1 character'):
            MetaValueInput(path=[''], value='1.0')

    def test_entry_exceeding_128_chars_rejected(self) -> None:
        with pytest.raises(ValidationError, match='at most 128 characters'):
            MetaValueInput(path=['x' * 129], value='1.0')

    def test_valid_six_entry_path_accepted(self) -> None:
        meta_value = MetaValueInput(
            path=['a', 'b', 'c', 'd', 'e', 'f'],
            value='1.0',
        )
        assert len(meta_value.path) == 6


# ---------------------------------------------------------------------------
# values[].value validation
# ---------------------------------------------------------------------------


class TestValuesValueValidation:
    def test_empty_string_accepted(self) -> None:
        meta_value = MetaValueInput(path=['app'], value='')
        assert meta_value.value == ''

    def test_value_exceeding_1024_chars_rejected(self) -> None:
        with pytest.raises(ValidationError, match='value'):
            MetaValueInput(path=['app'], value='x' * 1025)


# ---------------------------------------------------------------------------
# closed[].path validation
# ---------------------------------------------------------------------------


class TestClosedPathValidation:
    def test_empty_path_rejected(self) -> None:
        with pytest.raises(ValidationError, match='path'):
            MetaClosureInput(path=[])

    def test_seven_entry_path_rejected(self) -> None:
        with pytest.raises(ValidationError, match='path'):
            MetaClosureInput(path=['a', 'b', 'c', 'd', 'e', 'f', 'g'])

    def test_empty_string_entry_rejected(self) -> None:
        with pytest.raises(ValidationError, match='at least 1 character'):
            MetaClosureInput(path=[''])

    def test_entry_exceeding_128_chars_rejected(self) -> None:
        with pytest.raises(ValidationError, match='at most 128 characters'):
            MetaClosureInput(path=['x' * 129])

    def test_valid_path_accepted(self) -> None:
        closure = MetaClosureInput(path=['env', 'version'])
        assert closure.path == ['env', 'version']


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------


class TestStructuralValidation:
    def test_duplicate_path_in_values_rejected(self) -> None:
        with pytest.raises(ValidationError, match='duplicate path in values'):
            MetaSnapshotCreate(
                source='cicd',
                observed_at=datetime(2026, 1, 1, tzinfo=UTC),
                values=[
                    MetaValueInput(path=['app'], value='1.0'),
                    MetaValueInput(path=['app'], value='2.0'),
                ],
            )

    def test_duplicate_path_in_closed_rejected(self) -> None:
        with pytest.raises(ValidationError, match='duplicate path in closed'):
            MetaSnapshotCreate(
                source='cicd',
                observed_at=datetime(2026, 1, 1, tzinfo=UTC),
                closed=[
                    MetaClosureInput(path=['app']),
                    MetaClosureInput(path=['app']),
                ],
            )

    def test_same_path_in_values_and_closed_accepted(self) -> None:
        """Close-and-reopen: same path appearing in both values and closed is valid."""
        snapshot = MetaSnapshotCreate(
            source='cicd',
            observed_at=datetime(2026, 1, 1, tzinfo=UTC),
            values=[MetaValueInput(path=['app'], value='2.0')],
            closed=[MetaClosureInput(path=['app'])],
        )
        assert len(snapshot.values) == 1
        assert len(snapshot.closed) == 1

    def test_empty_values_and_closed_accepted_by_pydantic(self) -> None:
        """Both lists empty is valid at the schema level.

        The service layer rejects this as a no-op (tested in test_service.py).
        """
        snapshot = MetaSnapshotCreate(
            source='cicd',
            observed_at=datetime(2026, 1, 1, tzinfo=UTC),
            values=[],
            closed=[],
        )
        assert snapshot.values == []
        assert snapshot.closed == []

    def test_unknown_field_rejected(self) -> None:
        """StrictInput sets extra='forbid' — unknown fields must be rejected."""
        with pytest.raises(ValidationError, match='extra_forbidden'):
            MetaSnapshotCreate(
                source='cicd',
                observed_at=datetime(2026, 1, 1, tzinfo=UTC),
                surprise='unexpected',
            )
