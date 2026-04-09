# Finalize Sweeper — Robust Parent Run Completion

**Status:** Draft
**Date:** 2026-04-09
**Area:** `api/app/queue.py`, `api/app/modules/quality_gate/evaluation_run_repository.py`

## Background

`EvaluationRun` is the parent aggregate of a quality-gate evaluation. Each parent
has one or more `SLOEvaluation` children. A parent is considered `completed` when
every child is in a terminal state (`completed` or `failed`) and its aggregated
result has been written to the parent row.

The system currently drives that transition via an arq job
(`finalize_run_job`) enqueued by each child worker right after it commits its
own result. The fast path is:

```
child_worker: write child result -> COMMIT
            : enqueue finalize_run_job
finalize_run_job: open fresh session -> finalize_if_all_done -> COMMIT
```

### History

Two prior bugs shaped the current design, and both constrain the solution space
for this work:

1. **Rollup deadlock** (`docs/bug-evaluation-run-rollup-deadlock.md`). When the
   parent `UPDATE evaluations` ran inside the same transaction as the child
   `UPDATE slo_evaluation`, two concurrent child workers would both hold
   `FOR KEY SHARE` on the parent row (from the FK
   `slo_evaluation.evaluation_id -> evaluations.id`) and then both try to
   upgrade to `FOR NO KEY UPDATE` for the parent update — forming a classic
   lock-upgrade cycle. Fixed by moving the parent update into a separate
   transaction that opens *after* the child commit.

2. **Finalize dedup trap** (`docs/fixes_for_evaluation.patch`). The arq
   finalize job was enqueued with `_job_id=f'finalize:{parent_run_id}'` to
   dedupe per parent. Because arq persists a result key for a `_job_id` after
   the first execution regardless of whether the job did real work, the first
   child to enqueue `finalize_if_all_done` would see siblings still running,
   return `None`, and leave behind a result key that blocked all later children
   from re-enqueueing. If no further child ever triggered another attempt, the
   parent would sit in `pending` forever. Fixed by removing `_job_id`, relying
   on `finalize_if_all_done` idempotency, and accepting N finalize jobs per
   run of N children.

Both fixes are in place. This spec does not revisit them; it *adds* a safety
net so that any future failure of the fast path (worker SIGKILL between commit
and enqueue, Redis losing the queued job, transient DB errors exhausting arq
retries, manual DB surgery, new worker bugs) is self-healing rather than
permanent.

## Goals

- **No stuck runs.** Any parent whose children are all terminal must eventually
  be finalized, regardless of whether the fast-path enqueue succeeded.
- **No deadlocks at 24-wide child concurrency.** The reconciler must not
  reintroduce any form of the rollup deadlock or create new lock cycles with
  in-flight child evaluations or the existing arq finalize job.
- **Observable.** A non-zero rescue count is the canary for a new bug in the
  fast path. It must be visible without digging.
- **Minimal new concepts.** Stay within the existing stack — Postgres, arq,
  Redis. No triggers, no workflow engine, no outbox.

## Non-Goals

- Replacing the existing arq finalize job with inline finalize. Inline would
  work but sacrifices arq's automatic retry of transient DB failures and
  tightens the latency of the worker path. The user has explicitly chosen to
  keep the arq job.
- Changing any existing `finalize_if_all_done` semantics. The reconciler
  reuses the existing method as-is.
- Repairing already-stuck data. A one-shot repair query exists in
  `docs/bug-evaluation-run-rollup-deadlock.md` and can be run manually once
  the sweeper is live.

## Architecture

The fast path stays unchanged. A periodic arq cron job — `finalize_sweeper_job`
— runs on a configurable interval and scans for parent runs whose children
are all terminal but whose own status is still `pending` or `running`. For
each one, it calls the existing `finalize_if_all_done` in a fresh session.

### Mental model

- **Arq finalize job** = optimization. Happy path, ≤1s latency.
- **Sweeper** = correctness guarantee. Worst-case latency = one sweeper
  interval.
- Both call the same idempotent `finalize_if_all_done`.
- The sweeper's "rescued run" log line is the first-class signal that a new
  bug has been introduced on the fast path.

### Why this is deadlock-safe at 24-wide concurrency

The reconciler opens a fresh session that has never touched any child row.
It therefore never holds `FOR KEY SHARE` on the parent and never needs a lock
upgrade. Its `UPDATE evaluations` statement takes `FOR NO KEY UPDATE` cold.

From the Postgres row-lock compatibility matrix, `FOR NO KEY UPDATE` does not
conflict with `FOR KEY SHARE`. Concrete consequences:

- **Sweeper vs. live children.** The sweeper can update the parent row even
  while all 24 children concurrently hold `FOR KEY SHARE` on it from their
  child updates. No waiting, no cycle.
- **Sweeper vs. arq finalize job.** Both run in fresh sessions, both issue
  the same `FOR NO KEY UPDATE`. They serialize single-file on the row. The
  loser sees `status='completed'` and no-ops.
- **Two sweeper ticks in parallel** (hypothetical — arq cron is coordinated
  cluster-wide via Redis, so this shouldn't actually happen). Same shape as
  the previous case. Pure serialization, no cycle possible because neither
  tick holds any lock the other wants.

The prior deadlock was only possible because the parent update and the child
update shared a transaction. Any design where the parent update happens in a
transaction that never touched a child is deadlock-safe by construction.

### Why arq cron is safe across multiple worker instances

When the scheduled time arrives, every running worker computes the same
deterministic `job_id` for the tick (function name + scheduled timestamp) and
tries to enqueue with that id. Redis makes the first enqueue succeed and the
rest no-op. Exactly one worker then dequeues and runs the tick.

This is the same `_job_id` dedup mechanism that broke `finalize_run_job`. It
is safe here because each tick gets a *different* job id (the timestamp is
baked in), so a lingering result key from tick T cannot block tick T+1.

## Components

### 1. `EvaluationRunRepository.find_finalizable_pending_ids`

New read-only method on
`api/app/modules/quality_gate/evaluation_run_repository.py`.

```python
async def find_finalizable_pending_ids(self, *, limit: int) -> list[uuid.UUID]:
    """Return IDs of parent runs whose children are all terminal but whose own
    status is not yet 'completed'. Ordered by period_end ASC so the oldest
    stuck runs are rescued first. Takes no locks.
    """
```

Underlying SQL:

```sql
SELECT e.id
  FROM evaluations e
 WHERE e.status != 'completed'
   AND EXISTS (
         SELECT 1 FROM slo_evaluations se
          WHERE se.evaluation_id = e.id
       )
   AND NOT EXISTS (
         SELECT 1 FROM slo_evaluations se
          WHERE se.evaluation_id = e.id
            AND se.status IN ('pending','running','partial')
       )
 ORDER BY e.period_end ASC
 LIMIT :limit;
```

The inner `EXISTS` skips parents with zero children — those are runs that
crashed before fan-out and are not the sweeper's concern.

### 2. `finalize_sweeper_job` in `api/app/queue.py`

New arq job:

```python
async def finalize_sweeper_job(ctx: dict[str, Any]) -> None:
    """Periodic reconciler — finalizes parent runs the fast path missed."""
    settings = get_settings()
    batch_limit = settings.queue.finalize_sweeper_batch_limit
    session_factory = get_session_factory()

    started = time.monotonic()
    rescued = 0

    async with session_factory() as session:
        run_repo = EvaluationRunRepository(session)
        candidate_ids = await run_repo.find_finalizable_pending_ids(limit=batch_limit)

    for run_id in candidate_ids:
        async with session_factory() as session:
            run_repo = EvaluationRunRepository(session)
            finalized = await run_repo.finalize_if_all_done(run_id)
            await session.commit()
        if finalized is not None:
            rescued += 1
            logger.info(
                'sweeper_rescued_run',
                evaluation_id=str(run_id),
                result=finalized.result,
            )

    duration_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        'sweeper_tick',
        scanned=len(candidate_ids),
        rescued=rescued,
        duration_ms=duration_ms,
    )
```

Notes:

- Each rescue runs in its own session and its own commit so one failure does
  not roll back previous rescues.
- The scan query and the rescues are separate sessions to minimise how long
  any one session is open.
- `sweeper_tick` is logged at INFO even when `rescued=0` — it is the
  liveness signal. If log volume becomes an issue later, this is the one to
  move to DEBUG.

### 3. Cron registration in `WorkerSettings`

```python
class WorkerSettings:
    functions: ClassVar[list[Any]] = [
        run_evaluation_job,
        finalize_run_job,
        finalize_sweeper_job,
    ]
    cron_jobs: ClassVar[list[Any]] = [
        cron(finalize_sweeper_job, second=_sweeper_cron_seconds()),
    ]
    ...
```

`_sweeper_cron_seconds()` translates the configured interval into the set of
seconds-of-minute values arq cron expects:

- 5s  -> {0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}
- 10s -> {0, 10, 20, 30, 40, 50}
- 15s -> {0, 15, 30, 45}
- 20s -> {0, 20, 40}
- 30s -> {0, 30}
- 60s -> {0}

Arq cron fires on discrete second-of-minute values, so the interval must be
a divisor of 60. Any other value is a configuration error and must raise at
worker startup, not be silently rounded.

### 4. Configuration

`QueueSettings` in `api/app/config.py` gains two fields:

```python
finalize_sweeper_interval_seconds: int = _yaml.get('queue', {}).get(
    'finalize_sweeper_interval_seconds', 30
)
finalize_sweeper_batch_limit: int = _yaml.get('queue', {}).get(
    'finalize_sweeper_batch_limit', 100
)
```

A Pydantic validator on `finalize_sweeper_interval_seconds` enforces
membership in `{5, 10, 15, 20, 30, 60}`. `finalize_sweeper_batch_limit` must
be `>= 1`.

`config.yaml` documents both keys under `queue:` with their defaults and the
interval constraint.

### 5. Index for the sweeper query

The sweeper query filters on `e.status != 'completed'` and orders by
`e.period_end ASC`. A partial index matches both the filter and the order:

```sql
CREATE INDEX ix_evaluations_incomplete_period_end
    ON evaluations (period_end)
 WHERE status != 'completed';
```

Declared on the `EvaluationRun` model via
`Index(..., postgresql_where=...)` so the migration is regenerated through
the standard `scripts/db-regen-migrations.sh` workflow rather than
hand-written.

Partial-index size stays tiny in steady state (most rows are `completed` and
excluded), so the index write cost on child commits is negligible.

## Data Flow

### Happy path (unchanged)

```
child worker -> write child result (txn A)
             -> commit txn A (releases FK-SHARE on parent)
             -> enqueue finalize_run_job
finalize_run_job -> fresh session -> finalize_if_all_done -> COMMIT
```

### Rescue path (new)

```
cron tick (every N seconds, coordinated via arq Redis cron lock)
  -> one worker picks up finalize_sweeper_job
     -> find_finalizable_pending_ids(limit=100)
     -> for each candidate: finalize_if_all_done in its own session+txn
     -> log sweeper_rescued_run per success
     -> log sweeper_tick summary
```

The rescue path never touches a child row and never opens a transaction that
does anything before the parent `UPDATE`, so it cannot participate in a lock
cycle with any in-flight child transaction.

## Error Handling

- **`find_finalizable_pending_ids` raises.** Propagates out of the tick.
  Arq logs the failure and retries per its `max_tries` policy. The next tick
  will retry the scan independently.
- **A single rescue's `finalize_if_all_done` raises.** Caught by arq's
  per-job error handling only if the whole cron function raises. Because
  each rescue is in its own session/commit, we explicitly let a failure in
  one rescue abort the tick — the next tick will pick up the remaining
  candidates (ordered by `period_end` so progress is deterministic). No
  partial state is written to the DB.
- **DB connection lost mid-tick.** Same as above — tick fails, next tick
  resumes. Idempotency of `finalize_if_all_done` means retries are always
  safe.
- **Arq cron lock contention** (theoretical — shouldn't happen). Even if
  two workers both executed the tick concurrently, the Case-3 analysis
  above shows they cannot deadlock. Worst case: redundant finalize UPDATEs,
  one of which is a no-op. Harmless.

## Observability

Three structured log events (all via `structlog`, INFO unless noted):

| Event | When | Fields | Purpose |
|---|---|---|---|
| `sweeper_tick` | end of every tick | `scanned`, `rescued`, `duration_ms` | liveness heartbeat |
| `sweeper_rescued_run` | per rescued run | `evaluation_id`, `result` | canary — any occurrence means a fast-path bug |
| `parent evaluation run completed` | existing from `finalize_run_job` | `evaluation_id`, `result` | unchanged |

If Prometheus scraping of structlog is added later, the alert-worthy counter
is `sweeper_rescued_run_total`:

```
alert: FinalizeFastPathRegression
expr: increase(sweeper_rescued_run_total[1h]) > 0
for: 10m
```

## Testing

### Unit / repository tests

New tests in `api/tests/db/test_evaluation_run_repository.py`
(`@pytest.mark.integration` — hit real DB per project convention):

- `find_finalizable_pending_ids` returns a parent whose children are all
  `completed`.
- `find_finalizable_pending_ids` returns a parent whose children mix
  `completed` and `failed` (both terminal).
- `find_finalizable_pending_ids` skips a parent with one child in each of
  `pending`, `running`, `partial`.
- `find_finalizable_pending_ids` skips a parent with zero children.
- `find_finalizable_pending_ids` skips a parent already in `completed`.
- `find_finalizable_pending_ids` respects `limit`.
- `find_finalizable_pending_ids` orders by `period_end ASC`.

### Sweeper behaviour tests

New test module `api/tests/db/test_finalize_sweeper.py`:

- Empty DB / no stuck runs: tick is a no-op, logs summary with `rescued=0`.
- One stuck run: tick finalizes it, emits `sweeper_rescued_run`, parent
  becomes `completed` with the aggregated result.
- N stuck runs where N > `batch_limit`: tick rescues exactly
  `batch_limit` of them (oldest by `period_end`), leaves the rest; next
  tick finishes them.
- Stuck run + concurrent `finalize_run_job` targeting the same parent:
  both paths complete without error; parent ends up `completed` with
  consistent values. (Asserted on final state only — either order is
  acceptable.)
- Calling the sweeper when arq finalize already finalized the parent in
  the same tick: parent stays `completed`, no error, may be counted as a
  rescue (acceptable noise).

### Regression

`api/tests/test_queue.py`:

- Keep existing assertion that `finalize_run_job` is enqueued *without*
  `_job_id`.
- Add: simulate a worker that commits a child but fails to enqueue
  `finalize_run_job` (skip the enqueue call), then run one sweeper tick
  directly and assert the parent reaches `completed`.

### Configuration tests

`api/tests/test_config.py` (or equivalent):

- `finalize_sweeper_interval_seconds = 30` is accepted.
- `finalize_sweeper_interval_seconds = 45` raises a validation error at
  startup.
- `finalize_sweeper_batch_limit = 0` raises a validation error.

## Out of Scope

- Inline finalize (replacing the arq job). Explicitly rejected in this
  iteration.
- Advisory lock on the sweeper. Explicitly rejected — the deadlock-safety
  argument does not require it and the user does not want another concept.
- Prometheus metrics wiring. Left as an optional follow-up.
- One-shot repair of historical stuck runs. Handled separately via the
  query already documented in `docs/bug-evaluation-run-rollup-deadlock.md`.

## Files Touched

| File | Change |
|---|---|
| `api/app/modules/quality_gate/evaluation_run_repository.py` | add `find_finalizable_pending_ids` |
| `api/app/db/models.py` | add partial `Index` on `EvaluationRun` |
| `api/app/queue.py` | add `finalize_sweeper_job`, `_sweeper_cron_seconds`, register in `WorkerSettings` |
| `api/app/config.py` | add two `QueueSettings` fields + validator |
| `config.yaml` | document the two new keys |
| `api/alembic/versions/...` | regenerated migration (`scripts/db-regen-migrations.sh`) |
| `api/tests/db/test_evaluation_run_repository.py` | new tests for `find_finalizable_pending_ids` |
| `api/tests/db/test_finalize_sweeper.py` | new module |
| `api/tests/test_queue.py` | regression test for fast-path failure + sweeper rescue |
| `api/tests/test_config.py` | validator tests for new config fields |
