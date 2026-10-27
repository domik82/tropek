# Repairing a Day That Failed to Fetch

An SLO evaluation ends `failed` when its metrics could not be fetched from the data source. This guide
explains how a day gets there, how to tell a transient failure from a real one, and how to fetch the day
again without touching the database.

---

## How a day ends up `failed`

A fetch passes through three hops: the worker asks the Prometheus adapter, and the adapter asks Prometheus.
The adapter retries transient Prometheus failures (timeouts, 429/5xx, dropped connections) with exponential
backoff. A metric whose window could not be fetched completely is an error flagged `transient`, never a
partial value, so the worker retries it too. The worker retries quick failures of its HTTP call to the
adapter (connection errors, 429, 502, 503, a plain 504) itself, but only while a whole new attempt still fits
before the job's deadline. A long failure (a read timeout, or a 504 saying the adapter's budget ran out) is
not retried over HTTP: the evaluation job itself returns the row to `pending` and runs again after
`queue.retry_delay_seconds × attempt`, up to `queue.max_retries` more times (default 3, so four fetch rounds
in all). Only then is the SLO evaluation stored as `failed`. A 4xx answer other than 429, or an answer the
worker cannot read, cannot improve on a rerun and fails the evaluation at once.

A failed evaluation carries the history of its attempts in `job_stats`. A day whose adapter jobs queued too
long looks like this (every attempt waited the whole adapter budget of about 300 s):

```json
{
  "error": "adapter query failed after 4 attempts: adapter returned 504: budget exhausted",
  "fetch_attempts": [
    {"attempt": 1, "http_attempts": 1, "cause": "adapter returned 504: budget exhausted", "status": 504,
     "elapsed_s": 305.1, "at": "2026-10-15T02:10:05.412871+00:00"},
    {"attempt": 2, "http_attempts": 1, "cause": "adapter returned 504: budget exhausted", "status": 504,
     "elapsed_s": 305.0, "at": "2026-10-15T02:15:20.630144+00:00"},
    {"attempt": 3, "http_attempts": 1, "cause": "adapter returned 504: budget exhausted", "status": 504,
     "elapsed_s": 305.2, "at": "2026-10-15T02:20:45.918302+00:00"},
    {"attempt": 4, "http_attempts": 1, "cause": "adapter returned 504: budget exhausted", "status": 504,
     "elapsed_s": 305.1, "at": "2026-10-15T02:26:21.207755+00:00"}
  ]
}
```

Each entry has the job-level attempt number, `http_attempts` (how many HTTP requests that attempt made; quick
failures are retried inside one attempt, so this is 1 when the failure was not retried), the cause, the HTTP
status when there was one, how long the attempt took in seconds, and when it ended. Other causes you may see
are `ReadTimeout: …` (no answer within `reliability.adapter_timeout_seconds`), `adapter returned 503` (the
adapter's queue stayed full; `http_attempts` shows how many requests were sent), `ConnectError: …` (the adapter
was unreachable), and `transient adapter errors for <metric>: incomplete data: 1 of 6 chunks failed (last: …)`
(the adapter answered, but Prometheus failed part of the window). If every attempt shows the same cause, look
at the data source or the adapter, not at Tropek. If the attempts differ, the source was flaky and a refetch
is likely to succeed.

The timeouts that govern this chain are described in
[The timeout chain](../configuration.md#the-timeout-chain).

---

## Refetch versus re-evaluate

| | Re-evaluate | Refetch |
|---|---|---|
| Fetches from the source | No | Yes |
| Uses | Stored indicator values and a (possibly new) SLO definition | The source's current data |
| Use it when | The SLO definition or baseline changed | Stored values are missing, wrong or came from a failed fetch |
| Safe if the source lost the period | Yes | **No** (see the last section) |

A refetch resets each selected SLO evaluation **in place**:

- **Deleted:** the stored result, score and points, any result override, the SLI metadata, the indicator
  results, the SLI values, and the untriaged change points of those evaluation runs and SLOs (triaged ones, and those
  of other evaluations, stay).
- **Kept:** the evaluation's id, its annotations, its invalidation flag and note, and its baseline pins.
- **Recorded:** `job_stats.refetch` holds who asked, when, the reason, and the previous result and status,
  and the run gets a `refetch` annotation.

Then each row goes back to `pending` and runs as a normal evaluation job. Later days are **not** re-scored
by a refetch. If the refetched day feeds later baselines, run a re-evaluate from the day after it
afterwards.

A refetch is refused with 409, and nothing changes, if any matched evaluation is `pending` or `running`.
Wait for it to finish, then retry. A failed row that a later retry already replaced with a completed one is
left alone.

---

## From the UI

1. Open the asset, select the day's column, and choose **Run Evaluations**. Or open one evaluation's detail page
   and choose **Run Evaluations** there.
2. Switch the mode to **Refetch from source**. It is offered only when the panel's evaluation-name filter selects
   exactly one name, or on an evaluation's detail page (which refetches that evaluation's name). With no or
   several names selected, the option is hidden: refetch always targets a single evaluation name.
3. Check the **Start date (UTC)** and **End date (UTC)**, and the SLOs. Both dates start on the selected
   column's day (or the latest day in view when no column is selected), so a refetch never defaults to the
   whole history; widen the range only if you mean to. Only that one evaluation name is refetched; other
   evaluation names of the asset are left alone.
4. Tick **Only SLO evaluations that failed** to leave healthy results untouched.
5. Read the warning block: the stored data for the period is deleted and fetched again.
6. Read the preview line. It comes from a dry run and refreshes when you change the scope, for example
   "Will refetch 7 of 30 SLO evaluations between 2026-10-15T00:00 and 2026-10-15T00:00", or
   "Nothing to refetch" when no evaluation qualifies.
7. Tick **I understand that the stored data for this period is deleted**. The confirmation resets whenever
   you change the scope, so it always refers to what the preview shows.
8. Press **Run**. It stays disabled until the preview shows something to refetch and the confirmation is
   ticked.

The dialog closes and the affected cells render as pending until the jobs finish.

---

## From the API or client

Always run with `dry_run: true` first. It returns the counts and changes nothing.

### One period of an asset

```bash
curl -X POST "$TROPEK_URL/evaluations/refetch" \
  -H 'Content-Type: application/json' \
  -d '{
    "asset_name": "asset-a",
    "evaluation_name": "daily",
    "from": "2026-10-15T00:00:00Z",
    "to": "2026-10-15T23:59:59Z",
    "slo_names": ["latency-slo"],
    "only_failed": true,
    "dry_run": true,
    "reason": "adapter outage",
    "requested_by": "operator"
  }'
```

`from` and `to` are inclusive on each evaluation's `period_start` and must carry a UTC offset (`Z` or
`+00:00`); `evaluation_name` is required (a refetch is always one evaluation) and `slo_names` narrows the
scope; a range wider than 400 days, with `to` before `from`, or with a timestamp that has no offset is a
422. The response is
`{"matched": 3, "refetched": 3, "run_ids": ["..."], "dry_run": true}`. Send the same body
with `"dry_run": false` to run it.

### One evaluation run

```bash
curl -X POST "$TROPEK_URL/evaluation-run/$RUN_ID/refetch" \
  -H 'Content-Type: application/json' \
  -d '{"only_failed": true, "dry_run": true, "reason": "adapter outage"}'
```

An unknown asset or run is a 404.

### Python client

```python
from datetime import UTC, datetime

from tropek_client.models import RefetchRequest, RefetchRunRequest

preview = client.evaluations.refetch(
    RefetchRequest(
        asset_name='asset-a',
        evaluation_name='daily',
        from_=datetime(2026, 10, 15, tzinfo=UTC),
        to=datetime(2026, 10, 15, 23, 59, 59, tzinfo=UTC),
        only_failed=True,
        dry_run=True,
    )
)
print(preview.matched, preview.refetched)

client.evaluations.refetch_run(run_id, RefetchRunRequest(only_failed=True, reason='adapter outage'))
```

---

## When the source no longer has the period

A refetch deletes the stored values before it knows what the source will return. If the source has dropped
the period (Prometheus retention has passed, or the series were removed), the fetch finds no data, and the
evaluation completes with an `error` result and nothing left of the old values. Only a database restore
brings them back; the previous result is kept in `job_stats.refetch.previous_result` for reference, but not
the indicator values or SLI samples behind it.

Before refetching an old period, check that the source still holds it, and prefer `only_failed` so that
healthy results are never replaced.
