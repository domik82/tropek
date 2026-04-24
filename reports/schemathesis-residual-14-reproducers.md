# Schemathesis Residual-14 Reproducers

**Run:** `uv run --directory api pytest tests/schemathesis/test_schema.py -v --hypothesis-show-statistics`
**Captured output:** `/tmp/schemathesis-14.txt`
**Result:** **14 failed, 83 passed, 7 skipped** (`803.99s`).

The plan anticipated 14 failures but predicted a slightly different set — the baseline shifted by one
pass and the deltas are documented below under "Divergence from plan inventory".

> **Seeds:** schemathesis 4.x does not emit a numeric `hypothesis-seed` line in failure output — it
> prints a `curl` reproducer instead. Each block below embeds the exact reproducer from `/tmp/schemathesis-14.txt`.
> Re-running with `--hypothesis-seed=<N>` is not required; the Hypothesis DB (`.hypothesis/`) replays
> the failing example automatically when the same test node is re-run.

---

## Divergence from plan inventory

| Plan # | Plan expected endpoint | Actually failing? | Notes |
|---|---|---|---|
| 1 | `POST /assets/{asset_id}/meta/snapshots` | YES | matches |
| 2 | `PATCH /assets/{name}` | YES | matches |
| 3 | `POST /datasources` | **NO** | passing this run |
| 4 | `PATCH /datasources/{name}` | YES | matches |
| 5 | `POST /slo-definitions` | YES | matches |
| 6 | `POST /slo-definitions/test` | YES | matches |
| 7 | `POST /evaluation/{eval_id}/annotations` | YES | matches |
| 8 | `PATCH /evaluation/{eval_id}/annotations/{ann_id}` | YES | matches |
| 9 | `POST /evaluation-run/{run_id}/annotations` | YES | matches |
| 10 | `GET /sli-definitions` | **NO** | passing this run |
| 11 | `PUT /slo-groups/{name}` | YES | matches |
| 12 | `GET /evaluations` | YES | matches (cross-field XOR — date vs from/to) |
| 13 | `PUT /assets/{name}/slo-definitions/{slo_definition_id}` | YES | matches |
| 14 | `PUT /asset-groups/{name}/slo-definitions/{slo_definition_id}` | YES | matches |

**Plan residuals not seen in actual failures:** `POST /datasources`, `GET /sli-definitions`.
**Actual failures not named in plan:** `POST /sli-definitions`, `GET /evaluations/heatmap`.

Net count still 14. The plan's Task-3 ("fix `GET /sli-definitions`") must be re-scoped to
`POST /sli-definitions`; the `GET /evaluations/heatmap` failure replaces the anticipated
datasource-POST slot. Controller should decide whether to keep the task numbering or re-label.

---

## Reproducer blocks

### 1. POST /assets/{asset_id}/meta/snapshots (β)

- **Check:** RejectedPositiveData (422)
- **Response:** `"snapshot must contain values or closed entries"`
- **Offending field:** whole-body cross-field invariant — schemathesis generated `{"closed": [], "observed_at": "...", "source": "0", "values": []}` (both empty).
- **Current guard:** Pydantic model validator rejecting both-empty.
- **Suspected fix:** constraint is cross-field XOR-ish — not representable as plain OpenAPI. Either
  add an `anyOf`/`oneOf` in the schema export, exclude `positive_data_acceptance` for this op,
  or relax the model-validator to allow both-empty and let the service layer handle it.
- **Reproducer:**
  ```bash
  curl -X POST -H 'Content-Type: application/json' \
    -d '{"closed": [], "observed_at": "2000-01-01T00:00:00Z", "source": "0", "values": []}' \
    http://localhost/assets/e3e70682-c209-1cac-a29f-6fbed82c07cd/meta/snapshots
  ```

### 2. PATCH /assets/{name} (β)

- **Check:** RejectedPositiveData (422)
- **Response:** `"null bytes are not allowed in dict keys"` at `body.heatmap_config`
- **Offending field:** `heatmap_config` — a deeply nested dict whose *keys* include `"\u0000"`
  several layers down.
- **Current annotation (likely):** `heatmap_config: dict[str, Any] | None` with `SafeJsonAny` —
  walker traverses but per the input the walker did fire (it is what raised). The reject is real,
  but `heatmap_config`'s spec does not advertise a "no-null-bytes" constraint to schemathesis.
- **Suspected fix:** either (a) strip null bytes in the walker silently instead of rejecting, or
  (b) ensure the OpenAPI export declares the constraint (patternProperties / `x-null-byte-safe`),
  or (c) accept that null bytes reach the DB and rely on the existing walker (current behaviour
  IS rejecting — the test is flagging that schemathesis doesn't know about the constraint).
  Design unresolved — see memory note `project_heatmap_config_investigation.md`.
- **Reproducer:** see `/tmp/schemathesis-14.txt` line 167 (truncated curl too long to inline).

### 3. PATCH /datasources/{name} (β, residual 4)

- **Check:** RejectedPositiveData (422)
- **Response:** `"null bytes are not allowed in dict values"` at `body.tags`
- **Offending field:** `tags` — `dict[str, str]` with a value like `"\u0000"` somewhere.
- **Current annotation:** `tags: dict[str, str]` (apparently without the recursive walker).
- **Suspected fix:** apply `SafeJsonDict` (or whatever the string-leaf walker is) to `tags` on
  `DataSourceUpdate`. Note: POST currently passes — only PATCH fails, so the POST model already
  has the guard but the PATCH sibling doesn't.
- **Reproducer (trimmed):**
  ```bash
  curl -X PATCH -H 'Content-Type: application/json' \
    -d '{"adapter_url": "...", "display_name": "...", "tags": {"key": "\u0000..."}, "token": null}' \
    http://localhost/datasources/o
  ```
  Full reproducer at line 193 of `/tmp/schemathesis-14.txt`.

### 4. POST /sli-definitions (new — not in plan)

- **Check:** AcceptedNegativeData / server 500 (DB exception, not 422)
- **Response:** `asyncpg.exceptions.UntranslatableCharacterError: \u0000 cannot be converted to text`
- **Offending field:** `indicators` — `{"": "\u0000"}` (JSONB column receives `\u0000`).
- **Current annotation (likely):** `indicators: dict[str, Any]` with NO walker applied (it reaches
  the DB and postgres rejects).
- **Suspected fix:** apply `SafeJsonAny` (recursive null-byte walker) to `SLIDefinitionCreate.indicators`.
  Failure mode is a DB error (500) — the Pydantic layer is letting it through. This is probably
  what the plan intended as residual 10 ("GET /sli-definitions"); suspect mislabel.
- **Reproducer:**
  ```bash
  curl -X POST -H 'Content-Type: application/json' \
    -d '{"adapter_type": "", "name": "", "indicators": {"": "\u0000"}}' \
    http://localhost/sli-definitions
  ```

### 5. POST /slo-definitions (β)

- **Check:** RejectedPositiveData (422)
- **Response:** `"objective sli '0' not found in SLI definition '' indicators"` (domain_validation)
- **Offending field:** cross-field — `objectives[].sli` must reference `indicators` keys, but
  schemathesis happily generates objectives whose `sli` is absent from the inline indicators dict.
- **Current:** server-side domain validation rejects.
- **Suspected fix:** this is NOT a null-byte / SafeJsonAny issue — it's a genuine cross-field
  constraint unrepresentable in OpenAPI. Plan Task 2.4 assumed walker fix; this needs either a
  per-op exclusion of `positive_data_acceptance` with a rationale comment, or a JSON-Schema
  `dependentRequired` export (complex). **Flag to controller: plan hypothesis wrong for this one.**
- **Reproducer:** line 625 of `/tmp/schemathesis-14.txt`.

### 6. POST /slo-definitions/test (β)

- **Check:** RejectedPositiveData (422) — AND a second failure class where the adapter URL is empty
  and httpx rejects with `UnsupportedProtocol`.
- **Responses seen:**
  - `invalid slo: ... SLOComparison.aggregate_function: Input should be 'avg','p50','p90','p95','p99'` (empty string tripped enum)
  - `Request URL is missing an 'http://' or 'https://' protocol` (httpx leak from empty `data_source_name`)
- **Offending fields:** `comparison.aggregate_function = ""` and `data_source_name = ""`.
- **Current:** `aggregate_function` typed as `Literal[...]` but the OpenAPI export likely permits
  `""` via an `anyOf null/string` or missing `enum` narrowing; also `data_source_name` lookup fails
  and bubbles up as 500 instead of 404.
- **Suspected fix:**
  - Ensure the OpenAPI export of `SLOComparison.aggregate_function` lists the enum values *and*
    `nullable: true` only if the runtime accepts null — otherwise drop `""` from allowed inputs.
  - Wrap `data_source_name` lookup in try/except raising 404/400 rather than letting httpx bubble.
- **Reproducer:** lines 803 and 829 of `/tmp/schemathesis-14.txt`.

### 7. PUT /slo-groups/{name} (new — plan residual 11)

- **Check:** RejectedPositiveData (422)
- **Response:** `"null bytes are not allowed in dict keys"` at `body.tags`
- **Offending field:** `tags` — deeply-nested dict with null-byte key somewhere.
- **Current annotation (likely):** `tags: SafeJsonAny | None` with walker already firing.
- **Suspected fix:** same as residual 2 — either the OpenAPI export needs to advertise the
  constraint to schemathesis, or relax the walker to silently strip. Unlike plan hypothesis
  ("optional field short-circuit"), the walker DOES run and correctly rejects; the fix is about
  advertising the constraint, not the short-circuit.
- **Reproducer:** line 855 of `/tmp/schemathesis-14.txt`.

### 8. GET /evaluations (γ — plan residual 12)

- **Check:** RejectedPositiveData (422)
- **Response:** `"date and from/to filters are mutually exclusive"` (domain_validation)
- **Offending field:** **cross-field** — `date`, `from`, `to` query params are mutually exclusive,
  but schemathesis generated all three (`date=null&from=...&to=...`).
- **Current:** FastAPI router enforces in code; OpenAPI doesn't advertise the XOR.
- **Suspected fix:** NOT a SafeQueryStr issue (plan hypothesis wrong). Options:
  1. Expose the XOR via `oneOf` on the query params (ugly in OpenAPI).
  2. Exclude `positive_data_acceptance` for `('GET', '/evaluations')` with rationale.
  3. Treat `date=null` (literal string `"null"`) as "not set" in the handler (quick fix).
- **Reproducer:**
  ```bash
  curl -X GET 'http://localhost/evaluations?asset_name=&slo_name=&result=&date=null&group_name=&from=2000-01-01T00%3A00%3A00Z&to=2000-01-01T00%3A00%3A00Z&limit=200&offset=0'
  ```

### 9. GET /evaluations/heatmap (new — not in plan)

- **Check:** AcceptedNegativeData / server 500
- **Response:** `asyncpg.CharacterNotInRepertoireError: invalid byte sequence for encoding "UTF8": 0x00`
- **Offending field:** `asset_name` query param = `"\u0000"` reaches the SQL VARCHAR comparison.
- **Current:** query param appears to be plain `str` (no SafeQueryStr walker) → reaches asyncpg.
- **Suspected fix:** apply null-byte-rejecting string validator to `asset_name` (and siblings) on
  `GET /evaluations/heatmap`. This is the real "query-param" residual; plan Task 5 is reusable.
- **Reproducer:**
  ```bash
  curl -X GET 'http://localhost/evaluations/heatmap?asset_name=%00'
  ```

### 10. POST /evaluation/{eval_id}/annotations (β, residual 7)

- **Check:** RejectedPositiveData (422)
- **Response:** `"null bytes are not allowed in dict keys"` at `body.tags`
- **Offending field:** `tags` — nested dict with null-byte keys.
- **Current annotation:** likely `tags: dict[str, Any]`; walker fires (error is from the walker).
- **Suspected fix:** same pattern as #2 / #7 — walker IS running; need to either advertise the
  constraint to schemathesis or silently strip. The plan's hypothesis ("tags dict still permits
  null bytes") is inverted — the dict rejects them; schemathesis doesn't know.
- **Reproducer:** line 1306 of `/tmp/schemathesis-14.txt`.

### 11. PATCH /evaluation/{eval_id}/annotations/{ann_id} (β, residual 8)

- Same pattern as #10 (same shared annotations schema).
- **Reproducer:** line 1332 of `/tmp/schemathesis-14.txt`.

### 12. POST /evaluation-run/{run_id}/annotations (β, residual 9)

- Same pattern as #10 (same shared annotations schema, run-level).
- **Reproducer:** line 1358 of `/tmp/schemathesis-14.txt`.

### 13. PUT /assets/{name}/slo-definitions/{slo_definition_id} (γ, residual 13)

- **Check:** RejectedPositiveData (422)
- **Response:** `"null bytes are not allowed in dict keys"` at `body.comparison_rules`
- **Offending field:** `comparison_rules: list[dict[str, Any]]` — inner dict key contains `"\u0000"`.
- **Current:** walker DOES traverse list→dict→key (error path proves it). So the plan's Task 1
  hypothesis ("walker doesn't accept list") is wrong — it already does. The walker fires and
  correctly rejects; schemathesis does not know the constraint.
- **Suspected fix:** same family as #2/#7/#10. Advertise the constraint, or silently strip.
  Task 1 as written may not be needed.
- **Reproducer:** line 1384 of `/tmp/schemathesis-14.txt`.

### 14. PUT /asset-groups/{name}/slo-definitions/{slo_definition_id} (γ, residual 14)

- Same pattern as #13 (same `SLOAssignmentUpsert` shared schema).
- **Reproducer:** line 1410 of `/tmp/schemathesis-14.txt`.

---

## Pattern summary

| Pattern | Count | Endpoints |
|---|---|---|
| Null-byte rejected by walker → schemathesis doesn't know the constraint (need silent-strip or advertise) | 8 | #2, #3, #7, #10, #11, #12, #13, #14 |
| Null-byte reaches DB → need to ADD walker | 2 | #4 (POST /sli-definitions), #9 (GET /evaluations/heatmap asset_name) |
| Cross-field invariant unrepresentable in OpenAPI | 3 | #1 (snapshots both-empty), #5 (slo objective sli ref), #8 (GET /evaluations date vs from/to) |
| Empty-string enum / 500 on lookup | 1 | #6 (POST /slo-definitions/test) |

This reclassification materially changes Task 1 and Tasks 2.x in the plan: most β failures are
**not** about applying more `SafeJsonAny` — the walker is already running and rejecting. The
decisive choice is between (a) changing walker semantics from reject → silent-strip (dangerous;
silently mutating input is bad) and (b) accepting the rejection and excluding
`positive_data_acceptance` for those ops with a rationale comment ("constraint not expressible in
OpenAPI 3.1 without custom extensions"). Option (b) is the likely outcome for the 8 walker-reject
cases.

The two genuine "missing walker" cases (#4 POST /sli-definitions, #9 GET /evaluations/heatmap) are
the ones where a real code fix applies.

Controller should re-evaluate the task plan with these observations before authorising Task 1.
