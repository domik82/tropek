#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Starting stack..."
docker compose -f "$DIR/docker-compose.yml" "$@" up --build -d

echo ""
echo "==> Waiting for generator to finish..."
docker compose -f "$DIR/docker-compose.yml" "$@" logs -f generator 2>&1

echo ""
echo "==> Stack is up!"
echo "  Grafana:      http://localhost:3100  (admin / admin)"
echo "  Prometheus:   http://localhost:9090"
echo "  InfluxDB:     http://localhost:8086  (admin / adminpassword)"
echo "  TimescaleDB:  localhost:5534"
echo ""
echo "NOTE: Data is at fixed dates from the timeline YAML."
echo "      In Grafana, set the time range to match (e.g. 2026-03-14 to 2026-03-21)."
