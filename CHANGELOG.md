# Changelog

All notable changes to TROPEK are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Core evaluation engine** — pure-function SLO evaluation ported from Keptn lighthouse-service
  - SLO YAML parsing with embedded SLI queries (superset of Keptn 1.0 format)
  - Fixed threshold (`<600`), relative percent (`<=+10%`), and relative absolute (`<=+50`) criteria
  - Configurable baseline comparison (previous, pinned, or aggregate)
  - Per-objective scoring with pass/warning/fail and total score calculation
- **Async evaluation pipeline** — FastAPI + arq (Redis) job queue
  - POST to trigger, worker dequeues and evaluates, results to TimescaleDB
  - Re-evaluation support for updated SLOs against historical data
- **Prometheus adapter** — standalone query adapter with SLI template variable substitution
- **Change point detection** — E-Divisive algorithm (vendored from Apache Otava)
  - Per-metric configurable parameters (window size, p-value, min magnitude)
  - Automatic regression/improvement classification
- **SLO registry** — versioned SLO definitions with CRUD, validation, and dry-run test endpoint
- **SLI registry** — reusable SLI definitions with tagging
- **Asset management** — hierarchical project/service grouping with metadata timeline
- **Navigator UI** — React SPA with heatmap visualization, evaluation detail, and SLO management
  - Three-theme system (dark, alt, light)
  - Evaluation actions (invalidate, pin baseline, add notes)
  - Trend charts and SLI breakdown tables
- **Docker Compose deployment** — single-command setup with TimescaleDB, Redis, and all services
- **CI/CD pipeline** — GitHub Actions for lint, typecheck, tests, Docker security scanning, and releases
- **Docker security scanning** — Hadolint (Dockerfile lint) + Trivy (CVE scanning) in CI
