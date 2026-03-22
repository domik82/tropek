"""Generator configuration — bucket boundaries, scrape interval, jitter, error rates."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Micrometer default histogram bucket boundaries (milliseconds).
# Matches PrometheusMeterRegistry.publishPercentileHistogram() defaults.
MICROMETER_BUCKETS_MS: list[float] = [
    1,
    2,
    3,
    5,
    7,
    10,
    15,
    20,
    25,
    30,
    40,
    50,
    60,
    70,
    80,
    90,
    100,
    150,
    200,
    250,
    300,
    400,
    500,
    750,
    1000,
    1500,
    2000,
    5000,
]


def _parse_seconds(s: str) -> int:
    """Parse a duration string like '15s', '5m' into total seconds."""
    match = re.fullmatch(r"(\d+)\s*([sm])", s.strip())
    if not match:
        raise ValueError(f"invalid duration: {s!r}")
    value = int(match.group(1))
    unit = match.group(2)
    return value * 60 if unit == "m" else value


@dataclass
class GeneratorConfig:
    """Configuration for the raw data generator pipeline."""

    histogram_buckets_ms: list[float] = field(default_factory=lambda: list(MICROMETER_BUCKETS_MS))
    scrape_interval_s: int = 15
    jitter_pct: float = 0.0
    base_error_rate: float = 0.01
    latency_sigma: float = 0.4
    seed: int = 42

    @classmethod
    def default(cls) -> GeneratorConfig:
        """Return a config with all defaults (deterministic, no jitter)."""
        return cls()

    @classmethod
    def from_yaml(cls, path: Path | str) -> GeneratorConfig:
        """Load config from a YAML file."""
        with open(path) as f:
            raw = yaml.safe_load(f)

        gen = raw.get("generator", {})

        scrape_interval_s = cls.__dataclass_fields__["scrape_interval_s"].default
        if "scrape_interval" in gen:
            scrape_interval_s = _parse_seconds(str(gen["scrape_interval"]))

        return cls(
            histogram_buckets_ms=gen.get("histogram_buckets_ms", list(MICROMETER_BUCKETS_MS)),
            scrape_interval_s=scrape_interval_s,
            jitter_pct=float(gen.get("jitter", 0.0)),
            base_error_rate=float(gen.get("base_error_rate", 0.01)),
            latency_sigma=float(gen.get("latency_sigma", 0.4)),
            seed=int(gen.get("seed", 42)),
        )

    @property
    def histogram_buckets_seconds(self) -> list[float]:
        """Bucket boundaries converted to seconds (for Prometheus)."""
        return [b / 1000.0 for b in self.histogram_buckets_ms]
