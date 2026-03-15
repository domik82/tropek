# Quality Platform Phase 1 — Chunk 1: Project Scaffold

> **For agentic workers:** Use superpowers:executing-plans to implement this chunk.

**Goal:** Monorepo scaffold with uv, pyproject.toml, ruff, mypy, Docker Compose skeleton, and config loading verified by tests.

**Architecture:** Two Python services (`quality-gate-api`, `adapter-prometheus`) plus React UI, all wired in Docker Compose. Config loads from `config.yaml` + env vars via Pydantic Settings.

**Tech Stack:** Python 3.12, uv, FastAPI, Pydantic v2, mypy, ruff, Docker Compose v2

---

## Chunk 1: Scaffold

### Task 1.1: Monorepo root structure

**Files:**
- Create: `quality-platform/.gitignore`
- Create: `quality-platform/.env.example`
- Create: `quality-platform/config.yaml`
- Create: `quality-platform/docker-compose.yml`

- [ ] Create root directory and .gitignore

```bash
mkdir -p quality-platform
cd quality-platform
cat > .gitignore << 'EOF'
.env
__pycache__/
*.py[cod]
.mypy_cache/
.ruff_cache/
*.egg-info/
dist/
.venv/
node_modules/
EOF
```

- [ ] Create `.env.example`

```bash
cat > .env.example << 'EOF'
QG_DB_USER=quality_gate
QG_DB_PASSWORD=changeme
QG_REDIS_PASSWORD=changeme
QG_SECRET_KEY=change-me-in-production
# Optional Vault:
# QG_VAULT_ADDR=https://vault.internal:8200
# QG_VAULT_TOKEN=s.xxxxx
# QG_VAULT_SECRET_PATH=secret/data/quality-gate
EOF
```

- [ ] Create `config.yaml`

```yaml
server:
  host: "0.0.0.0"
  port: 8080

database:
  host: "timescaledb"
  port: 5432
  name: "quality_gate"
  pool_size: 10
  max_overflow: 20

cache:
  backend: "redis"
  host: "redis"
  port: 6379
  db: 0
  ttl_seconds:
    trend: 60
    evaluation_list: 30
    evaluation_detail: 300
    slo_definition: 600

queue:
  backend: "redis"
  db_index: 1
  max_retries: 3
  retry_delay_seconds: 10
  job_timeout_seconds: 120
  keep_result_seconds: 3600

reliability:
  adapter_timeout_seconds: 30
  adapter_retry_attempts: 3
  adapter_retry_backoff_seconds: 2
  watchdog_interval_seconds: 60
  stuck_job_threshold_seconds: 180

evaluation:
  async_threshold_metrics: 10

adapters:
  prometheus:
    url: "http://adapter-prometheus:8081"
    timeout_seconds: 30
  max_concurrent_queries_per_adapter: 10

db_writer:
  workers: 5
  batch_size: 100

file_ingestion:
  allowed_path_prefix: "/data/results"
  max_file_size_mb: 50

logging:
  level: "INFO"
  format: "json"
```

- [ ] Create `docker-compose.yml` skeleton

```yaml
services:
  timescaledb:
    image: timescale/timescaledb:latest-pg16
    environment:
      POSTGRES_USER: ${QG_DB_USER}
      POSTGRES_PASSWORD: ${QG_DB_PASSWORD}
      POSTGRES_DB: quality_gate
    ports:
      - "5432:5432"
    volumes:
      - timescaledb_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${QG_DB_USER} -d quality_gate"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --requirepass ${QG_REDIS_PASSWORD}
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${QG_REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  quality-gate-api:
    build:
      context: ./quality-gate-api
      dockerfile: Dockerfile
    ports:
      - "8080:8080"
    environment:
      QG_DB_USER: ${QG_DB_USER}
      QG_DB_PASSWORD: ${QG_DB_PASSWORD}
      QG_REDIS_PASSWORD: ${QG_REDIS_PASSWORD}
      QG_SECRET_KEY: ${QG_SECRET_KEY}
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - results_data:/data/results
    depends_on:
      timescaledb:
        condition: service_healthy
      redis:
        condition: service_healthy

  quality-gate-worker:
    build:
      context: ./quality-gate-api
      dockerfile: Dockerfile
    command: ["uv", "run", "arq", "app.worker.WorkerSettings"]
    environment:
      QG_DB_USER: ${QG_DB_USER}
      QG_DB_PASSWORD: ${QG_DB_PASSWORD}
      QG_REDIS_PASSWORD: ${QG_REDIS_PASSWORD}
      QG_SECRET_KEY: ${QG_SECRET_KEY}
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - results_data:/data/results
    depends_on:
      timescaledb:
        condition: service_healthy
      redis:
        condition: service_healthy
    deploy:
      replicas: 2

  adapter-prometheus:
    build:
      context: ./adapter-prometheus
      dockerfile: Dockerfile
    ports:
      - "8081:8081"
    environment:
      PROMETHEUS_URL: ${PROMETHEUS_URL:-http://prometheus:9090}
      QG_ADAPTER_PROMETHEUS_USERNAME: ${QG_ADAPTER_PROMETHEUS_USERNAME:-}
      QG_ADAPTER_PROMETHEUS_PASSWORD: ${QG_ADAPTER_PROMETHEUS_PASSWORD:-}

  ui:
    build:
      context: ./ui
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    depends_on:
      - quality-gate-api

volumes:
  timescaledb_data:
  redis_data:
  results_data:
```

- [ ] Commit

```bash
git init
git add .
git commit -m "chore: monorepo root scaffold with Docker Compose"
```

---

### Task 1.2: quality-gate-api Python project

**Files:**
- Create: `quality-gate-api/pyproject.toml`
- Create: `quality-gate-api/Dockerfile`
- Create: `quality-gate-api/app/__init__.py`
- Create: `quality-gate-api/app/config.py`
- Create: `quality-gate-api/tests/__init__.py`
- Create: `quality-gate-api/tests/test_config.py`

- [ ] Initialise uv project

```bash
cd quality-gate-api
uv init --name quality-gate-api --python 3.12
```

- [ ] Replace generated `pyproject.toml` with full config

```toml
[project]
name = "quality-gate-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "arq>=0.26",
    "redis>=5.0",
    "httpx>=0.27",
    "pyyaml>=6.0",
    "python-multipart>=0.0.9",
    "structlog>=24.0",
    "hvac>=2.0",         # Vault client (optional at runtime)
    "tenacity>=8.3",     # retry logic
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-httpx>=0.30",
    "mypy>=1.10",
    "ruff>=0.4",
    "types-pyyaml",
    "types-redis",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-httpx>=0.30",
    "mypy>=1.10",
    "ruff>=0.4",
    "types-pyyaml",
    "types-redis",
]
```

- [ ] Install dependencies

```bash
uv sync
```

Expected: `.venv/` created, all packages installed.

- [ ] Write the failing config test

```python
# tests/test_config.py
import os
import pytest
from pathlib import Path


def test_config_loads_from_yaml(tmp_path: Path) -> None:
    """Config loads database host from config.yaml."""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("database:\n  host: myhost\n  port: 5432\n  name: testdb\n")

    os.environ["QG_CONFIG_PATH"] = str(cfg_file)
    os.environ["QG_DB_USER"] = "testuser"
    os.environ["QG_DB_PASSWORD"] = "testpass"
    os.environ["QG_REDIS_PASSWORD"] = "redispass"
    os.environ["QG_SECRET_KEY"] = "testsecret"

    # Force reimport
    import importlib
    import app.config as config_module
    importlib.reload(config_module)

    from app.config import get_settings
    settings = get_settings()

    assert settings.database.host == "myhost"
    assert settings.database.name == "testdb"
    assert settings.database.user == "testuser"
    assert settings.database.password.get_secret_value() == "testpass"


def test_env_overrides_yaml(tmp_path: Path) -> None:
    """Environment variable QG_DB_USER takes precedence over yaml defaults."""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("database:\n  host: localhost\n  port: 5432\n  name: qg\n")

    os.environ["QG_CONFIG_PATH"] = str(cfg_file)
    os.environ["QG_DB_USER"] = "override_user"
    os.environ["QG_DB_PASSWORD"] = "pass"
    os.environ["QG_REDIS_PASSWORD"] = "rpass"
    os.environ["QG_SECRET_KEY"] = "secret"

    import importlib
    import app.config as config_module
    importlib.reload(config_module)

    from app.config import get_settings
    settings = get_settings()
    assert settings.database.user == "override_user"
```

- [ ] Run failing test

```bash
uv run pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.config'`

- [ ] Implement `app/config.py`

```python
# app/config.py
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_yaml() -> dict[str, Any]:
    path = Path(os.environ.get("QG_CONFIG_PATH", "/app/config.yaml"))
    if path.exists():
        with path.open() as f:
            return yaml.safe_load(f) or {}
    return {}


_yaml = _load_yaml()


class DatabaseSettings(BaseSettings):
    host: str = _yaml.get("database", {}).get("host", "localhost")
    port: int = _yaml.get("database", {}).get("port", 5432)
    name: str = _yaml.get("database", {}).get("name", "quality_gate")
    pool_size: int = _yaml.get("database", {}).get("pool_size", 10)
    max_overflow: int = _yaml.get("database", {}).get("max_overflow", 20)
    user: str = ""
    password: SecretStr = SecretStr("")

    model_config = SettingsConfigDict(env_prefix="QG_DB_")

    @property
    def async_url(self) -> str:
        pw = self.password.get_secret_value()
        return f"postgresql+asyncpg://{self.user}:{pw}@{self.host}:{self.port}/{self.name}"


class CacheTTLSettings(BaseSettings):
    trend: int = _yaml.get("cache", {}).get("ttl_seconds", {}).get("trend", 60)
    evaluation_list: int = _yaml.get("cache", {}).get("ttl_seconds", {}).get("evaluation_list", 30)
    evaluation_detail: int = _yaml.get("cache", {}).get("ttl_seconds", {}).get("evaluation_detail", 300)
    slo_definition: int = _yaml.get("cache", {}).get("ttl_seconds", {}).get("slo_definition", 600)


class CacheSettings(BaseSettings):
    backend: str = _yaml.get("cache", {}).get("backend", "redis")
    host: str = _yaml.get("cache", {}).get("host", "redis")
    port: int = _yaml.get("cache", {}).get("port", 6379)
    db: int = _yaml.get("cache", {}).get("db", 0)
    ttl: CacheTTLSettings = CacheTTLSettings()
    password: SecretStr = SecretStr("")

    model_config = SettingsConfigDict(env_prefix="QG_REDIS_")

    @property
    def url(self) -> str:
        pw = self.password.get_secret_value()
        auth = f":{pw}@" if pw else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class QueueSettings(BaseSettings):
    db_index: int = _yaml.get("queue", {}).get("db_index", 1)
    max_retries: int = _yaml.get("queue", {}).get("max_retries", 3)
    retry_delay_seconds: int = _yaml.get("queue", {}).get("retry_delay_seconds", 10)
    job_timeout_seconds: int = _yaml.get("queue", {}).get("job_timeout_seconds", 120)
    keep_result_seconds: int = _yaml.get("queue", {}).get("keep_result_seconds", 3600)


class ReliabilitySettings(BaseSettings):
    adapter_timeout_seconds: int = _yaml.get("reliability", {}).get("adapter_timeout_seconds", 30)
    adapter_retry_attempts: int = _yaml.get("reliability", {}).get("adapter_retry_attempts", 3)
    adapter_retry_backoff_seconds: int = _yaml.get("reliability", {}).get("adapter_retry_backoff_seconds", 2)
    watchdog_interval_seconds: int = _yaml.get("reliability", {}).get("watchdog_interval_seconds", 60)
    stuck_job_threshold_seconds: int = _yaml.get("reliability", {}).get("stuck_job_threshold_seconds", 180)


class AdapterConfig(BaseSettings):
    url: str = ""
    timeout_seconds: int = 30


class AdaptersSettings(BaseSettings):
    prometheus: AdapterConfig = AdapterConfig(
        url=_yaml.get("adapters", {}).get("prometheus", {}).get("url", "http://adapter-prometheus:8081"),
        timeout_seconds=_yaml.get("adapters", {}).get("prometheus", {}).get("timeout_seconds", 30),
    )
    max_concurrent_queries_per_adapter: int = (
        _yaml.get("adapters", {}).get("max_concurrent_queries_per_adapter", 10)
    )


class EvaluationSettings(BaseSettings):
    async_threshold_metrics: int = _yaml.get("evaluation", {}).get("async_threshold_metrics", 10)


class FileIngestionSettings(BaseSettings):
    allowed_path_prefix: str = _yaml.get("file_ingestion", {}).get("allowed_path_prefix", "/data/results")
    max_file_size_mb: int = _yaml.get("file_ingestion", {}).get("max_file_size_mb", 50)


class Settings(BaseSettings):
    database: DatabaseSettings = DatabaseSettings()
    cache: CacheSettings = CacheSettings()
    queue: QueueSettings = QueueSettings()
    reliability: ReliabilitySettings = ReliabilitySettings()
    adapters: AdaptersSettings = AdaptersSettings()
    evaluation: EvaluationSettings = EvaluationSettings()
    file_ingestion: FileIngestionSettings = FileIngestionSettings()
    secret_key: SecretStr = SecretStr("")

    model_config = SettingsConfigDict(env_prefix="QG_")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] Create `app/__init__.py` (empty)

```bash
touch app/__init__.py tests/__init__.py
```

- [ ] Run tests — expect pass

```bash
uv run pytest tests/test_config.py -v
```

Expected:
```
PASSED tests/test_config.py::test_config_loads_from_yaml
PASSED tests/test_config.py::test_env_overrides_yaml
```

- [ ] Run mypy and ruff

```bash
uv run mypy app/config.py
uv run ruff check app/config.py
```

Expected: no errors.

- [ ] Create `Dockerfile`

```dockerfile
FROM python:3.12-slim

RUN pip install uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

COPY . .

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] Create minimal `app/main.py`

```python
# app/main.py
from fastapi import FastAPI
from app.config import get_settings

app = FastAPI(title="Quality Gate API", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] Commit

```bash
git add quality-gate-api/
git commit -m "feat: quality-gate-api scaffold with uv, config, ruff, mypy"
```

---

### Task 1.3: adapter-prometheus scaffold

**Files:**
- Create: `adapter-prometheus/pyproject.toml`
- Create: `adapter-prometheus/Dockerfile`
- Create: `adapter-prometheus/app/__init__.py`
- Create: `adapter-prometheus/app/main.py`
- Create: `adapter-prometheus/app/config.py`
- Create: `adapter-prometheus/tests/__init__.py`

- [ ] Initialise uv project

```bash
cd ../adapter-prometheus
uv init --name adapter-prometheus --python 3.12
```

- [ ] Write `pyproject.toml`

```toml
[project]
name = "adapter-prometheus"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.7",
    "httpx>=0.27",
    "pyyaml>=6.0",
    "tenacity>=8.3",
    "structlog>=24.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-httpx>=0.30",
    "mypy>=1.10",
    "ruff>=0.4",
    "types-pyyaml",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-httpx>=0.30",
    "mypy>=1.10",
    "ruff>=0.4",
    "types-pyyaml",
]
```

- [ ] Install

```bash
uv sync
```

- [ ] Create `app/config.py`

```python
# app/config.py
import os
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    prometheus_url: str = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
    default_step: str = "60s"
    username: str = ""
    password: SecretStr = SecretStr("")
    timeout_seconds: int = 30
    retry_attempts: int = 3
    retry_backoff_seconds: int = 2

    model_config = SettingsConfigDict(env_prefix="QG_ADAPTER_PROMETHEUS_")


def get_settings() -> Settings:
    return Settings()
```

- [ ] Create `app/main.py`

```python
# app/main.py
from fastapi import FastAPI

app = FastAPI(title="Prometheus Adapter", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "datasource": "prometheus"}
```

- [ ] Create `Dockerfile`

```dockerfile
FROM python:3.12-slim

RUN pip install uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

COPY . .

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081"]
```

- [ ] Commit

```bash
cd ..
git add adapter-prometheus/
git commit -m "feat: adapter-prometheus scaffold"
```

---

### Task 1.4: Verify Docker Compose starts

- [ ] Copy `.env.example` to `.env` and fill values

```bash
cp .env.example .env
# Edit .env: set real passwords or keep defaults for local dev
```

- [ ] Start infrastructure only

```bash
docker compose up timescaledb redis -d
docker compose ps
```

Expected: both services `healthy`.

- [ ] Build and start API

```bash
docker compose build quality-gate-api
docker compose up quality-gate-api -d
curl http://localhost:8080/health
```

Expected: `{"status":"ok"}`

- [ ] Tear down

```bash
docker compose down
```

- [ ] Commit

```bash
git commit -m "chore: verify Docker Compose scaffold starts cleanly" --allow-empty
```
