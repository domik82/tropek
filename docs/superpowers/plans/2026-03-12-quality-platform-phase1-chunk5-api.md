# Quality Platform Phase 1 — Chunk 5: REST API Endpoints

> **For agentic workers:** Use superpowers:executing-plans to implement this chunk.
> **Depends on:** Chunks 1–4

**Goal:** All REST API endpoints wired up — evaluations (all modes), SLO registry (versioned), trend, annotations, rerun. FastAPI routers with Pydantic schemas, Redis caching on reads.

---

## Chunk 5: REST API

### Task 5.1: Pydantic Schemas

**Files:**
- Create: `quality-gate-api/app/modules/quality_gate/schemas.py`
- Create: `quality-gate-api/app/modules/slo_registry/schemas.py`
- Create: `quality-gate-api/tests/test_schemas.py`

- [ ] Write `app/modules/quality_gate/schemas.py`

```python
# app/modules/quality_gate/schemas.py
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class DatasourceConfig(BaseModel):
    adapter: str = "prometheus"
    url: str | None = None


class AssetVersionInfo(BaseModel):
    name: str
    commit: str | None = None
    branch: str | None = None
    version: str | None = None


class EvaluationRequest(BaseModel):
    name: str
    start: datetime
    end: datetime
    asset_name: str | None = None
    assets: list[AssetVersionInfo] = Field(default_factory=list)
    slo_name: str | None = None
    slo_yaml: str | None = None
    # Ingestion: exactly one of these three groups
    datasource: DatasourceConfig | None = None
    metrics: dict[str, float | None] | None = None
    results_path: str | None = None
    results_format: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    async_mode: bool = False

    @model_validator(mode="after")
    def validate_ingestion_mode(self) -> "EvaluationRequest":
        modes = [
            self.datasource is not None,
            self.metrics is not None,
            self.results_path is not None,
        ]
        if sum(modes) != 1:
            raise ValueError(
                "Exactly one of 'datasource', 'metrics', or 'results_path' must be provided"
            )
        if self.results_path and not self.results_format:
            raise ValueError("'results_format' is required when 'results_path' is provided")
        if not self.slo_name and not self.slo_yaml:
            raise ValueError("Either 'slo_name' or 'slo_yaml' must be provided")
        return self


class EvaluationFileRequest(BaseModel):
    """Parsed from the 'meta' field in multipart upload."""
    name: str
    start: datetime
    end: datetime
    asset_name: str | None = None
    slo_name: str | None = None
    slo_yaml: str | None = None
    results_format: str
    metadata: dict[str, str] = Field(default_factory=dict)


class TargetResult(BaseModel):
    criteria: str
    target_value: float
    violated: bool


class IndicatorResult(BaseModel):
    metric: str
    display_name: str
    value: float | None
    compared_value: float | None = None
    change_absolute: float | None = None
    change_relative_pct: float | None = None
    status: str
    score: float
    weight: int
    key_sli: bool
    pass_targets: list[TargetResult] = Field(default_factory=list)
    warning_targets: list[TargetResult] | None = None


class AnnotationOut(BaseModel):
    id: UUID
    evaluation_id: UUID
    content: str
    author: str | None
    category: str | None
    meta: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class EvaluationOut(BaseModel):
    id: UUID
    name: str
    status: str
    result: str | None
    score: float | None
    start: datetime
    end: datetime
    slo_name: str | None
    slo_version: int | None
    ingestion_mode: str
    adapter_used: str | None
    invalidated: bool
    invalidation_note: str | None
    asset_snapshot: dict[str, Any]
    metadata: dict[str, Any]
    compared_evaluation_ids: list[str] = Field(default_factory=list)
    indicator_results: list[dict[str, Any]] = Field(default_factory=list)
    annotations: list[AnnotationOut] = Field(default_factory=list)
    job_stats: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class EvaluationAccepted(BaseModel):
    eval_id: UUID
    status: str = "pending"
    status_url: str


class InvalidateRequest(BaseModel):
    invalidated: bool
    invalidation_note: str | None = None


class RerunRequest(BaseModel):
    mode: str = "soft"  # "soft" | "hard"
    reason: str = ""
    triggered_by: str | None = None


class AnnotationRequest(BaseModel):
    content: str
    author: str | None = None
    category: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
```

- [ ] Write `app/modules/slo_registry/schemas.py`

```python
# app/modules/slo_registry/schemas.py
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SLOCreateRequest(BaseModel):
    name: str
    slo_yaml: str
    notes: str | None = None
    author: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class SLOUpdateRequest(BaseModel):
    slo_yaml: str
    notes: str | None = None
    author: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class SLOVersionOut(BaseModel):
    name: str
    version: int
    notes: str | None
    author: str | None
    meta: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class SLODetailOut(SLOVersionOut):
    slo_yaml: str


class SLOVersionListOut(BaseModel):
    name: str
    versions: list[SLOVersionOut]


class SLOValidateRequest(BaseModel):
    slo_yaml: str


class SLOValidateResponse(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)


class TrendPoint(BaseModel):
    timestamp: str
    value: float
    eval_id: str
    result: str
```

- [ ] Commit

```bash
git add app/modules/
git commit -m "feat: Pydantic request/response schemas for evaluations and SLO registry"
```

---

### Task 5.2: SLO Registry Router

**Files:**
- Create: `quality-gate-api/app/modules/slo_registry/router.py`
- Create: `quality-gate-api/app/modules/slo_registry/service.py`
- Create: `quality-gate-api/tests/api/test_slo_registry.py`

- [ ] Write failing API tests

```python
# tests/api/test_slo_registry.py
import pytest
from httpx import AsyncClient

VALID_SLO = """spec_version: '1.0'
indicators:
  cpu: 'avg_over_time(cpu[5m])'
objectives:
  - sli: cpu
    pass:
      - criteria: ["<90"]
    weight: 1
total_score:
  pass: "90%"
  warning: "75%"
"""


@pytest.fixture
async def client(app):
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c


async def test_create_slo(client: AsyncClient) -> None:
    resp = await client.post("/slos", json={
        "name": "test-slo",
        "slo_yaml": VALID_SLO,
        "notes": "initial version",
        "author": "test",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["version"] == 1
    assert data["name"] == "test-slo"


async def test_create_second_version_increments(client: AsyncClient) -> None:
    await client.post("/slos", json={"name": "versioned-slo", "slo_yaml": VALID_SLO})
    resp = await client.put("/slos/versioned-slo", json={
        "slo_yaml": VALID_SLO,
        "notes": "v2",
    })
    assert resp.status_code == 201
    assert resp.json()["version"] == 2


async def test_get_latest_slo(client: AsyncClient) -> None:
    await client.post("/slos", json={"name": "get-test", "slo_yaml": VALID_SLO})
    resp = await client.get("/slos/get-test")
    assert resp.status_code == 200
    assert resp.json()["slo_yaml"] == VALID_SLO


async def test_get_nonexistent_slo_404(client: AsyncClient) -> None:
    resp = await client.get("/slos/nonexistent")
    assert resp.status_code == 404


async def test_validate_valid_slo(client: AsyncClient) -> None:
    resp = await client.post("/slos/validate", json={"slo_yaml": VALID_SLO})
    assert resp.status_code == 200
    assert resp.json()["valid"] is True


async def test_validate_invalid_slo(client: AsyncClient) -> None:
    resp = await client.post("/slos/validate", json={"slo_yaml": "not yaml: ]["})
    assert resp.status_code == 200
    assert resp.json()["valid"] is False
    assert resp.json()["errors"]


async def test_list_versions(client: AsyncClient) -> None:
    await client.post("/slos", json={"name": "list-ver", "slo_yaml": VALID_SLO})
    await client.put("/slos/list-ver", json={"slo_yaml": VALID_SLO, "notes": "v2"})
    resp = await client.get("/slos/list-ver/versions")
    assert resp.status_code == 200
    assert len(resp.json()["versions"]) == 2


async def test_get_specific_version(client: AsyncClient) -> None:
    await client.post("/slos", json={"name": "spec-ver", "slo_yaml": VALID_SLO})
    resp = await client.get("/slos/spec-ver/versions/1")
    assert resp.status_code == 200
    assert resp.json()["version"] == 1
```

- [ ] Create `app/modules/slo_registry/service.py`

```python
# app/modules/slo_registry/service.py
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.quality_gate.engine.slo_parser import SLOParseError, parse_slo
from app.modules.slo_registry.repository import SLORepository
from app.db.models import SLODefinition


async def create_slo(
    session: AsyncSession,
    *,
    name: str,
    slo_yaml: str,
    notes: str | None,
    author: str | None,
    meta: dict[str, Any],
) -> SLODefinition:
    _validate_or_raise(slo_yaml)
    repo = SLORepository(session)
    return await repo.create(name=name, slo_yaml=slo_yaml, notes=notes, author=author, meta=meta)


async def update_slo(
    session: AsyncSession,
    *,
    name: str,
    slo_yaml: str,
    notes: str | None,
    author: str | None,
    meta: dict[str, Any],
) -> SLODefinition:
    _validate_or_raise(slo_yaml)
    repo = SLORepository(session)
    return await repo.create(name=name, slo_yaml=slo_yaml, notes=notes, author=author, meta=meta)


def validate_slo_yaml(slo_yaml: str) -> list[str]:
    errors: list[str] = []
    try:
        parse_slo(slo_yaml)
    except SLOParseError as e:
        errors.append(str(e))
    except Exception as e:
        errors.append(f"Unexpected error: {e}")
    return errors


def _validate_or_raise(slo_yaml: str) -> None:
    errors = validate_slo_yaml(slo_yaml)
    if errors:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail={"slo_yaml": errors})
```

- [ ] Create `app/modules/slo_registry/router.py`

```python
# app/modules/slo_registry/router.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis import cache_delete_pattern, cache_get, cache_set, make_cache_key
from app.config import get_settings
from app.db.session import get_session as _get_session
from app.modules.slo_registry import repository as repo_module
from app.modules.slo_registry import service
from app.modules.slo_registry.schemas import (
    SLOCreateRequest,
    SLODetailOut,
    SLOUpdateRequest,
    SLOValidateRequest,
    SLOValidateResponse,
    SLOVersionListOut,
    SLOVersionOut,
)
from app.modules.slo_registry.repository import SLORepository

router = APIRouter(prefix="/slos", tags=["SLO Registry"])


async def _db() -> AsyncSession:  # type: ignore[misc]
    async with _get_session() as session:
        yield session


@router.post("", status_code=201, response_model=SLOVersionOut)
async def create_slo(req: SLOCreateRequest, session: AsyncSession = Depends(_db)):
    slo = await service.create_slo(
        session,
        name=req.name,
        slo_yaml=req.slo_yaml,
        notes=req.notes,
        author=req.author,
        meta=req.meta,
    )
    await cache_delete_pattern(make_cache_key("slo", req.name, "*"))
    return SLOVersionOut.model_validate(slo)


@router.put("/{name}", status_code=201, response_model=SLOVersionOut)
async def update_slo(name: str, req: SLOUpdateRequest, session: AsyncSession = Depends(_db)):
    slo = await service.update_slo(
        session, name=name, slo_yaml=req.slo_yaml, notes=req.notes, author=req.author, meta=req.meta
    )
    await cache_delete_pattern(make_cache_key("slo", name, "*"))
    return SLOVersionOut.model_validate(slo)


@router.get("/{name}", response_model=SLODetailOut)
async def get_slo(name: str, session: AsyncSession = Depends(_db)):
    ttl = get_settings().cache.ttl.slo_definition
    key = make_cache_key("slo", name, "latest")
    cached = await cache_get(key)
    if cached:
        return SLODetailOut(**cached)

    repo = SLORepository(session)
    slo = await repo.get_latest(name)
    if not slo:
        raise HTTPException(status_code=404, detail=f"SLO '{name}' not found")

    out = SLODetailOut.model_validate(slo)
    await cache_set(key, out.model_dump(mode="json"), ttl)
    return out


@router.get("/{name}/versions", response_model=SLOVersionListOut)
async def list_versions(name: str, session: AsyncSession = Depends(_db)):
    repo = SLORepository(session)
    versions = await repo.list_versions(name)
    return SLOVersionListOut(
        name=name,
        versions=[SLOVersionOut.model_validate(v) for v in versions],
    )


@router.get("/{name}/versions/{version}", response_model=SLODetailOut)
async def get_version(name: str, version: int, session: AsyncSession = Depends(_db)):
    repo = SLORepository(session)
    slo = await repo.get_version(name, version)
    if not slo:
        raise HTTPException(status_code=404, detail=f"SLO '{name}' version {version} not found")
    return SLODetailOut.model_validate(slo)


@router.delete("/{name}", status_code=204)
async def delete_slo(name: str, session: AsyncSession = Depends(_db)):
    repo = SLORepository(session)
    count = await repo.soft_delete(name)
    if count == 0:
        raise HTTPException(status_code=404, detail=f"SLO '{name}' not found")
    await cache_delete_pattern(make_cache_key("slo", name, "*"))


@router.post("/validate", response_model=SLOValidateResponse)
async def validate_slo(req: SLOValidateRequest):
    errors = service.validate_slo_yaml(req.slo_yaml)
    return SLOValidateResponse(valid=len(errors) == 0, errors=errors)
```

- [ ] Wire routers into `app/main.py`

```python
# app/main.py
from fastapi import FastAPI
from app.config import get_settings
from app.modules.slo_registry.router import router as slo_router
# More routers added in subsequent tasks

app = FastAPI(title="Quality Gate API", version="0.1.0")

app.include_router(slo_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] Create test `conftest.py` with in-memory DB

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app as fastapi_app


@pytest.fixture
def app():
    return fastapi_app
```

- [ ] Run API tests

```bash
uv run pytest tests/api/test_slo_registry.py -v
```

Note: these tests require a running TimescaleDB. For unit tests, mock the session. Integration tests run against the real DB.

- [ ] Commit

```bash
git add app/modules/slo_registry/ tests/api/
git commit -m "feat: SLO registry CRUD API with versioning and validation"
```

---

### Task 5.3: Evaluations Router

**Files:**
- Create: `quality-gate-api/app/modules/quality_gate/router.py`
- Create: `quality-gate-api/app/modules/quality_gate/service.py`

- [ ] Create `app/modules/quality_gate/service.py`

```python
# app/modules/quality_gate/service.py
"""Orchestrates evaluation trigger: resolve SLO, substitute vars, enqueue job."""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from arq import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.modules.quality_gate.engine.slo_parser import parse_slo
from app.modules.quality_gate.engine.variables import UnresolvedVariableError, build_variables, substitute_slo_variables
from app.modules.quality_gate.parsers.csv_parser import parse_csv
from app.modules.quality_gate.parsers.jmeter_parser import parse_jmeter
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.slo_registry.repository import SLORepository
from app.db.models import Evaluation
from fastapi import HTTPException


async def trigger_evaluation(
    *,
    session: AsyncSession,
    arq_redis: ArqRedis,
    name: str,
    start: datetime,
    end: datetime,
    asset_name: str | None,
    assets: list[dict[str, Any]],
    slo_name: str | None,
    slo_yaml_inline: str | None,
    datasource: dict[str, Any] | None,
    metrics: dict[str, float | None] | None,
    results_path: str | None,
    results_format: str | None,
    metadata: dict[str, str],
    async_mode: bool,
) -> Evaluation:
    settings = get_settings()

    # 1. Resolve SLO
    slo_version_int: int | None = None
    if slo_yaml_inline:
        resolved_slo_yaml = slo_yaml_inline
    elif slo_name:
        repo = SLORepository(session)
        slo_def = await repo.get_latest(slo_name)
        if not slo_def:
            raise HTTPException(404, f"SLO '{slo_name}' not found")
        resolved_slo_yaml = slo_def.slo_yaml
        slo_version_int = slo_def.version
    else:
        raise HTTPException(422, "slo_name or slo_yaml required")

    # 2. Determine ingestion mode and build job payload
    ingestion_mode: str
    job_extras: dict[str, Any] = {}

    if metrics is not None:
        ingestion_mode = "push"
        job_extras["metrics"] = metrics
    elif results_path is not None:
        ingestion_mode = "file"
        _check_path_allowed(results_path, settings.file_ingestion.allowed_path_prefix)
        parsed_metrics = _parse_file(results_path, results_format or "csv")
        job_extras["metrics"] = parsed_metrics
    else:
        # pull mode
        ingestion_mode = "pull"
        adapter_url = (datasource or {}).get("url") or settings.adapters.prometheus.url

        # Variable substitution
        variables = build_variables(
            metadata, asset_name=asset_name, test_name=name,
            start=start.isoformat(), end=end.isoformat(),
        )
        try:
            resolved_slo_yaml = substitute_slo_variables(resolved_slo_yaml, variables)
        except UnresolvedVariableError as e:
            raise HTTPException(422, str(e)) from e

        slo = parse_slo(resolved_slo_yaml)
        job_extras.update({
            "adapter_url": adapter_url,
            "sli_yaml": _extract_indicators_yaml(slo),
            "indicators": list(slo.indicators.keys()),
            "variables": variables,
        })

    job_extras["resolved_slo_yaml"] = resolved_slo_yaml

    # 3. Build asset snapshot
    asset_snapshot: dict[str, Any] = {
        "name": asset_name,
        "tags": {k: v for k, v in metadata.items() if k in ("os", "arch", "branch")},
        "primary_version": metadata.get("branch") or metadata.get("version"),
        "build_ref": metadata.get("build"),
        "components": assets,
    }

    # 4. Create pending evaluation record
    eval_repo = EvaluationRepository(session)
    ev = await eval_repo.create_pending(
        name=name,
        start_time=start,
        end_time=end,
        ingestion_mode=ingestion_mode,
        asset_snapshot=asset_snapshot,
        metadata=dict(metadata),
        slo_name=slo_name,
        slo_version=slo_version_int,
        adapter_used=(datasource or {}).get("adapter"),
    )

    # Store job payload in job_stats (arq passes only eval_id)
    from sqlalchemy import update
    from app.db.models import Evaluation as EvalModel
    await session.execute(
        update(EvalModel).where(EvalModel.id == ev.id).values(job_stats=job_extras)
    )
    await session.flush()

    # 5. Enqueue job
    await arq_redis.enqueue_job("run_evaluation_job", str(ev.id))
    return ev


def _check_path_allowed(path: str, prefix: str) -> None:
    resolved = Path(path).resolve()
    allowed = Path(prefix).resolve()
    if not str(resolved).startswith(str(allowed)):
        raise HTTPException(400, f"results_path must be under {prefix}")


def _parse_file(path: str, fmt: str) -> dict[str, float | None]:
    content = Path(path).read_text()
    if fmt == "csv":
        return parse_csv(content)
    if fmt == "jmeter":
        return parse_jmeter(content)
    raise HTTPException(400, f"Unsupported results_format: {fmt}")


def _extract_indicators_yaml(slo: Any) -> str:
    """Serialise only the indicators block as YAML text."""
    import yaml
    return yaml.dump({"spec_version": "1.0", "indicators": slo.indicators})
```

- [ ] Create `app/modules/quality_gate/router.py`

```python
# app/modules/quality_gate/router.py
from __future__ import annotations

import json
import uuid
from typing import Any

from arq import ArqRedis
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis import cache_delete_pattern, cache_get, cache_set, make_cache_key
from app.config import get_settings
from app.db.models import Evaluation
from app.db.session import get_session as _get_session
from app.modules.quality_gate import service
from app.modules.quality_gate.rerun import RerunMode, execute_rerun
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.quality_gate.schemas import (
    AnnotationRequest,
    AnnotationOut,
    EvaluationAccepted,
    EvaluationFileRequest,
    EvaluationOut,
    EvaluationRequest,
    InvalidateRequest,
    RerunRequest,
)

router = APIRouter(prefix="/evaluations", tags=["Evaluations"])


async def _db():
    async with _get_session() as session:
        yield session


async def _arq() -> ArqRedis:  # type: ignore[misc]
    from arq.connections import create_pool, RedisSettings
    settings = get_settings()
    pw = settings.cache.password.get_secret_value()
    rs = RedisSettings(
        host=settings.cache.host,
        port=settings.cache.port,
        database=settings.queue.db_index,
        password=pw or None,
    )
    pool = await create_pool(rs)
    try:
        yield pool
    finally:
        await pool.aclose()


@router.post("", status_code=202, response_model=EvaluationAccepted)
async def trigger_evaluation(
    req: EvaluationRequest,
    session: AsyncSession = Depends(_db),
    arq: ArqRedis = Depends(_arq),
):
    ev = await service.trigger_evaluation(
        session=session,
        arq_redis=arq,
        name=req.name,
        start=req.start,
        end=req.end,
        asset_name=req.asset_name,
        assets=[a.model_dump() for a in req.assets],
        slo_name=req.slo_name,
        slo_yaml_inline=req.slo_yaml,
        datasource=req.datasource.model_dump() if req.datasource else None,
        metrics=req.metrics,
        results_path=req.results_path,
        results_format=req.results_format,
        metadata=req.metadata,
        async_mode=req.async_mode,
    )
    return EvaluationAccepted(
        eval_id=ev.id,
        status_url=f"/evaluations/{ev.id}",
    )


@router.post("/file", status_code=202, response_model=EvaluationAccepted)
async def trigger_evaluation_file(
    meta: str = Form(...),
    results_file: UploadFile = File(...),
    session: AsyncSession = Depends(_db),
    arq: ArqRedis = Depends(_arq),
):
    try:
        req = EvaluationFileRequest.model_validate_json(meta)
    except Exception as e:
        raise HTTPException(422, f"Invalid meta JSON: {e}") from e

    settings = get_settings()
    max_bytes = settings.file_ingestion.max_file_size_mb * 1024 * 1024
    content = await results_file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(413, "File exceeds maximum allowed size")

    text = content.decode("utf-8", errors="replace")

    # Parse file inline (no path needed)
    from app.modules.quality_gate.parsers.csv_parser import parse_csv
    from app.modules.quality_gate.parsers.jmeter_parser import parse_jmeter
    if req.results_format == "csv":
        metrics = parse_csv(text)
    elif req.results_format == "jmeter":
        metrics = parse_jmeter(text)
    else:
        raise HTTPException(400, f"Unsupported results_format: {req.results_format}")

    ev = await service.trigger_evaluation(
        session=session,
        arq_redis=arq,
        name=req.name,
        start=req.start,
        end=req.end,
        asset_name=req.asset_name,
        assets=[],
        slo_name=req.slo_name,
        slo_yaml_inline=req.slo_yaml,
        datasource=None,
        metrics=metrics,
        results_path=None,
        results_format=None,
        metadata=req.metadata,
        async_mode=False,
    )
    return EvaluationAccepted(eval_id=ev.id, status_url=f"/evaluations/{ev.id}")


@router.get("", response_model=list[EvaluationOut])
async def list_evaluations(
    name: str | None = None,
    result: str | None = None,
    from_: str | None = None,
    to: str | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(_db),
):
    from datetime import datetime
    from app.cache.redis import hash_filter
    key = make_cache_key("evals", "list", hash_filter(
        name=name, result=result, from_=from_, to=to, limit=limit, offset=offset
    ))
    cached = await cache_get(key)
    if cached:
        return cached

    repo = EvaluationRepository(session)
    evals = await repo.list_evaluations(
        name=name, result=result,
        from_=datetime.fromisoformat(from_) if from_ else None,
        to=datetime.fromisoformat(to) if to else None,
        limit=limit, offset=offset,
    )
    out = [EvaluationOut.model_validate(e).model_dump(mode="json") for e in evals]
    await cache_set(key, out, get_settings().cache.ttl.evaluation_list)
    return out


@router.get("/{eval_id}", response_model=EvaluationOut)
async def get_evaluation(eval_id: uuid.UUID, session: AsyncSession = Depends(_db)):
    key = make_cache_key("eval", str(eval_id))
    cached = await cache_get(key)
    if cached:
        return cached

    repo = EvaluationRepository(session)
    ev = await repo.get(eval_id)
    if not ev:
        raise HTTPException(404, f"Evaluation {eval_id} not found")

    out = EvaluationOut.model_validate(ev).model_dump(mode="json")
    ttl = get_settings().cache.ttl.evaluation_detail
    await cache_set(key, out, ttl)
    return out


@router.patch("/{eval_id}", response_model=EvaluationOut)
async def patch_evaluation(
    eval_id: uuid.UUID,
    req: InvalidateRequest,
    session: AsyncSession = Depends(_db),
):
    await session.execute(
        update(Evaluation)
        .where(Evaluation.id == eval_id)
        .values(invalidated=req.invalidated, invalidation_note=req.invalidation_note)
    )
    await cache_delete_pattern(make_cache_key("eval", str(eval_id)))
    await cache_delete_pattern("evals:list:*")
    repo = EvaluationRepository(session)
    ev = await repo.get(eval_id)
    if not ev:
        raise HTTPException(404)
    return EvaluationOut.model_validate(ev)


@router.post("/{eval_id}/rerun", status_code=202, response_model=EvaluationAccepted)
async def rerun_evaluation(
    eval_id: uuid.UUID,
    req: RerunRequest,
    session: AsyncSession = Depends(_db),
    arq: ArqRedis = Depends(_arq),
):
    await execute_rerun(
        eval_id=eval_id,
        mode=RerunMode(req.mode),
        reason=req.reason,
        triggered_by=req.triggered_by,
        session=session,
        arq_redis=arq,
    )
    return EvaluationAccepted(eval_id=eval_id, status_url=f"/evaluations/{eval_id}")


@router.post("/{eval_id}/annotations", status_code=201, response_model=AnnotationOut)
async def add_annotation(
    eval_id: uuid.UUID,
    req: AnnotationRequest,
    session: AsyncSession = Depends(_db),
):
    repo = EvaluationRepository(session)
    ev = await repo.get(eval_id)
    if not ev:
        raise HTTPException(404)
    ann = await repo.add_annotation(
        eval_id, content=req.content, author=req.author,
        category=req.category, meta=req.meta,
    )
    await cache_delete_pattern(make_cache_key("eval", str(eval_id)))
    return AnnotationOut.model_validate(ann)


@router.get("/{eval_id}/annotations", response_model=list[AnnotationOut])
async def list_annotations(eval_id: uuid.UUID, session: AsyncSession = Depends(_db)):
    repo = EvaluationRepository(session)
    ev = await repo.get(eval_id)
    if not ev:
        raise HTTPException(404)
    return [AnnotationOut.model_validate(a) for a in ev.annotations]


@router.delete("/{eval_id}/annotations/{ann_id}", status_code=204)
async def delete_annotation(
    eval_id: uuid.UUID,
    ann_id: uuid.UUID,
    session: AsyncSession = Depends(_db),
):
    repo = EvaluationRepository(session)
    deleted = await repo.delete_annotation(ann_id)
    if not deleted:
        raise HTTPException(404)
    await cache_delete_pattern(make_cache_key("eval", str(eval_id)))
```

- [ ] Wire into main.py

```python
# app/main.py (updated)
from fastapi import FastAPI
from app.modules.slo_registry.router import router as slo_router
from app.modules.quality_gate.router import router as eval_router

app = FastAPI(title="Quality Gate API", version="0.1.0")
app.include_router(slo_router)
app.include_router(eval_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] Commit

```bash
git add .
git commit -m "feat: evaluations router with all ingestion modes, annotations, and rerun"
```

---

### Task 5.4: Trend Router and File Parsers

**Files:**
- Create: `quality-gate-api/app/modules/quality_gate/parsers/__init__.py`
- Create: `quality-gate-api/app/modules/quality_gate/parsers/csv_parser.py`
- Create: `quality-gate-api/app/modules/quality_gate/parsers/jmeter_parser.py`
- Create: `quality-gate-api/app/trend/__init__.py`
- Create: `quality-gate-api/app/trend/router.py`
- Create: `quality-gate-api/tests/parsers/test_csv_parser.py`
- Create: `quality-gate-api/tests/parsers/test_jmeter_parser.py`

- [ ] Implement CSV parser

```python
# app/modules/quality_gate/parsers/csv_parser.py
from __future__ import annotations

import csv
import io


def parse_csv(content: str) -> dict[str, float | None]:
    """Parse CSV with columns: metric_name, value, aggregation.
    Returns {metric_name: value} dict.
    """
    reader = csv.DictReader(io.StringIO(content.strip()))
    result: dict[str, float | None] = {}
    for row in reader:
        name = row.get("metric_name", "").strip()
        val_str = row.get("value", "").strip()
        if not name:
            continue
        try:
            result[name] = float(val_str)
        except (ValueError, TypeError):
            result[name] = None
    return result
```

- [ ] Implement JMeter parser

```python
# app/modules/quality_gate/parsers/jmeter_parser.py
from __future__ import annotations

import xml.etree.ElementTree as ET
from statistics import mean, quantiles


def parse_jmeter(content: str) -> dict[str, float | None]:
    """Parse JMeter .jtl XML and extract standard HTTP metrics."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return {}

    # Collect all sample elements
    samples = root.findall(".//httpSample") + root.findall(".//sample")
    if not samples:
        return {}

    elapsed_times: list[float] = []
    errors = 0
    total = len(samples)
    bytes_list: list[float] = []

    for s in samples:
        elapsed = s.get("t")
        success = s.get("s", "true").lower()
        nb = s.get("by", "0")
        if elapsed:
            elapsed_times.append(float(elapsed))
        if success == "false":
            errors += 1
        try:
            bytes_list.append(float(nb))
        except ValueError:
            pass

    if not elapsed_times:
        return {}

    elapsed_times.sort()

    def pct(lst: list[float], p: float) -> float:
        idx = int(len(lst) * p / 100)
        return lst[min(idx, len(lst) - 1)]

    duration_s = sum(elapsed_times) / 1000  # approx test duration in seconds

    return {
        "response_time_avg": mean(elapsed_times),
        "response_time_p90": pct(elapsed_times, 90),
        "response_time_p95": pct(elapsed_times, 95),
        "response_time_p99": pct(elapsed_times, 99),
        "error_rate": errors / total if total else 0.0,
        "throughput_rps": total / duration_s if duration_s > 0 else 0.0,
        "bytes_per_second": sum(bytes_list) / duration_s if duration_s > 0 else 0.0,
    }
```

- [ ] Write tests for parsers

```python
# tests/parsers/test_csv_parser.py
from app.modules.quality_gate.parsers.csv_parser import parse_csv


def test_parse_valid_csv() -> None:
    csv = "metric_name,value,aggregation\nresponse_time_p99,450.3,p99\nerror_rate,0.02,avg\n"
    result = parse_csv(csv)
    assert result["response_time_p99"] == 450.3
    assert result["error_rate"] == 0.02


def test_parse_missing_value_returns_none() -> None:
    csv = "metric_name,value,aggregation\nbad_metric,,avg\n"
    result = parse_csv(csv)
    assert result["bad_metric"] is None


def test_parse_empty_returns_empty() -> None:
    assert parse_csv("") == {}
```

```python
# tests/parsers/test_jmeter_parser.py
from app.modules.quality_gate.parsers.jmeter_parser import parse_jmeter

JMETER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<testResults version="1.2">
  <httpSample t="450" s="true" lb="GET /" by="1024"/>
  <httpSample t="500" s="true" lb="GET /" by="2048"/>
  <httpSample t="600" s="false" lb="POST /api" by="256"/>
</testResults>"""


def test_parse_jmeter_returns_metrics() -> None:
    result = parse_jmeter(JMETER_XML)
    assert "response_time_avg" in result
    assert "error_rate" in result
    assert abs(result["error_rate"] - (1/3)) < 0.01


def test_parse_invalid_xml_returns_empty() -> None:
    result = parse_jmeter("not xml at all")
    assert result == {}
```

- [ ] Create trend router

```python
# app/trend/router.py
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis import cache_get, cache_set, make_cache_key, hash_filter
from app.config import get_settings
from app.db.session import get_session as _get_session
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.slo_registry.schemas import TrendPoint

router = APIRouter(prefix="/trend", tags=["Trend"])


async def _db():
    async with _get_session() as session:
        yield session


@router.get("", response_model=list[TrendPoint])
async def get_trend(
    test_name: str,
    metric: str,
    asset_name: str | None = None,
    from_: str | None = None,
    to: str | None = None,
    result_filter: str | None = None,
    session: AsyncSession = Depends(_db),
):
    settings = get_settings()
    result_list = result_filter.split(",") if result_filter else None

    key = make_cache_key("trend", hash_filter(
        test_name=test_name, metric=metric, asset_name=asset_name,
        from_=from_, to=to, result_filter=result_filter
    ))
    cached = await cache_get(key)
    if cached:
        return cached

    repo = EvaluationRepository(session)
    points = await repo.get_trend(
        test_name=test_name,
        metric_name=metric,
        asset_name=asset_name,
        from_=datetime.fromisoformat(from_) if from_ else None,
        to=datetime.fromisoformat(to) if to else None,
        result_filter=result_list,
    )
    await cache_set(key, points, settings.cache.ttl.trend)
    return points
```

- [ ] Wire trend router into main.py

```python
from app.trend.router import router as trend_router
app.include_router(trend_router)
```

- [ ] Run all tests

```bash
uv run pytest tests/ -v --ignore=tests/api/
```

Expected: all unit tests pass.

- [ ] Commit

```bash
git add .
git commit -m "feat: trend endpoint, CSV and JMeter file parsers"
```

---

### Task 5.5: Full-Flow Integration Tests

> **These are the Python equivalent of Go's `TestEvaluateSLIHandler_HandleEvent`.**
> They test the complete HTTP path: API request → validation → job enqueue → evaluation engine → DB write → result retrieval.
> Unlike unit tests, these require real TimescaleDB + Redis running.

**Files:**
- Create: `api/tests/integration/__init__.py`
- Create: `api/tests/integration/conftest.py`
- Create: `api/tests/integration/test_evaluation_flow.py`

- [ ] Add integration marker to `api/pyproject.toml`

Add under `[tool.pytest.ini_options]`:
```toml
markers = [
    "integration: marks tests requiring real DB + Redis (deselect with -m 'not integration')",
]
```

- [ ] Create `api/tests/integration/conftest.py`

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.session import get_session


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
async def clean_db():
    yield
    async with get_session() as session:
        await session.execute(
            "TRUNCATE evaluations, slo_definitions, evaluation_annotations, sli_values CASCADE"
        )
```

- [ ] Create `api/tests/integration/test_evaluation_flow.py`

Scenarios to cover — each maps to a Go test case:

| Test | Go equivalent | What it verifies |
|---|---|---|
| `test_push_mode_pass` | `TestEvaluateObjectives` (pass branch) | Full HTTP → engine → DB → result=pass |
| `test_push_mode_fail_key_sli` | `TestCalculateScore` (key_sli) | key_sli=true fail overrides 99% score |
| `test_push_mode_warning` | `TestEvaluateObjectives` (warning branch) | warning result stored and returned |
| `test_inline_slo_works` | `TestEvaluateSLIHandler_HandleEvent` | slo_yaml inline, no registry needed |
| `test_invalidation_flag_persists` | `TestEvaluateSLIHandler_HandleEvent` | PATCH sets invalidated=true |
| `test_annotation_stored_on_evaluation` | N/A (new feature) | annotation visible in GET response |
| `test_slo_version_recorded` | N/A (new feature) | latest SLO version stamped on evaluation |
| `test_csv_file_mode_pass` | N/A (new feature) | multipart CSV → correct metric values |
| `test_relative_criteria_with_history` | `TestEvaluateComparison` | second eval uses first as baseline |
| `test_slo_registry_versioning` | N/A | PUT creates v2, evaluations use latest |

```python
import asyncio
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

SIMPLE_SLO = """spec_version: '1.0'
indicators:
  latency: 'unused_in_push_mode'
objectives:
  - sli: latency
    pass:
      - criteria: ["<500"]
    weight: 1
    key_sli: false
total_score:
  pass: "90%"
  warning: "75%"
"""


async def _wait_completed(client: AsyncClient, eval_id: str, timeout: int = 20) -> dict:
    for _ in range(timeout):
        r = await client.get(f"/evaluations/{eval_id}")
        if r.json()["status"] == "completed":
            return r.json()
        await asyncio.sleep(0.2)
    raise TimeoutError(f"Evaluation {eval_id} did not complete in time")


async def test_push_mode_pass(client: AsyncClient) -> None:
    await client.post("/slos", json={"name": "latency-slo", "slo_yaml": SIMPLE_SLO})
    resp = await client.post("/evaluations", json={
        "name": "api-test", "start": "2026-03-12T10:00:00Z", "end": "2026-03-12T10:30:00Z",
        "slo_name": "latency-slo", "metrics": {"latency": 400.0}, "metadata": {"os": "linux"},
    })
    assert resp.status_code == 202
    result = await _wait_completed(client, resp.json()["eval_id"])
    assert result["result"] == "pass"
    assert result["score"] == 100.0
    assert result["indicator_results"][0]["status"] == "pass"


async def test_push_mode_fail_key_sli(client: AsyncClient) -> None:
    key_slo = SIMPLE_SLO.replace("key_sli: false", "key_sli: true")
    await client.post("/slos", json={"name": "key-slo", "slo_yaml": key_slo})
    resp = await client.post("/evaluations", json={
        "name": "key-test", "start": "2026-03-12T10:00:00Z", "end": "2026-03-12T10:30:00Z",
        "slo_name": "key-slo", "metrics": {"latency": 999.0}, "metadata": {},
    })
    result = await _wait_completed(client, resp.json()["eval_id"])
    assert result["result"] == "fail"


async def test_push_mode_warning(client: AsyncClient) -> None:
    warn_slo = SIMPLE_SLO.replace(
        'criteria: ["<500"]',
        'criteria: ["<300"]\n    warning:\n      - criteria: ["<600"]',
    ).replace('pass: "90%"', 'pass: "100%"')
    await client.post("/slos", json={"name": "warn-slo", "slo_yaml": warn_slo})
    resp = await client.post("/evaluations", json={
        "name": "warn-test", "start": "2026-03-12T10:00:00Z", "end": "2026-03-12T10:30:00Z",
        "slo_name": "warn-slo", "metrics": {"latency": 450.0}, "metadata": {},
    })
    result = await _wait_completed(client, resp.json()["eval_id"])
    assert result["result"] == "warning"


async def test_inline_slo_no_registry(client: AsyncClient) -> None:
    resp = await client.post("/evaluations", json={
        "name": "inline-test", "start": "2026-03-12T10:00:00Z", "end": "2026-03-12T10:30:00Z",
        "slo_yaml": SIMPLE_SLO, "metrics": {"latency": 400.0}, "metadata": {},
    })
    result = await _wait_completed(client, resp.json()["eval_id"])
    assert result["result"] == "pass"
    assert result["slo_name"] is None  # inline, not registered


async def test_invalidation_flag_persists(client: AsyncClient) -> None:
    await client.post("/slos", json={"name": "inv-slo", "slo_yaml": SIMPLE_SLO})
    resp = await client.post("/evaluations", json={
        "name": "inv-test", "start": "2026-03-12T10:00:00Z", "end": "2026-03-12T10:30:00Z",
        "slo_name": "inv-slo", "metrics": {"latency": 400.0}, "metadata": {},
    })
    eval_id = resp.json()["eval_id"]
    await _wait_completed(client, eval_id)
    await client.patch(f"/evaluations/{eval_id}", json={
        "invalidated": True, "invalidation_note": "known issue",
    })
    detail = (await client.get(f"/evaluations/{eval_id}")).json()
    assert detail["invalidated"] is True
    assert detail["invalidation_note"] == "known issue"


async def test_annotation_stored_on_evaluation(client: AsyncClient) -> None:
    await client.post("/slos", json={"name": "ann-slo", "slo_yaml": SIMPLE_SLO})
    resp = await client.post("/evaluations", json={
        "name": "ann-test", "start": "2026-03-12T10:00:00Z", "end": "2026-03-12T10:30:00Z",
        "slo_name": "ann-slo", "metrics": {"latency": 400.0}, "metadata": {},
    })
    eval_id = resp.json()["eval_id"]
    await _wait_completed(client, eval_id)
    await client.post(f"/evaluations/{eval_id}/annotations", json={
        "content": "Kernel updated", "category": "environment", "author": "ops",
    })
    detail = (await client.get(f"/evaluations/{eval_id}")).json()
    assert len(detail["annotations"]) == 1
    assert detail["annotations"][0]["content"] == "Kernel updated"


async def test_slo_version_stamped_on_evaluation(client: AsyncClient) -> None:
    await client.post("/slos", json={"name": "ver-slo", "slo_yaml": SIMPLE_SLO})
    await client.put("/slos/ver-slo", json={"slo_yaml": SIMPLE_SLO, "notes": "v2"})
    resp = await client.post("/evaluations", json={
        "name": "ver-test", "start": "2026-03-12T10:00:00Z", "end": "2026-03-12T10:30:00Z",
        "slo_name": "ver-slo", "metrics": {"latency": 400.0}, "metadata": {},
    })
    result = await _wait_completed(client, resp.json()["eval_id"])
    assert result["slo_version"] == 2


async def test_csv_file_mode_pass(client: AsyncClient) -> None:
    csv_slo = SIMPLE_SLO.replace("latency", "throughput_mbps").replace("<500", ">500")
    await client.post("/slos", json={"name": "csv-slo", "slo_yaml": csv_slo})
    csv_content = "metric_name,value,aggregation\nthroughput_mbps,945.3,avg\n"
    resp = await client.post(
        "/evaluations/file",
        data={"meta": (
            '{"name":"csv-test","start":"2026-03-12T09:00:00Z",'
            '"end":"2026-03-12T09:20:00Z","slo_name":"csv-slo",'
            '"results_format":"csv","metadata":{}}'
        )},
        files={"results_file": ("results.csv", csv_content.encode(), "text/csv")},
    )
    assert resp.status_code == 202
    result = await _wait_completed(client, resp.json()["eval_id"])
    assert result["result"] == "pass"


async def test_relative_criteria_uses_previous_evaluation_as_baseline(
    client: AsyncClient,
) -> None:
    """Matches Go's TestEvaluateComparison — second evaluation uses first as baseline."""
    rel_slo = """spec_version: '1.0'
comparison:
  compare_with: several_results
  number_of_comparison_results: 1
  include_result_with_score: pass
  aggregate_function: avg
  scope_tags: [os]
indicators:
  latency: 'unused'
objectives:
  - sli: latency
    pass:
      - criteria: ["<=+10%"]
    weight: 1
total_score:
  pass: "90%"
  warning: "75%"
"""
    await client.post("/slos", json={"name": "rel-slo", "slo_yaml": rel_slo})

    # First evaluation — baseline value 400ms
    resp1 = await client.post("/evaluations", json={
        "name": "rel-test", "start": "2026-03-11T10:00:00Z", "end": "2026-03-11T10:30:00Z",
        "slo_name": "rel-slo", "metrics": {"latency": 400.0}, "metadata": {"os": "linux"},
    })
    await _wait_completed(client, resp1.json()["eval_id"])

    # Second evaluation — 430ms is within +10% of 400ms → should pass
    resp2 = await client.post("/evaluations", json={
        "name": "rel-test", "start": "2026-03-12T10:00:00Z", "end": "2026-03-12T10:30:00Z",
        "slo_name": "rel-slo", "metrics": {"latency": 430.0}, "metadata": {"os": "linux"},
    })
    result2 = await _wait_completed(client, resp2.json()["eval_id"])
    assert result2["result"] == "pass"
    rt = result2["indicator_results"][0]
    assert rt["compared_value"] == 400.0
    assert rt["change_relative_pct"] == pytest.approx(7.5)
```

- [ ] Run unit tests unaffected

```bash
uv run pytest tests/ -m "not integration" -q
```

Expected: all existing tests still pass.

- [ ] Run integration tests (requires infrastructure)

```bash
docker compose up timescaledb redis -d
uv run alembic upgrade head
uv run pytest tests/integration/ -v -m integration
```

- [ ] Commit

```bash
git add .
git commit -m "test: full-flow integration tests — Python equivalent of Go TestEvaluateSLIHandler_HandleEvent"
```
