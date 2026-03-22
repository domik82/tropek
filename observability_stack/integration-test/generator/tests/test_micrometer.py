"""Tests for MicrometerApp cumulative accumulation."""

from __future__ import annotations

from datetime import UTC, datetime

from slo_generator.micrometer import MicrometerApp
from slo_generator.raw import RawSample


def _make_sample(
    ts_offset: int = 0,
    request_count: int = 10,
    latencies_ms: list[float] | None = None,
    error_count: int = 0,
) -> RawSample:
    base = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
    lats = latencies_ms if latencies_ms is not None else [20.0] * request_count
    return RawSample(
        timestamp=base,
        service="api",
        host="host1",
        request_count=request_count,
        error_count=error_count,
        latencies_ms=lats,
        cpu_percent=40.0,
        memory_bytes=512 * 1024 * 1024,
    )


class TestCounterAccumulation:
    def test_counter_equals_total_requests(self):
        app = MicrometerApp()
        app.record_second(_make_sample(request_count=10))
        app.record_second(_make_sample(request_count=20))
        app.record_second(_make_sample(request_count=30))

        snap = app.scrape(1000.0)
        assert snap.request_counter == 60

    def test_error_counter_accumulates(self):
        app = MicrometerApp()
        app.record_second(_make_sample(request_count=10, error_count=2))
        app.record_second(_make_sample(request_count=10, error_count=3))

        snap = app.scrape(1000.0)
        assert snap.error_counter == 5

    def test_count_equals_total_latencies(self):
        app = MicrometerApp()
        app.record_second(_make_sample(request_count=10))
        app.record_second(_make_sample(request_count=20))

        snap = app.scrape(1000.0)
        assert snap.count == 30


class TestHistogramBuckets:
    def test_buckets_are_cumulative(self):
        app = MicrometerApp()
        app.record_second(_make_sample(request_count=100, latencies_ms=[15.0] * 100))

        snap = app.scrape(1000.0)
        # Each bucket count should be >= the previous (cumulative)
        for i in range(1, len(snap.bucket_counts)):
            assert snap.bucket_counts[i] >= snap.bucket_counts[i - 1], (
                f"bucket[{i}] ({snap.bucket_counts[i]}) < bucket[{i - 1}] ({snap.bucket_counts[i - 1]})"
            )

    def test_inf_bucket_equals_total_count(self):
        app = MicrometerApp()
        app.record_second(_make_sample(request_count=50))
        app.record_second(_make_sample(request_count=30))

        snap = app.scrape(1000.0)
        assert snap.bucket_counts[-1] == 80  # +Inf = total

    def test_bucket_placement_15ms(self):
        """15ms latency should land in le=15 bucket but not le=10."""
        app = MicrometerApp()
        app.record_second(_make_sample(request_count=1, latencies_ms=[15.0]))

        snap = app.scrape(1000.0)
        buckets = dict(zip(snap.buckets_ms, snap.bucket_counts, strict=False))

        # 15.0 should be in le=15 (exact match)
        assert buckets[15.0] == 1
        # 15.0 should NOT be in le=10
        assert buckets[10.0] == 0

    def test_bucket_placement_25ms(self):
        """25ms latency: in le=25 and above, not in le=20."""
        app = MicrometerApp()
        app.record_second(_make_sample(request_count=1, latencies_ms=[25.0]))

        snap = app.scrape(1000.0)
        buckets = dict(zip(snap.buckets_ms, snap.bucket_counts, strict=False))

        assert buckets[25.0] == 1
        assert buckets[20.0] == 0
        assert buckets[30.0] == 1  # cumulative
        assert buckets[float("inf")] == 1


class TestSumAccumulation:
    def test_sum_equals_total_latency(self):
        app = MicrometerApp()
        app.record_second(_make_sample(request_count=3, latencies_ms=[10.0, 20.0, 30.0]))
        app.record_second(_make_sample(request_count=2, latencies_ms=[5.0, 15.0]))

        snap = app.scrape(1000.0)
        assert snap.sum_ms == 80.0  # 10+20+30+5+15


class TestScrapeReadonly:
    def test_scrape_is_readonly(self):
        app = MicrometerApp()
        app.record_second(_make_sample(request_count=10))

        snap1 = app.scrape(1000.0)
        snap2 = app.scrape(1000.0)

        assert snap1.request_counter == snap2.request_counter
        assert snap1.sum_ms == snap2.sum_ms
        assert snap1.bucket_counts == snap2.bucket_counts

    def test_scrape_returns_copy_of_buckets(self):
        app = MicrometerApp()
        app.record_second(_make_sample(request_count=5))

        snap = app.scrape(1000.0)
        snap.bucket_counts[0] = 999  # mutate the snapshot

        snap2 = app.scrape(1000.0)
        assert snap2.bucket_counts[0] != 999  # original unchanged


class TestGauges:
    def test_cpu_and_memory_from_last_sample(self):
        app = MicrometerApp()
        app.record_second(
            RawSample(
                timestamp=datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC),
                service="api",
                host="host1",
                request_count=10,
                error_count=0,
                latencies_ms=[20.0] * 10,
                cpu_percent=75.5,
                memory_bytes=1024 * 1024 * 1024,
            )
        )

        snap = app.scrape(1000.0)
        assert snap.cpu_percent == 75.5
        assert snap.memory_bytes == 1024 * 1024 * 1024


class TestCustomBuckets:
    def test_custom_bucket_boundaries(self):
        app = MicrometerApp(buckets_ms=[10.0, 50.0, 100.0])
        app.record_second(_make_sample(request_count=1, latencies_ms=[25.0]))

        snap = app.scrape(1000.0)
        # Should have [10, 50, 100, +Inf]
        assert len(snap.buckets_ms) == 4
        assert snap.buckets_ms[-1] == float("inf")

        buckets = dict(zip(snap.buckets_ms, snap.bucket_counts, strict=False))
        assert buckets[10.0] == 0  # 25 > 10
        assert buckets[50.0] == 1  # 25 <= 50
        assert buckets[100.0] == 1  # cumulative
        assert buckets[float("inf")] == 1
