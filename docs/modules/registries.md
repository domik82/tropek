# SLO & SLI Registries

## Purpose

Versioned, immutable definition registries for SLOs and SLIs. Every change creates a
new version — evaluations record which version they used, so historical results are
always reproducible.

## Key Concepts

| Concept | What It Is |
|---------|------------|
| **SLO Definition** | Structured objectives with criteria, scoring thresholds, and comparison config. Identified by name + version. |
| **SLI Definition** | A map of metric names to query strings (PromQL, SQL, etc.). Identified by name + version. |
| **Versioning** | Immutable after insert. POST with an existing name auto-increments the version. |
| **Soft Delete** | DELETE deactivates all versions (sets `active = false`). Data is preserved. |
| **Validation** | `POST /slo-definitions/validate` dry-runs SLO parsing and criteria checking without creating a version. |
| **Test** | `POST /slo-definitions/test` evaluates an SLO against live adapter metrics without persisting results. |
| **Tags** | Both SLOs and SLIs support key/value tags for filtering and grouping. |

## Typical Workflows

### Create and iterate on an SLO

1. Validate the SLO structure: `POST /slo-definitions/validate`
2. Test against live metrics: `POST /slo-definitions/test`
3. Create version 1: `POST /slo-definitions`
4. Update (creates version 2): `POST /slo-definitions` with the same name
5. View version history: `GET /slo-definitions/{name}/versions`

### Create an SLI definition

1. Create: `POST /sli-definitions` with an indicator map and adapter type
2. Reference from an SLO definition via `sli_name` (and optionally `sli_version`)

## SLO Endpoints

| Method | Path | What It Does |
|--------|------|--------------|
| `GET` | `/slo-definitions` | List all active SLO definitions. Supports `tag_key`, `tag_val`, and `kind` filters. |
| `POST` | `/slo-definitions` | Create a new SLO definition (auto-increments version if name exists). |
| `POST` | `/slo-definitions/validate` | Validate SLO structure and criteria strings without saving. |
| `POST` | `/slo-definitions/test` | Evaluate an SLO against live adapter metrics without persisting. |
| `GET` | `/slo-definitions/tag-keys` | Return distinct tag keys with usage counts. |
| `GET` | `/slo-definitions/tag-values` | Return distinct tag values for a given key with usage counts. |
| `GET` | `/slo-definitions/{name:path}` | Get the latest active version of an SLO definition. |
| `GET` | `/slo-definitions/{name:path}/versions` | List all versions of an SLO definition. |
| `DELETE` | `/slo-definitions/{name:path}` | Deactivate all versions of an SLO definition. |

## SLI Endpoints

| Method | Path | What It Does |
|--------|------|--------------|
| `GET` | `/sli-definitions` | List all active SLI definitions. Supports `adapter_type`, `tag_key`, and `tag_val` filters. |
| `POST` | `/sli-definitions` | Create a new SLI definition (auto-increments version if name exists). |
| `GET` | `/sli-definitions/tag-keys` | Return distinct tag keys with usage counts. |
| `GET` | `/sli-definitions/tag-values` | Return distinct tag values for a given key with usage counts. |
| `GET` | `/sli-definitions/{name}` | Get the latest active version of an SLI definition. |
| `GET` | `/sli-definitions/{name}/versions` | List all versions of an SLI definition. |
| `DELETE` | `/sli-definitions/{name}` | Deactivate all versions of an SLI definition. |

## Gotchas / Design Decisions

- Versions are auto-incremented using `SELECT ... FOR UPDATE` to prevent race conditions.
- GET returns the latest active version by default. Use `/versions` for full history.
- SLO names support path characters (e.g., `http/api-slo`) via `{name:path}` routing. SLI names do not — they are plain path segments.
- SLO creation validates that all objective `sli` references exist in the linked SLI definition's indicator map before inserting.
- The `/test` endpoint hits a real adapter (datasource) — it is not a mock dry-run. It requires a valid datasource to be reachable.
- Deactivation is soft — re-POSTing with the same name after DELETE creates a new active version starting from the next version number.
- Tag-key and tag-value endpoints enable UI filtering by labels attached to definitions without loading all definitions.
