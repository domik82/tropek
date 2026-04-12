# Asset-Level Evaluation Trigger — Specification

## Problem

The current trigger API requires callers to specify individual SLOs. This causes:

1. **Missing evaluations**: When triggering via batch or single, SLOs bound through `SLOBinding` or `TemplateBinding` are missed entirely. Example: `checkout-api` has `plugin/auth` SLO bound via template binding, but `trigger_batch('core-services', ...)` never creates an evaluation for it because `_scan_batch_members` only queries `AssetSLOLink` + `AssetGroupSLOLink`, not `SLOBinding`.

2. **Heatmap inconsistency**: The heatmap shows ALL indicators across ALL SLOs for an asset, but evaluations only cover a subset of SLOs. This makes cells appear missing/empty for SLOs that were never triggered.

3. **Caller burden**: The caller must know which SLOs are linked to an asset and trigger each one individually. This is error-prone and defeats the purpose of having SLO links.

## Current Architecture

### Trigger Paths

| Path | Input | SLO Resolution |
|---|---|---|
| `trigger_single` | asset + slo_name | Exactly 1 SLO (explicit) |
| `trigger_batch` | group_name | Per-member: `AssetSLOLink` + `AssetGroupSLOLink` (misses `SLOBinding`) |

### SLO Binding Types (3 sources)

1. **`AssetSLOLink`** — direct asset-level link (e.g., `checkout-api` → `agg-latency-slo`)
2. **`AssetGroupSLOLink`** — group-level link (e.g., `core-services` group → some SLO)
3. **`SLOBinding`** — polymorphic binding targeting asset OR asset_group, created by:
   - Manual creation via API
   - Template binding expansion (SLO groups generate SLOs + create SLOBindings)

### Key Files

- `api/app/modules/quality_gate/trigger_service.py` — `TriggerService.trigger_single()`, `trigger_batch()`, `_scan_batch_members()`
- `api/app/modules/quality_gate/trigger.py` — `resolve_single_trigger()` resolves asset+SLO into a `TriggerContext`
- `api/app/modules/quality_gate/schemas.py` — `TriggerRequest` (requires `slo_name`), `BatchTriggerRequest`
- `api/app/modules/quality_gate/router.py` — POST `/evaluations` and POST `/evaluations/batch`
- `api/app/modules/quality_gate/dependencies.py` — `QualityGateRepos` with all repository references
- `api/app/modules/assets/repository.py` — `AssetSLOLinkRepository`, `AssetGroupSLOLinkRepository`
- `api/app/modules/quality_gate/protocols.py` — `SLOBindingReader.find_for_asset()`
- `api/app/db/models.py` — `SLOBinding` model (has `target_type` = 'asset' | 'asset_group', `target_id`, `slo_name`, `data_source_name`)

### How SLO Links Are Currently Resolved

`resolve_single_trigger(asset_name, slo_name, ...)`:
1. Looks up asset by name
2. Looks up `AssetSLOLink` for (asset, slo_name) — gets `sli_name` + `data_source_name`
3. If not found, falls back to `SLOBinding.find_for_asset(asset_id, slo_name)` — gets `data_source_name` but needs SLI from SLO definition
4. Loads SLO definition + SLI definition
5. Returns `TriggerContext` with all resolved references

## Required Changes

### 1. New Endpoint: Trigger All SLOs for Asset

**POST `/evaluations/asset`** (or make `slo_name` optional on existing POST `/evaluations`)

Request:
```json
{
  "asset_name": "checkout-api",
  "evaluation_name": "batch-test",
  "period_start": "2026-03-15T08:00:00Z",
  "period_end": "2026-03-15T08:30:00Z",
  "variables": {}
}
```

Response:
```json
{
  "evaluation_ids": ["uuid1", "uuid2", "uuid3"],
  "slo_names": ["http-availability-slo", "agg-latency-slo", "plugin/auth"],
  "status": "pending"
}
```

### 2. New Function: Resolve All SLOs for Asset

Create `resolve_all_slos_for_asset(asset_id, asset_name, repos)` that returns all linked SLO names from ALL three sources:

```python
async def resolve_all_slos_for_asset(
    asset_id: uuid.UUID,
    repos: QualityGateRepos,
) -> list[str]:
    """Collect all SLO names linked to an asset from all binding sources."""
    slo_names: set[str] = set()

    # Source 1: Direct AssetSLOLinks
    asset_links = await repos.slo_link_repo.list_by_asset(asset_id)
    for lnk in asset_links:
        slo_names.add(lnk.slo_name)

    # Source 2: AssetGroupSLOLinks (from groups the asset belongs to)
    groups = await repos.asset_group_repo.list_groups_for_asset(asset_id)
    for group in groups:
        group_links = await repos.group_link_repo.list_by_group(group.id)
        for gl in group_links:
            slo_names.add(gl.slo_name)

    # Source 3: SLOBindings (direct asset bindings + group bindings)
    bindings = await repos.binding_repo.list_for_asset(asset_id)
    for binding in bindings:
        slo_names.add(binding.slo_name)

    return sorted(slo_names)
```

**Note**: `list_groups_for_asset` and `list_for_asset` may need to be added to the repositories. Check if they exist:
- `AssetGroupRepository` — needs `list_groups_for_asset(asset_id)` to find which groups contain this asset
- `SLOBindingRepository` — needs `list_for_asset(asset_id)` that returns all bindings targeting this asset OR any group containing this asset

### 3. Fix `_scan_batch_members` to Include SLOBindings

The batch trigger must also use the same `resolve_all_slos_for_asset` function so it doesn't miss SLOBindings. Replace the current manual resolution with the unified function.

### 4. Make `slo_name` Optional on Single Trigger

In `TriggerRequest`, make `slo_name: str | None = None`. When None, resolve all SLOs and create one evaluation per SLO (same as the new endpoint). When provided, behave as before (single SLO).

### 5. Seed Script Update

Update `scripts/seed_evaluations.py` to use the asset-level trigger instead of per-SLO triggers. The `ASSETS` list should just be asset names, not (asset, slo) pairs. This ensures seeded data matches what the UI expects.

Update `scripts/e2e_tests.py` to test the new asset-level trigger.

## Testing

- Unit test: `resolve_all_slos_for_asset` returns all 3 binding types
- Unit test: asset-level trigger creates correct number of evaluations
- Integration test: trigger `checkout-api` and verify evaluations exist for `http-availability-slo`, `agg-latency-slo`, AND `plugin/auth`
- E2E: `batch-test` for `core-services` should produce evaluations for all SLOs including template-generated ones

## Context for Logging Changes (Same Branch)

This branch also has uncommitted logging improvements that should be committed first:

- **structlog routed through stdlib logging** — `api/app/logging_config.py` uses `ProcessorFormatter` so both structlog and stdlib logs go to the same RotatingFileHandler
- **Worker detailed logging** — `evaluation context`, `adapter raw response`, per-indicator `indicator result`, `evaluation scored` — all bound with `evaluation_id` for grep-based tracing
- **Mock adapter logging** — every query logged with namespace, time range, per-metric CSV lookup results
- **Adapter client** — logs actual values/errors dicts (not just counts)
- **RotatingFileHandler** — 10 MB x 100 files, configured via `LOG_DIR` env var
- **dev-start.sh** — cleans `out/logs/` on restart, exports `LOG_DIR` for all services

## Other Uncommitted Changes on This Branch

These are all on the `phase1b` worktree (`/home/domik/projects/tropek/.worktrees/phase1b`), branch `main`, uncommitted:

1. **Scoring: missing data → ERROR** (`api/app/modules/quality_gate/engine/scoring.py`) — `value is None` returns `IndicatorStatus.ERROR` instead of `FAIL`, score=0, contributes_to_score=True
2. **Worker: fetch_errors override** (`api/app/modules/quality_gate/worker.py`) — adapter errors set `metrics_fetched[err_name] = None` so engine sees missing data
3. **Worker: SLI rows write 0.0 for None** — trend charts show dip instead of gap
4. **Mock adapter: CSV lookup for aggregated mode** (`adapters/mock/app/main.py`) — checks CSV store, returns errors when no data exists
5. **Mock scenario: `agg-latency-sli` metric** (`adapters/mock/scenarios/stable.yaml`) — CSV data for aggregated SLI
6. **UI: error status** (`ui/src/lib/status.ts`) — `error` entries in `STATUS_TEXT` and `STATUS_LABEL`
7. **Prometheus adapter: better error logging** — `logger.warning` with context instead of `logger.exception` for expected "no data" errors
8. **Test updated** (`api/tests/engine/test_scoring.py`) — `test_objective_missing_metric_is_error` expects `IndicatorStatus.ERROR`

All unit tests pass (278 passed). The changes need to be committed before starting the asset-level trigger work.
