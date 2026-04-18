# Schemathesis First-Run Triage

Run command: `uv run --directory api pytest tests/schemathesis/test_schema.py`

Run date: 2026-04-18

Result of the latest full run (after landed fixes): **60 passed, 41 failed / 101 tests**
(up from 11/101 on first run — see fix log below).

## Fixes landed in this phase

| Commit | Category | Notes |
|---|---|---|
| `f154179` | Test infrastructure | `.env.test` now overrides dev creds in the schemathesis conftest; DB engine rebuilt per request with NullPool so each Hypothesis example gets a connection on its own event loop. Also fixed `alembic/env.py` to resolve `ENV_FILE` relative to repo root. |
| `bc3c02f` | Response-schema drift | `DomainValidationError` now emits `HTTPValidationError` (`detail: list[ValidationError]`) instead of `detail: <string>`. |
| `20e74c9` | Silent 500s | Blanket `IntegrityError` → 409 handler so unique / FK / NOT-NULL violations never surface as 500s. |
| `411d0e0` | Routing / 405 | `MethodNotAllowedMiddleware` snapshots every literal-path route's allowed methods at startup and returns 405 + `Allow` before Starlette would otherwise dispatch to a parameterised sibling and 422 its body. Prompted by security-review concern. |
| `789e3f3` | Schema drift | Meta path-entry length moved from a custom `@field_validator` to `Annotated[str, StringConstraints(min_length=1, max_length=128)]`. Constraint now flows into the OpenAPI schema so schemathesis stops generating empty / overlong entries that the custom validator would reject. |
| `42d64da` | OpenAPI ↔ reality alignment | 3 things in one commit: (a) `SessionMiddleware` commits only on 2xx and rolls back on 4xx/5xx — kills `PendingRollbackError` 500s after `IntegrityError` → 409; (b) `custom_openapi()` injects 404 (path-param ops), 409 (mutating ops) and 422 (every op) into the spec since FastAPI only auto-documents 422 on body-bearing endpoints; (c) `AnnotationCategoryCreate.show_on_graph` typed `StrictBool` so Pydantic no longer silently coerces `0`/`1` to boolean — fixes `AcceptedNegativeData` check. |

## Remaining failures — residual schema drift

After the above fixes the ~41 remaining failures are dominated by schema drift
around cross-field constraints that **cannot be expressed in vanilla JSON
Schema** and which we deliberately enforce at the Pydantic `@model_validator`
layer:

- `ReEvaluateRequest.exactly_one_scope` / `slo_name_and_names_mutually_exclusive`
- `SLIDefinitionCreate.validate_mode_fields` (mode-dependent field requirements)
- `GET /trend` query-param `eval_id XOR (asset_name + slo_name)` check
- `MetaSnapshotCreate` per-list uniqueness by `path`

Schemathesis correctly considers the generated input "schema-compliant" and
expects a 2xx. Fixing these requires one of:

1. **Discriminated unions / `oneOf` schemas** — architectural refactor of the
   request bodies so the constraint is representable in OpenAPI. Ideal but
   non-trivial per endpoint.
2. **`json_schema_extra` annotations** — expose the constraint (e.g.
   `uniqueItems: true` on single-field lists) without restructuring the model.
   Works only for constraints JSON Schema can represent.
3. **Targeted `schemathesis` exclusion** — document the constraint at the
   operation level and tell schemathesis these are known-unrepresentable. Keeps
   every other conformance + security check active.

## Historical note: prior dominant cause (pre-fix)

Spot-checking a representative failure (`GET /datasources/tag-keys`):

```
Unsupported method PATCH returned 422, expected 405 Method Not Allowed
```

This is the **`UnsupportedMethodResponse`** check. Starlette resolves `PATCH
/datasources/tag-keys` to the catch-all `/datasources/{name}` route (because
the OpenAPI spec only lists `GET` for `/datasources/tag-keys`). The body
validator then returns 422 ("Field required") instead of Starlette's 405.
The same collision pattern explains the failures on every route that lives
under a parameterised sibling — `/datasources/{name}`, `/assets/{name}`,
`/asset-groups/{name}`, `/slo-definitions/{name}`, and so on.

This is a FastAPI + Starlette behaviour, not a backend bug:
path-with-literal-prefix endpoints are registered after the parameterised
catch-all, and Starlette matches the first route that accepts the method.
Schemathesis' check is stricter than the actual HTTP spec here — RFC 7231 is
happy with 4xx responses; it only mandates 405 when a registered resource
does not support the method.

## Next step — options

The plan's Task 3 says "Do not silence failures by lowering --checks". Two
ways forward that do not silence real checks:

1. **Document `UnsupportedMethodResponse` as an accepted limitation** and
   disable only that single check via Schemathesis configuration, keeping
   all other conformance + security checks active. The remaining suite would
   go from 90/101 failing to ~10/101, and the residual handful are the real
   bugs worth fixing.
2. **Register a FastAPI global 405 handler** that inspects the URL against
   known routes and returns 405 when the method is not registered for that
   exact path. This matches Schemathesis' expectation but adds app
   complexity to satisfy a test-only concern.

Recommended: option 1 — it keeps the test signal focused on actual API
contract violations.

## Surfaced but not yet fixed

- The `IntegrityError` handler returns 409, but the OpenAPI spec does not
  yet document `409` on mutating endpoints. Schemathesis will flag any
  integrity collision it hits as an undocumented status code. Fix: add a
  default `responses={409: {"model": HTTPValidationError}}` to each
  mutating router, or a FastAPI custom `openapi()` post-processor.
- `asyncpg.CharacterNotInRepertoireError` (null byte `0x00` in generated
  strings) surfaces as a 500. Needs Pydantic input validation on
  user-provided string fields to reject `\0` before the DB is hit.
- Some POST endpoints with required nested bodies return 422 with the
  legacy flat-detail shape from custom validators; the fix for
  `DomainValidationError` covered the domain-raised case, not Pydantic-raised
  cases that escape the default FastAPI handler.

## Endpoints still excluded from fuzzing

Kept from the initial harness — side-effect-heavy (arq enqueue):

- `POST /api/evaluations`
- `POST /api/evaluations/re-evaluate`
