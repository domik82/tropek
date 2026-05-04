# Changelog

All notable changes to TROPEK are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0-alpha] - 2026-05-01

Initial alpha release. TROPEK is a standalone quality gate and performance test
evaluation platform — a Python rewrite of Keptn's lighthouse-service, deployable
via Docker Compose without Kubernetes.

### Core

- **Evaluation engine** — pure-function SLO evaluation ported from Keptn's Go lighthouse-service (zero I/O, fully unit-tested)
  - SLO YAML parsing with embedded SLI queries (superset of Keptn 1.0 format)
  - Fixed threshold (`<600`), relative percent (`<=+10%`), and relative absolute (`<=+50`) criteria
  - Key SLI veto — one critical metric failure fails the entire evaluation regardless of score
  - Configurable baseline comparison (single result, several results with aggregate)
  - Per-objective scoring with pass/warning/fail and weighted total score calculation
- **Async evaluation pipeline** — FastAPI + arq (Redis) job queue with configurable concurrency (max_jobs=10)
  - Adapter-based data ingestion — pull metrics from Prometheus (shipped); custom adapters for other sources can be added
  - Multi-phase worker pipeline: fetch SLIs, evaluate, detect change points, store results
  - Evaluation batches — trigger evaluations for multiple assets in a single request
- **Change point detection** — E-Divisive algorithm (vendored from Apache Otava)
  - Per-metric configurable parameters (window size, p-value, min magnitude)
  - Automatic regression/improvement classification

### Registries & Data Model

- **SLO registry** — versioned SLO definitions with CRUD, validation, and dry-run test endpoint
- **SLI registry** — reusable SLI definitions with tagging
- **Asset & group registry** — hierarchical project/service grouping with metadata timeline and tags
- **SLO groups & templates** — organise SLOs into reusable groups, assign them to assets
- **Display groups** — control how SLI objectives are grouped and ordered in the UI
- **Data source registry** — register adapter instances (Prometheus, mock adapter for testing)
- **Comparison scoping** — `scope_tags` in SLO comparison config to scope baseline history per series

### Evaluation Actions

- **Annotations with categories** — attach categorised contextual notes to evaluations
- **Invalidation & restore** — mark evaluations as invalid and restore them without deleting data
- **Baseline pinning** — pin a specific evaluation as the comparison baseline
- **Status overrides** — manually override an evaluation's pass/warning/fail status
- **Re-evaluation** — re-run an evaluation against updated SLO criteria

### Adapters

- **Prometheus adapter** — standalone query adapter with SLI template variable substitution
- **Mock adapter** — data generator for testing and development

### Frontend

- **Navigator UI** — React 19 SPA with heatmap visualization of evaluation results across assets and time
- **Evaluation detail** — SLI breakdown table, trend charts, and evaluation actions
- **SLO management** — three-mode registry (tree, detail panel, sidebar)
- **Three-theme system** — dark (Radix-based), alt (neutral), light
- **Mock system** — MSW-based deterministic mocks for offline development (30 days history, 40 assets, 30 metrics)

### Infrastructure

- **Docker Compose deployment** — single-command setup with TimescaleDB, Redis, API, worker, UI, and adapters
- **Standalone deploy** — pre-built images on ghcr.io, download compose file from GitHub Releases
- **CI/CD pipeline** — GitHub Actions for lint, typecheck, unit tests, contract freshness, Schemathesis conformance tests
- **Docker security scanning** — Hadolint (Dockerfile lint) + Trivy (CVE scanning) in CI
- **Contract testing** — OpenAPI schema codegen + Schemathesis property-based API conformance tests
- **Python client** — typed client with CLI (not yet on PyPI)

### Tech Stack

- Python 3.13, FastAPI, SQLAlchemy 2 (async), PostgreSQL 16 + TimescaleDB, Redis 7, arq, uv
- React 19, TypeScript 5.9, Vite 8, Tailwind CSS 4, shadcn/ui, Apache ECharts 6, TanStack React Query 5, pnpm
