"""Tests for RawSample, latency generation, jitter, and error generation."""

from __future__ import annotations

import numpy as np
import pytest
from slo_generator.raw import apply_jitter, generate_errors, generate_latencies


class TestGenerateLatencies:
    def test_count_matches(self) -> None:
        rng = np.random.default_rng(42)
        result = generate_latencies(50, base_ms=20.0, sigma=0.4, rng=rng)
        assert len(result) == 50

    def test_zero_count_returns_empty(self) -> None:
        rng = np.random.default_rng(42)
        assert generate_latencies(0, base_ms=20.0, sigma=0.4, rng=rng) == []

    def test_deterministic_with_same_seed(self) -> None:
        rng1 = np.random.default_rng(42)
        rng2 = np.random.default_rng(42)
        r1 = generate_latencies(30, base_ms=20.0, sigma=0.4, rng=rng1)
        r2 = generate_latencies(30, base_ms=20.0, sigma=0.4, rng=rng2)
        assert r1 == r2

    def test_distribution_median_near_base(self) -> None:
        rng = np.random.default_rng(42)
        result = generate_latencies(10_000, base_ms=20.0, sigma=0.4, rng=rng)
        median = float(np.median(result))
        assert 16.0 < median < 24.0, f"median {median} not near base_ms 20.0"

    def test_all_values_positive(self) -> None:
        rng = np.random.default_rng(42)
        result = generate_latencies(100, base_ms=5.0, sigma=0.8, rng=rng)
        assert all(v > 0 for v in result)


class TestApplyJitter:
    def test_zero_jitter_returns_exact(self) -> None:
        rng = np.random.default_rng(42)
        assert apply_jitter(100.0, 0.0, rng) == 100.0

    def test_jitter_within_bounds(self) -> None:
        rng = np.random.default_rng(42)
        base = 100.0
        pct = 0.05
        results = [apply_jitter(base, pct, rng) for _ in range(1000)]
        assert all(base * (1 - pct) <= v <= base * (1 + pct) for v in results)

    def test_jitter_changes_value(self) -> None:
        rng = np.random.default_rng(42)
        results = {apply_jitter(100.0, 0.1, rng) for _ in range(10)}
        assert len(results) > 1, "jitter should produce varying values"


class TestGenerateErrors:
    def test_zero_rate_returns_zero(self) -> None:
        rng = np.random.default_rng(42)
        assert generate_errors(100, 0.0, rng) == 0

    def test_full_rate_returns_all(self) -> None:
        rng = np.random.default_rng(42)
        assert generate_errors(100, 1.0, rng) == 100

    def test_zero_requests_returns_zero(self) -> None:
        rng = np.random.default_rng(42)
        assert generate_errors(0, 0.5, rng) == 0

    @pytest.mark.parametrize("error_rate", [0.01, 0.5, 0.9])
    def test_high_rate_produces_proportional_errors(self, error_rate: float) -> None:
        rng = np.random.default_rng(42)
        total = 10_000
        errors = generate_errors(total, error_rate, rng)
        expected = total * error_rate
        assert abs(errors - expected) / expected < 0.1, f"errors={errors}, expected≈{expected}"

    def test_deterministic_with_same_seed(self) -> None:
        r1 = generate_errors(100, 0.1, np.random.default_rng(42))
        r2 = generate_errors(100, 0.1, np.random.default_rng(42))
        assert r1 == r2
