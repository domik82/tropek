# Architecture Documentation Index

This document has been superseded by the structured architecture docs.

## System-Wide Architecture

- [architecture/system-overview.md](architecture/system-overview.md) -- Service topology, communication patterns, deployment
- [architecture/evaluation-flow.md](architecture/evaluation-flow.md) -- Evaluation lifecycle, ingestion modes, scoring logic
- [architecture/data-model.md](architecture/data-model.md) -- Database schema, table groups, design decisions
- [architecture/configuration.md](architecture/configuration.md) -- Configuration layers, settings classes, environment variables

## Module Architecture

- [../api/docs/architecture.md](../api/docs/architecture.md) -- API layer: modules, DI, repository pattern, endpoint reference
- [../api/docs/evaluation-engine.md](../api/docs/evaluation-engine.md) -- Pure evaluation engine: criteria, scoring, variable substitution
- [../api/docs/database-layer.md](../api/docs/database-layer.md) -- ORM models, session management, migrations, repository methods
- [../ui/docs/architecture.md](../ui/docs/architecture.md) -- Frontend: tech stack, directory structure, state management, theming
- [../ui/docs/features.md](../ui/docs/features.md) -- Feature modules: evaluations, assets, navigator, SLOs, SLIs
- [../ui/docs/mocking.md](../ui/docs/mocking.md) -- MSW mock system and deterministic data generator
- [../adapters/prometheus/docs/architecture.md](../adapters/prometheus/docs/architecture.md) -- Adapter architecture, planned interface, adapter contract
