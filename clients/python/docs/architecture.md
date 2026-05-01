# Python Client — Architecture

Contributor guide for `clients/python/tropek_client/`.

## Module Structure

```
tropek_client/
├── __init__.py       # Public API: TropekClient + exception classes
├── client.py         # HTTP client with resource-namespaced methods
├── models.py         # Pydantic response models
├── manifest.py       # YAML manifest loader and reconciler
├── cli.py            # Click CLI interface
└── exceptions.py     # Typed exception hierarchy
```

## Client Design (`client.py`)

The client uses **namespace classes** to group API methods by resource type. Each
namespace (e.g., `_Assets`, `_SLODefinitions`) is a private class that receives a
shared `httpx.Client` instance. `TropekClient.__init__` instantiates all namespaces
and exposes them as public attributes.

HTTP pattern for every method:
1. Build params/body dict, omitting `None` values
2. Call `self._http.{verb}(path, ...)` 
3. Pass response through `_raise_for_status()` (maps status codes to typed exceptions)
4. Deserialize via `Model.model_validate(resp.json())`

Paginated endpoints return `PagedResponse[T]` (items + total). Non-paginated
endpoints return the model directly or a raw `dict` for polymorphic responses
(evaluations trigger, batch, re-evaluate).

`TropekClient` implements the context manager protocol for automatic cleanup.

## Error Handling (`exceptions.py`)

Four-class hierarchy:
- `TropekAPIError(status_code, detail)` — base, catches any non-2xx
- `TropekNotFoundError(detail)` — 404
- `TropekConflictError(detail)` — 409
- `TropekValidationError(detail)` — 422

`_raise_for_status()` uses structural pattern matching on `resp.status_code`.
The response body's `detail` field is extracted when available; raw text is the fallback.

## Models (`models.py`)

Pydantic v2 models mirroring API response schemas. Key patterns:
- `PagedResponse[T]` — generic paginated wrapper using Python 3.12+ type parameter syntax
- `ConfigDict(from_attributes=True)` on ORM-mapped models for compatibility
- `EvaluationDetail` extends `EvaluationSummary` (adds annotations, indicator results)
- Request models (`SLOTestRequest`, `BaselineConfig`) for structured input
- String IDs on assignment models (`SLOAssignment`, `SLOGroupAssignment`) — the API
  returns UUIDs as strings in some endpoints

## Manifest System (`manifest.py`)

### Processing Pipeline

```
load_manifests(path)
    ├── _load_file()          # YAML multi-doc parsing
    ├── _parse_document()     # Validate required fields, known kinds
    └── _topological_sort()   # Sort by _KIND_ORDER dependency

validate_manifests(path)
    ├── load_manifests()
    └── _validate_doc_refs()  # Cross-reference warnings

dry_run(client, manifests)
    └── for each doc:
        ├── _lookup()         # Fetch existing resource from API
        ├── _has_diff()       # Field-level comparison
        └── → PlanAction(CREATE | UPDATE | SKIP)

apply(client, manifests)
    ├── dry_run()             # Build plan first
    └── for each action:
        ├── _create()         # Kind-specific create dispatch
        ├── _update()         # Kind-specific update dispatch
        └── _dependents_of()  # Block downstream kinds on failure
```

### Dependency Graph

`_KIND_ORDER` defines processing order: `AssetType → DataSource → Asset → SLI → SLO
→ AssetGroup → SLOGroup → SLOAssignment → SLOGroupAssignment`.

`_KIND_DEPS` maps each kind to its dependents for error propagation — if an `Asset`
creation fails, `AssetGroup`, `SLOAssignment`, and `SLOGroupAssignment` are blocked.

### Update Semantics

- **Versioned resources** (SLI, SLO): updates create a new version via the same
  `create` endpoint rather than patching in place.
- **Immutable resources** (SLOAssignment, SLOGroupAssignment): `_has_diff` always
  returns `False` — requires manual delete + recreate.
- **AssetGroup**: member/subgroup sync not yet implemented; updates are skipped.

## CLI (`cli.py`)

Click command tree with three commands:

- `tropek validate -f <path>` — offline YAML validation
- `tropek apply -f <path> [--dry-run] [--base-url] [--api-key]` — reconcile manifests
- `tropek export [-f <path>] [--base-url] [--api-key]` — dump current state as YAML

`export` uses `_collect_documents()` which iterates all resource types and builds
manifest dicts. It also walks per-asset and per-group SLO assignments.

## Test Structure

```
tests/
├── test_client.py     # HTTP mocking via pytest-httpx; covers CRUD + error mapping
├── test_manifest.py   # Manifest loading, sorting, dry_run, apply with MagicMock client
├── test_cli.py        # Click CliRunner tests for validate + apply --dry-run
└── test_models.py     # Pydantic model_validate round-trips
```

Dev dependencies: `pytest`, `pytest-httpx` (for `HTTPXMock` fixture).

Tests use `MagicMock` for the client in manifest/CLI tests and `HTTPXMock` for
HTTP-level client tests. No real API calls in any test.

## Known Limitations

See [`technical-debt.md`](technical-debt.md) for detailed analysis and recommended
fixes. Summary:

- No contract validation against the backend OpenAPI spec — client can silently drift
- `AssetGroup` update via manifests is a no-op (member sync not implemented)
- Assignment updates require manual delete + recreate
- No async client variant
- `export` does not include SLO group assignments
- Some endpoints return raw `dict` instead of typed models (evaluation triggers)
