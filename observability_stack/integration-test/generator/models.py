"""Core data models for the SLO test data generator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class MetricType(StrEnum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass(frozen=True)
class Sample:
    """A single timestamped metric observation."""

    timestamp: datetime
    value: float
    labels: dict[str, str] = field(default_factory=dict, hash=False)

    def with_labels(self, **extra: str) -> Sample:
        return Sample(
            timestamp=self.timestamp,
            value=self.value,
            labels={**self.labels, **extra},
        )


@dataclass
class MetricFamily:
    """A named metric with type and help text, carrying a stream of samples."""

    name: str
    metric_type: MetricType
    help_text: str
    samples: list[Sample] = field(default_factory=list)

    def add(self, sample: Sample) -> None:
        self.samples.append(sample)

    def __len__(self) -> int:
        return len(self.samples)


@dataclass
class ScenarioWindow:
    """Time window definition for a scenario."""

    start: datetime
    end: datetime
    label: str  # e.g. "healthy", "outage", "degradation"


# ── Histogram helpers ─────────────────────────────────────────────────────

# Standard Prometheus histogram buckets for request durations (seconds)
DURATION_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]


def make_histogram_samples(
    timestamp: datetime,
    labels: dict[str, str],
    p50: float,
    p99: float,
    count: float,
) -> list[Sample]:
    """Generate histogram bucket, sum, and count samples for a given timestamp.

    Uses a simplified two-point distribution model:
    - ~50% of requests finish by p50
    - ~99% finish by p99
    - remaining ~1% are slow outliers

    Returns: bucket samples (one per le), _sum sample, _count sample
    """
    samples = []
    cumulative = 0.0

    for bucket in DURATION_BUCKETS:
        if bucket <= p50 * 0.5:
            # Very fast requests — small fraction
            frac = 0.1
        elif bucket <= p50:
            frac = 0.5
        elif bucket <= p99 * 0.7:
            frac = 0.80
        elif bucket <= p99:
            frac = 0.99
        elif bucket <= p99 * 2:
            frac = 0.999
        else:
            frac = 0.9999

        cumulative = count * frac
        samples.append(
            Sample(
                timestamp=timestamp,
                value=cumulative,
                labels={**labels, "le": str(bucket)},
            )
        )

    # +Inf bucket = total count
    samples.append(
        Sample(
            timestamp=timestamp,
            value=count,
            labels={**labels, "le": "+Inf"},
        )
    )

    # _sum ≈ average latency * count (use geometric mean of p50 and p99)
    avg_latency = (p50 + p99) / 2
    samples.append(Sample(timestamp=timestamp, value=avg_latency * count, labels=labels))

    # _count
    samples.append(Sample(timestamp=timestamp, value=count, labels=labels))

    return samples
