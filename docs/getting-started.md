# Getting Started with TROPEK

## Prerequisites

- Docker Engine 24+ with Docker Compose v2
- A Prometheus instance (optional — you can use push mode or file upload without one)

## Deployment

### 1. Download deployment files

From the [latest release](https://github.com/domik82/tropek/releases/latest):

```bash
curl -LO https://github.com/domik82/tropek/releases/latest/download/docker-compose.yml
curl -LO https://github.com/domik82/tropek/releases/latest/download/.env.example
```

Or copy them from the `deploy/` directory if you've cloned the repo.

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` and set:

| Variable | Required | Description |
|---|---|---|
| `TK_DB_PASSWORD` | Yes | PostgreSQL password for the bundled TimescaleDB |
| `TK_REDIS_PASSWORD` | Yes | Redis password |
| `TK_SECRET_KEY` | Yes | Application secret — generate with `openssl rand -hex 32` |
| `TK_DB_USER` | No | PostgreSQL user (default: `tropek`) |
| `TK_DB_NAME` | No | Database name (default: `tropek`) |
| `PROMETHEUS_URL` | No | URL of your Prometheus instance |

### 3. Start

```bash
docker compose up -d
```

This starts all services: TimescaleDB, Redis, API (with automatic migrations), worker,
Prometheus adapter, and UI.

### 4. Verify

```bash
# Check all services are running
docker compose ps

# Check API health
curl http://localhost:8080/health
```

- **UI**: http://localhost:3000
- **API docs** (Swagger): http://localhost:8080/docs

## Bringing your own database or Redis

If you have an existing PostgreSQL (with TimescaleDB) or Redis instance, set the URL
variables instead of the component variables:

```env
TK_DATABASE_URL=postgresql+asyncpg://user:pass@your-host:5432/tropek
TK_REDIS_URL=redis://:password@your-host:6379/0
```

Then remove the `timescaledb` and/or `redis` services from `docker-compose.yml`.

TROPEK creates its own tables via Alembic migrations — it will not modify existing
tables in your database.

## Pinning a version

By default, the compose file uses the `latest` image tag. To pin to a specific release:

```bash
TROPEK_VERSION=v0.1.0-alpha docker compose up -d
```

Or set `TROPEK_VERSION=v0.1.0-alpha` in your `.env` file.

## Connecting a Prometheus datasource

1. Register a datasource via the API:

```bash
curl -X POST http://localhost:8080/datasources \
  -H "Content-Type: application/json" \
  -d '{"name": "prometheus", "adapter": "prometheus"}'
```

2. Create an SLO definition (see [SLO format](../README.md#slo-format) in the README).

3. Trigger an evaluation:

```bash
curl -X POST http://localhost:8080/evaluations \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-first-eval",
    "start": "2026-05-01T10:00:00Z",
    "end": "2026-05-01T10:30:00Z",
    "slo_name": "your-slo-name",
    "datasource": {"adapter": "prometheus"}
  }'
```

## Overriding config.yaml

The API image includes a default `config.yaml` with sensible defaults. To customize
(e.g. change cache TTLs, pool sizes, or adapter URLs), mount your own:

```yaml
# In docker-compose.yml, under the api and worker services:
volumes:
  - ./config.yaml:/app/config.yaml:ro
```

See [docs/configuration.md](configuration.md) for all available settings.

## Upgrading

```bash
# Pull new images
docker compose pull

# Restart (migrations run automatically)
docker compose up -d
```
