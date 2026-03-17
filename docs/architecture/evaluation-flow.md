# Evaluation Flow

The core use case: a client triggers an evaluation, metrics are fetched, scored against
SLO criteria, and the result is persisted.

## Sequence

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API :8080
    participant R as Redis
    participant W as Worker
    participant Ad as Adapter :8081
    participant E as Engine (pure)
    participant DB as TimescaleDB

    C->>A: POST /evaluations
    A->>DB: create_pending(eval_id)
    A->>R: enqueue job(eval_id)
    A-->>C: 202 Accepted {eval_id, status: pending}

    R->>W: dequeue job
    W->>DB: mark_running(eval_id)
    W->>DB: get_baselines(asset, slo, comparison)
    W->>Ad: POST /query (SLI queries + time range)
    Ad-->>W: {values: {...}, errors: {...}}

    W->>E: evaluate(slo, metrics, baselines)
    E-->>W: EvaluationResult

    W->>DB: mark_completed(result, score, indicators)
    W->>DB: write_sli_values(hypertable)

    C->>A: GET /evaluations/{eval_id}
    A->>DB: get_by_id()
    A-->>C: EvaluationDetail
```

## Evaluation Lifecycle

```mermaid
stateDiagram-v2
    [*] --> pending: create_pending()
    pending --> running: mark_running()
    running --> completed: mark_completed()
    running --> failed: mark_failed()
    running --> partial: mark_partial() [crash]
    partial --> pending: watchdog reschedule
```

| Status | Meaning |
|--------|---------|
| **pending** | Enqueued, waiting for a worker |
| **running** | Worker picked it up, fetching metrics or evaluating |
| **completed** | Engine ran, result + score + indicators persisted |
| **failed** | Unrecoverable error (adapter down, invalid SLO, etc.) |
| **partial** | Worker crashed mid-execution; watchdog can reschedule |

## Ingestion Modes

Three ways to supply metric values:

### Pull mode (adapter fetches from Prometheus)

```
Client -> API: POST /evaluations {slo_name, datasource, start, end, metadata}
Worker -> Adapter: POST /query {queries, start, end, step, variables}
Adapter -> Prometheus: GET /api/v1/query_range
```

### Push mode (client provides values inline)

```
Client -> API: POST /evaluations {slo_name, metrics: {metric: value, ...}}
Worker: skips adapter call, uses provided values directly
```

### File mode (CSV or JMeter upload)

```
Client -> API: POST /evaluations/file (multipart: meta JSON + results file)
Worker: parses file, extracts metric values
```

## Baseline Comparison

Relative criteria (e.g. `<=+10%`) compare the current value against a baseline
derived from previous evaluations:

1. Worker calls `get_baselines()` with the comparison config from the SLO
2. Baselines are filtered by: asset, SLO name, result score (pass/warn/all), count limit
3. Values are aggregated using the configured function (avg, p50, p90, p95, p99)
4. If `scope_tags` is set, baselines are further filtered to matching asset labels
5. If no baselines exist, relative criteria **always pass** (no penalty for first run)

## Scoring

```mermaid
flowchart TD
    E[evaluate] -->|for each objective| SO[score_objective]
    SO --> PC[parse criteria strings]
    PC -->|fixed: <600| FX[Compare value vs threshold]
    PC -->|relative: <=+10%| RL[Compute target from baseline]
    RL --> FX
    SO -->|PASS / WARNING / FAIL / INFO| OR[ObjectiveResult]
    E -->|collect all results| CTS[calculate_total_score]
    CTS -->|sum weighted scores| TS[TotalScore]
    CTS -->|check key SLI veto| TS
    TS -->|score vs pass%/warning%| ER[EvaluationResult]
```

- **Within a criteria block**: AND logic (all must pass)
- **Across blocks**: OR logic (any block passing = pass)
- **Key SLI**: if a key SLI fails, the entire evaluation fails regardless of total score
- **INFO status**: objectives with no pass criteria are informational, don't affect score

## Post-Evaluation

After completion, evaluations support:

- **Annotations**: contextual notes (e.g. "kernel updated before this test")
- **Invalidation**: mark as invalid without deleting (preserves audit trail)
- **Trend queries**: time-series data from the `sli_values` hypertable
