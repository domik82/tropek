# Evaluation Write Architecture

How the worker pipeline writes evaluation results to the database. Documents the
current multi-phase, micro-transaction design that prevents deadlocks under concurrent load.

## Context

Each evaluation batch triggers up to 240 arq jobs (12 assets x 20 SLOs). With
`max_jobs=10` per worker and 4 worker replicas, up to 40 jobs execute concurrently.
All jobs write to interrelated tables with foreign key constraints, and `sli_values`
is a TimescaleDB hypertable with chunk-level locking.

The core invariant: **no DB transaction may span an HTTP call or hold locks longer
than ~15ms**.

## Tables and FK relationships

```
evaluations (EvaluationRun — parent)
  ▲
  │ FK: slo_evaluations.evaluation_id
  │
slo_evaluations (SLOEvaluation — one per asset+SLO)
  ▲                          ▲
  │ FK: indicator_results    │ FK: sli_values
  │     .evaluation_id       │     .slo_evaluation_id
  │                          │
indicator_results            sli_values (TimescaleDB hypertable)
```

Key lock interactions:
- `UPDATE slo_evaluations` takes a **row exclusive lock** on that row.
- `INSERT INTO indicator_results` takes a **shared FK lock** on the parent `slo_evaluations` row.
- `INSERT INTO sli_values` takes a **shared FK lock** on `slo_evaluations` AND a
  **ShareUpdateExclusiveLock** on the TimescaleDB time chunk (self-conflicting).

## Job lifecycle — `run_evaluation_job`

Orchestrated in `api/app/queue.py`, with phase functions in
`api/app/modules/quality_gate/worker.py`.

```
                        ┌─────────────────────────────────────────────┐
                        │         run_evaluation_job (arq job)        │
                        └─────────────────────────────────────────────┘

 ┌──────────────┐  ┌──────────────┐  ┌─────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐
 │  Session 1   │  │  Session 2   │  │ No DB   │  │  Session 3   │  │  Session 4   │  │  Session 5  │
 │  Phase 1     │  │  Phase 2a    │  │ HTTP IO │  │  Phase 2b    │  │  Phase 3a    │  │  Phase 3b   │
 │  ~5ms        │  │  ~10ms       │  │ 1-10s   │  │  ~10ms       │  │  ~10ms       │  │  ~10ms      │
 │              │  │              │  │         │  │              │  │              │  │             │
 │ mark_running │  │ load SLO def │  │ query   │  │ resolve      │  │ mark_        │  │ INSERT      │
 │ snapshot     │  │ load SLI def │  │ adapter │  │ baselines    │  │ completed    │  │ sli_values  │
 │              │  │ load datasrc │  │         │  │              │  │ INSERT       │  │             │
 │ COMMIT       │  │ COMMIT       │  │         │  │ COMMIT       │  │ indicators   │  │ COMMIT      │
 │              │  │              │  │         │  │              │  │ COMMIT       │  │             │
 └──────────────┘  └──────────────┘  └─────────┘  └──────────────┘  └──────────────┘  └─────────────┘
        │                                                                                    │
        │                          snapshot (Pydantic model)                                  │
        └────────────────── carried across all phases as detached data ───────────────────────┘
```

### Phase 1 — Mark running + snapshot

```python
async with session_factory() as session:
    snapshot = await load_evaluation_snapshot(session, eval_id, worker_id=...)
    await session.commit()
```

**Writes**: `UPDATE slo_evaluations SET status='running' WHERE id=X`
**Locks**: Row exclusive on one `slo_evaluations` row. Released on COMMIT (~5ms).
**Output**: `EvaluationSnapshot` — a Pydantic model with all fields copied from the ORM row.
No SQLAlchemy objects are carried past this point.

### Phase 2a — Load definitions

```python
async with session_factory() as session:
    slo_def, sli_def = await _load_definitions(session, snapshot, cache=cache)
    datasource = await DataSourceRepository(session).get_by_name(snapshot.data_source_name)
    await session.commit()
```

**Writes**: None (read-only).
**Locks**: None meaningful.
**Output**: ORM definition objects (`SLODefinition`, `SLIDefinition`, `DataSource`).

### HTTP adapter query (no DB session)

```python
adapter_client = HttpAdapterClient(timeout=..., http_client=ctx['http_client'])
```

The adapter HTTP call (1-10 seconds) happens with **no open DB session and no locks held**.
Uses a shared `httpx.AsyncClient` per worker process (connection pooling).

### Phase 2b — Resolve baselines + evaluate

```python
async with session_factory() as session:
    baseline_repo = BaselineRepository(session, cache=cache)
    fetch_result = await fetch_and_evaluate(snapshot=..., ...)
    await session.commit()
```

**Writes**: None (read-only baseline queries + pure `evaluate()` computation).
**Output**: `FetchAndEvaluateResult` — metrics, baselines, scored result.

### Phase 3a — Write evaluation result + indicator rows

```python
async with session_factory() as session:
    await write_results(session=session, snapshot=..., slo_def=..., fetch_result=...)
    await session.commit()
```

**Writes**:
1. `UPDATE slo_evaluations SET status='completed', result=..., score=...` — marks this eval done.
2. `INSERT INTO indicator_results` — one row per SLI indicator (~8 rows).

**Locks held simultaneously**:
- Row exclusive lock on this `slo_evaluations` row (from UPDATE).
- Shared FK lock on the parent `evaluations` row (FK check on UPDATE).
- Shared FK lock on `slo_objectives` rows (from indicator INSERT).

**Duration**: ~10ms. Released on COMMIT.

**What is NOT here**: No `sli_values` INSERT. This is deliberate — see below.

### Phase 3b — Write SLI values to hypertable

```python
async with session_factory() as session:
    await write_sli_values_phase(session=..., snapshot=..., sli_def=..., fetch_result=...)
    await session.commit()
```

**Writes**: `INSERT INTO sli_values` — one row per indicator (~8 rows).

**Locks held simultaneously**:
- Shared FK lock on the `slo_evaluations` row (FK check — shared, not exclusive).
- `ShareUpdateExclusiveLock` on the TimescaleDB time chunk.

**Duration**: ~10ms. Released on COMMIT.

### Finalize — deduped arq job

```python
await pool.enqueue_job('finalize_run_job', str(parent_run_id))
```

Separate arq job, one per completing child. Each child enqueues its own finalize
attempt without deduplication — `finalize_if_all_done` is idempotent, so
multiple executions are safe and only the last one (when all children are done)
actually marks the parent as completed.

```python
async with session_factory() as session:
    finalized = await run_repo.finalize_if_all_done(run_id)
    await session.commit()
```

## Why Phase 3 is split into 3a and 3b

The deadlock that required the split:

```
Worker A (Phase 3, combined):
  UPDATE slo_evaluations SET status='completed'   → row exclusive lock on eval row A
  INSERT INTO sli_values (slo_evaluation_id=A)     → needs chunk lock, WAITS

Worker B (Phase 3, combined):
  UPDATE slo_evaluations SET status='completed'   → row exclusive lock on eval row B
  INSERT INTO sli_values (slo_evaluation_id=B)     → holds chunk lock (same time chunk),
                                                     needs FK shared lock on eval row B (OK),
                                                     but chunk lock conflicts → DEADLOCK CYCLE
```

The problem: `UPDATE slo_evaluations` (row exclusive) + `INSERT sli_values` (chunk lock +
FK shared lock) in the **same transaction** creates a lock ordering conflict when multiple
workers target the same TimescaleDB time chunk.

The fix: separate them into two transactions so **row exclusive locks and chunk locks are
never held simultaneously**.

In Phase 3a, `mark_completed` holds a row exclusive lock but no chunk lock.
In Phase 3b, `INSERT sli_values` holds a chunk lock and a shared FK lock (not exclusive).
Shared FK locks don't conflict with each other, so concurrent Phase 3b transactions can
queue for the chunk lock without deadlocking.

## Consistency guarantee

Phase 3a commits before Phase 3b starts. If Phase 3b fails (process crash, timeout),
the evaluation is marked `completed` with indicator results but missing `sli_values` rows.

This is acceptable because:
- `sli_values` is a denormalized analytics table (heatmaps, trend charts).
- The authoritative result lives in `slo_evaluations.result` + `indicator_results`.
- A re-run of the evaluation will overwrite the `sli_values` rows.

If stronger consistency is needed in the future, Phase 3b could be made idempotent with
`ON CONFLICT DO UPDATE` and a reconciliation job that retries failed SLI writes.

## Error handling

All failure paths use `_mark_failed()` — a helper that opens its own session, marks the
evaluation as failed with error details in `job_stats`, and commits.

```python
async def _mark_failed(session_factory, eval_id, error):
    async with session_factory() as session:
        await EvaluationRepository(session).mark_failed(eval_id, job_stats={'error': error})
        await session.commit()
```

Failure points and their handling:
- **Phase 1** returns `None` (eval not found or already processed) → early return, no mark_failed.
- **Phase 2a** definition not found → `_mark_failed` + return.
- **HTTP adapter** error (connect, timeout, HTTP status) → `fetch_and_evaluate` returns `None` → `_mark_failed` + return.
- **Phase 3a/3b** are expected to succeed (data already validated). On unexpected DB error,
  the arq retry mechanism handles it.

## Predecessor deferral

Before Phase 1, the job checks if an earlier evaluation for the same asset+SLO is still
pending or running:

```python
if await _has_pending_predecessor(session_factory, eval_id):
    await pool.enqueue_job('run_evaluation_job', eval_id_str, defer_count + 1,
                           _defer_by=timedelta(seconds=2))
    return
```

This serializes evaluations within a single asset+SLO pair so that baseline comparisons
are consistent — a newer evaluation should compare against the completed result of the
previous period, not a still-running one. Max 60 deferrals (2 minutes).

## Files

| File | Role |
|------|------|
| `api/app/queue.py` | Job orchestration: `run_evaluation_job`, `finalize_run_job`, `_mark_failed`, worker lifecycle |
| `api/app/modules/quality_gate/worker.py` | Phase functions: `load_evaluation_snapshot`, `fetch_and_evaluate`, `write_results`, `write_sli_values_phase` |
| `api/app/modules/quality_gate/worker.py` | Data models: `EvaluationSnapshot`, `FetchAndEvaluateResult` |
| `api/app/db/models.py` | ORM: `SLOEvaluation` (FK→`evaluations`), `SLIValue` (FK→`slo_evaluations`, hypertable) |
| `config.yaml` | `queue.max_jobs`, `reliability.adapter_timeout_seconds` |
