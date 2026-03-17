# System Overview

TROPEK is a quality gate and performance evaluation platform composed of six services
orchestrated via Docker Compose. No Kubernetes required.

## Service Topology

```mermaid
graph LR
    Client["Client / CI"]
    UI["UI<br/>React SPA<br/>:3000"]
    API["API<br/>FastAPI<br/>:8080"]
    Redis["Redis<br/>:6379<br/>db 0 = cache<br/>db 1 = queue"]
    Worker["Worker<br/>arq<br/>x2 replicas"]
    Adapter["Prometheus Adapter<br/>:8081"]
    Prom["Prometheus<br/>(external)"]
    DB["TimescaleDB<br/>PostgreSQL 16<br/>:5432"]

    Client -->|REST| API
    UI -->|/api proxy| API
    API -->|enqueue job| Redis
    Worker -->|dequeue| Redis
    Worker -->|POST /query| Adapter
    Adapter -->|PromQL| Prom
    Worker -->|read/write| DB
    API -->|read| DB
    API -->|cache| Redis
```

## Services

| Service | Port | Technology | Role |
|---------|------|------------|------|
| **api** | 8080 | FastAPI (Python 3.13) | REST API, evaluation trigger, registries, trend queries |
| **worker** | -- | arq (same image as api) | Async evaluation: fetch metrics, run engine, persist results |
| **adapter-prometheus** | 8081 | FastAPI | Translates SLI queries into PromQL, returns aggregated values |
| **timescaledb** | 5432 | PostgreSQL 16 + TimescaleDB | Evaluations, SLO/SLI registries, SLI time-series hypertable |
| **redis** | 6379 | Redis 7 | Job queue (db 1) and response cache (db 0) |
| **ui** | 3000 | React 19 + Vite | SPA with mock-first development (MSW) |

## Communication Patterns

- **API <-> Worker**: Decoupled via Redis job queue (arq). API enqueues, worker dequeues.
- **Worker <-> Adapter**: Synchronous HTTP POST `/query` with retry + timeout (tenacity).
- **API <-> DB**: Async SQLAlchemy ORM (asyncpg driver). Repository pattern.
- **API <-> Redis**: Response caching with per-endpoint TTLs.
- **UI <-> API**: REST over HTTP. In dev, Vite proxies `/api` to `:8080`. MSW intercepts in mock mode.

## Deployment Profiles

```bash
# Full stack
docker compose up --build

# Dev (infra only, run API/worker on host)
docker compose up timescaledb redis -d

# Test (adds isolated test DB on :5433)
docker compose --profile test up timescaledb-test -d
```

## Configuration Layers

```
Vault (highest priority)
  -> QG_* environment variables
    -> .env file
      -> config.yaml (lowest priority, non-secrets)
```

See [configuration.md](configuration.md) for details.
