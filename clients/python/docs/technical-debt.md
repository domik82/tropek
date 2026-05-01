# Python Client — Technical Debt

## No contract validation against backend OpenAPI spec

**Priority:** High — silent drift risk on every API change.

### Problem

The Python client is entirely hand-written: endpoint paths, request bodies, and
response models in `client.py` and `models.py` have no automated check against the
backend's OpenAPI specification (`api/openapi.json`). When the backend adds, renames,
or removes a field or endpoint, the client can silently drift — wrong paths, missing
fields, or stale models are only caught at runtime.

The existing tests (`test_client.py`) mock HTTP responses with hardcoded JSON. They
verify the client's own parsing logic, not conformance to the actual API contract.

### Contrast with the UI

The React UI has a codegen pipeline (`just codegen` → `openapi-typescript`) that
regenerates TypeScript DTOs from `api/openapi.json`. The UI's DTO layer is always in
sync by construction. The Python client has no equivalent.

### Recommended approach

Add a contract test suite (`tests/test_openapi_contract.py`) that loads
`api/openapi.json` at test time and validates:

1. **Endpoint coverage** — every path+method the client calls exists in the spec.
   Walk each namespace class, extract the HTTP method and path from method bodies
   (or maintain a declarative registry), and assert the path exists in
   `spec['paths']`.

2. **Response model fields** — for each endpoint the client deserializes into a
   Pydantic model, compare the model's field names and types against the spec's
   response schema. Flag missing fields, extra fields, and type mismatches.

3. **Request body shape** — for POST/PUT/PATCH endpoints, verify the JSON body keys
   the client sends match the spec's `requestBody` schema.

This does not require a running server — it's a pure spec-vs-code comparison that
runs with `pytest` alongside the existing unit tests. The OpenAPI JSON is already
committed and regenerated as part of the dev workflow.

### Alternatives considered

- **Full codegen** (like the UI): higher maintenance burden for a small client,
  and loses the hand-tuned ergonomics of the current API surface. Better suited
  if the client grows significantly.
- **Integration tests against a live server**: already exist for the backend itself
  (schemathesis). A contract test is lighter and catches drift without infrastructure.

### Scope

- `client.py`: 12 namespace classes, ~60 methods, ~30 distinct endpoint paths
- `models.py`: ~25 Pydantic models, ~150 fields total

## Manifest system gaps

### AssetGroup update is a no-op

`_has_diff()` returns `False` for `AssetGroup` — member and subgroup sync is not
implemented. Manifests can create groups but cannot reconcile membership changes.

### Immutable assignment types

`SLOAssignment` and `SLOGroupAssignment` cannot be updated via manifests. The diff
check always returns `False`. Changing an assignment requires manual delete + recreate
outside the manifest system.

### Export omits SLO group assignments

`_collect_documents()` in `cli.py` exports SLO assignments for assets and groups but
does not export `SLOGroupAssignment` records. A round-trip export → apply would lose
group assignment state.

## Missing async client

The client uses synchronous `httpx.Client`. There is no `AsyncTropekClient` variant
for use in async codebases (e.g., inside the TROPEK worker or other FastAPI services).

## Untyped return values

Several evaluation methods (`evaluate`, `evaluate_batch`, `re_evaluate_from_date`,
`re_evaluate_from_baseline`, `re_evaluate_from_evaluation`) return raw `dict` instead
of typed Pydantic models. The `EvaluationRun` model exists in `models.py` but is not
used by these methods.
