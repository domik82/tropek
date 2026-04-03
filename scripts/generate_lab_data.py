"""Generate 90-day walking diagonal CSV data for the lab-monitor scale test.

Each day produces one evaluation window (30 min). For 8 SLI metrics across
24 SLOs (3 templates x 8 processes), the fail/warn pattern walks diagonally
across SLI rows so every heatmap column has a unique fingerprint.

Pattern per 11-day cycle:
  Days 0-4: all pass
  Day 5: one SLI fails (walks to next SLI each cycle)
  Days 6-9: all pass
  Day 10: one SLI warns (offset +4 from fail SLI)

Output: adapters/mock/data/prometheus-local/lab-metrics.csv
Usage: uv run python scripts/generate_lab_data.py
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 8 metrics matching lab-process-sli indicators
METRICS = [
    ('cpu_pct', 30.0, 95.0, 70.0),        # (name, pass_val, fail_val, warn_val)
    ('memory_mb', 200.0, 900.0, 700.0),
    ('handles', 150.0, 900.0, 700.0),
    ('io_bytes_sec', 300000.0, 1800000.0, 1400000.0),
    ('threads', 80.0, 350.0, 280.0),
    ('gc_pause_ms', 20.0, 90.0, 70.0),
    ('heap_mb', 100.0, 450.0, 360.0),
    ('open_files', 40.0, 180.0, 140.0),
]

NUM_DAYS = 90
CYCLE_LEN = 11
FAIL_DAY = 5
WARN_DAY = 10
NUM_SLIS = len(METRICS)

# Start date: 90 days before 2026-03-15 (existing data start)
# so the lab data covers 2025-12-16 to 2026-03-15
START = datetime(2025, 12, 16, tzinfo=timezone.utc)
WINDOW_MINUTES = 30
INTERVAL_MINUTES = 5


def compute_value(day: int, sli_idx: int) -> tuple[str, float]:
    """Return (metric_name, value) for a given day and SLI index."""
    name, pass_val, fail_val, warn_val = METRICS[sli_idx]
    cycle_day = day % CYCLE_LEN
    fail_sli = (day // CYCLE_LEN) % NUM_SLIS
    warn_sli = ((day // CYCLE_LEN) + 4) % NUM_SLIS

    if cycle_day == FAIL_DAY and sli_idx == fail_sli:
        return name, fail_val
    if cycle_day == WARN_DAY and sli_idx == warn_sli:
        return name, warn_val
    return name, pass_val


def main() -> None:
    """Generate lab-metrics.csv with 90 days of walking diagonal data."""
    output_dir = Path('adapters/mock/data/prometheus-local')
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / 'lab-metrics.csv'

    rows: list[dict[str, str]] = []

    for day in range(NUM_DAYS):
        window_start = START + timedelta(days=day, hours=12)  # noon each day
        t = window_start

        while t < window_start + timedelta(minutes=WINDOW_MINUTES):
            for sli_idx in range(NUM_SLIS):
                metric_name, value = compute_value(day, sli_idx)
                rows.append({
                    'timestamp': t.isoformat(),
                    'metric_name': metric_name,
                    'value': f'{value:.6f}',
                })
            t += timedelta(minutes=INTERVAL_MINUTES)

    rows.sort(key=lambda r: (r['timestamp'], r['metric_name']))

    with csv_path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['timestamp', 'metric_name', 'value'])
        writer.writeheader()
        writer.writerows(rows)

    print(f'generated {csv_path} ({len(rows)} rows, {NUM_DAYS} days)')


if __name__ == '__main__':
    main()
