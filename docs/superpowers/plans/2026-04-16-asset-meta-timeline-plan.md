# Asset Meta Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a collapsible Gantt-style "asset meta timeline" section inside the evaluation detail view that shows an asset's meta-state history (hierarchical versions, flags, hardware) derived at query time from source-tagged snapshots, pinned to the focus eval's timestamp.

**Architecture:**

- Server: a new `asset_meta` FastAPI module with three append-only tables, an ingest endpoint, and two read endpoints (full + summary). The read path is a pure ~20-function derivation stack (snapshot → raw spans → conflict-resolved → clipped → vis-timeline wire format). Zero I/O below `timeline/`.
- UI: a new top-level feature `ui/src/features/meta_timeline/` following the DTO/Domain/Mapper layering. Renders via `vis-timeline` in a default-collapsed single-row strip placed between the heatmap and the first table on the eval detail page.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, Alembic, pytest (unit + integration); React 19, TypeScript, React Query, vis-timeline 8.x, Vitest + Testing Library + happy-dom.

**Spec:** `docs/superpowers/specs/2026-04-16-asset-meta-timeline-design.md`. This plan references spec sections heavily instead of duplicating code — the implementer MUST read the relevant sections before each task. The spec's §7 function decomposition is a binding contract.

**Supporting references:**
- `CLAUDE.md` — project conventions (shell discipline, integration test flow, UI testing caveats).
- `docs/superpowers/specs/2026-04-12-ui-layering-design.md` — DTO/domain/mapper layering pattern.
- `api/tropek/modules/quality_gate/` — existing layered module to mirror.
- `api/tropek/modules/assets/` — simpler module reference (single-file service/repo/router).

---

## Chunk overview

Each chunk is a reviewable unit sized to land as one PR. Each chunk leaves the codebase green (lint + typecheck + tests pass). Review checkpoints close each chunk.

1. **DB schema + ORM models + migration + repository layer** — schema in place, repo tested against real DB.
2. **Pure derivation stack** — the §7.1–§7.6 sub-package + §6.7 `count_distinct_leaf_paths`, zero I/O, every function TDD'd.
3. **Ingest path (schemas + service + router)** — POST endpoint live with Pydantic validation + integration tests.
4. **Read + summary endpoints** — GET endpoints live with integration tests, OpenAPI schema exported, UI types regenerated.
5. **UI feature scaffolding** — `vis-timeline` installed; feature layout at `features/meta_timeline/` (api / domain / mappers / hooks / index / ui-types) following the layering spec.
6. **MetaTimeline React wrapper** — imperative vis-timeline wrapper + tooltip renderer + base CSS.
7. **CollapsedStrip + MetaTimelineSection + EvaluationDetail integration** — collapsible section wired into the eval detail page.
8. **CSS theme variables** — semantic tokens for meta-span / marker added to all three themes (dark / current / light).
9. **Manual verification** — the §10.4 checklist + §14 acceptance criteria, no code changes.

---

## Chunk 1 — DB schema + ORM models + migration + repository layer

**Why first:** every later chunk depends on the three new tables existing and being reachable via a repository.

**Files:**
- Modify: `api/tropek/db/models.py` — add `AssetMetaSnapshot`, `AssetMetaValue`, `AssetMetaClosure` ORM classes.
- Create: `api/alembic/versions/003_asset_meta_tables.py` — regenerated, NOT hand-written.
- Create: `api/tropek/modules/asset_meta/__init__.py` — empty package marker.
- Create: `api/tropek/modules/asset_meta/repositories.py` — `AssetMetaRepository` with `insert_snapshot`, `insert_values`, `insert_closures`, `load_snapshots_for_derivation`.
- Create: `api/tests/asset_meta/__init__.py` — new test package.
- Create: `api/tests/asset_meta/db/__init__.py`
- Create: `api/tests/asset_meta/db/conftest.py` — re-uses the existing db fixture stack (see `api/tests/db/conftest.py` and `api/tests/quality_gate/db/conftest.py` for the pattern).
- Create: `api/tests/asset_meta/db/test_repository.py` — integration tests for the repo.

### Task 1.1: Define ORM models (spec §4.1, §13.1)

- [ ] **Step 1.1.1: Read spec §4.1 and §13.1** to confirm columns, indexes, FK cascade, and `TEXT[]` → `ARRAY(Text)` mapping. Also re-read `api/tropek/db/models.py:36-130` (the `AssetType` / `Asset` models) to match the column-alignment and docstring style used by neighbouring models.

- [ ] **Step 1.1.2: Add `AssetMetaSnapshot`** to `api/tropek/db/models.py` immediately after the existing `Asset` model group. Columns per §4.1: `id UUID PK default uuid4`, `asset_id UUID FK assets.id ON DELETE CASCADE not null`, `source Text not null`, `observed_at DateTime(tz=True) not null`, `created_at DateTime(tz=True) server_default=now() not null`. Two indexes: `idx_asset_meta_snapshots_asset_observed` on `(asset_id, observed_at)` and `idx_asset_meta_snapshots_asset_source_observed` on `(asset_id, source, observed_at)`. Use the same `fmt: off` / aligned-column style as `Asset`.

- [ ] **Step 1.1.3: Add `AssetMetaValue`** per §4.1. Columns: `id BigInteger PK autoincrement`, `snapshot_id UUID FK asset_meta_snapshots.id ON DELETE CASCADE not null`, `path ARRAY(Text) not null`, `value Text not null`. Unique constraint on `(snapshot_id, path)` and index `idx_asset_meta_values_snapshot` on `snapshot_id`.

- [ ] **Step 1.1.4: Add `AssetMetaClosure`** per §4.1. Columns: `id BigInteger PK autoincrement`, `snapshot_id UUID FK asset_meta_snapshots.id ON DELETE CASCADE not null`, `path ARRAY(Text) not null`. Unique constraint on `(snapshot_id, path)` and index `idx_asset_meta_closures_snapshot` on `snapshot_id`.

- [ ] **Step 1.1.5: Verify imports** — ensure `ARRAY`, `BigInteger`, `Text`, `UUID`, `DateTime`, `ForeignKey`, `Index`, `UniqueConstraint`, `func` are all in the module's import block. Add anything missing.

- [ ] **Step 1.1.6: Run typecheck** to confirm the models compile.
  Run: `uv run --directory api mypy tropek/db/models.py`
  Expected: success, no new errors.

- [ ] **Step 1.1.7: Commit**
  ```bash
  git add api/tropek/db/models.py
  git commit -m "feat(db): add asset meta snapshot/value/closure ORM models"
  ```

### Task 1.2: Regenerate the Alembic migration (spec §13.1, CLAUDE.md "Migration workflow" memory)

- [ ] **Step 1.2.1: Re-read** CLAUDE.md § "Integration Tests — REQUIRED STEPS" and the memory entry `Migration workflow` (never hand-write migrations). Confirm the dev database is running (`just up` if not) — `db-regen-migrations.sh` requires it.

- [ ] **Step 1.2.2: Run the regeneration script.**
  Run: `./scripts/db-regen-migrations.sh`
  Expected: a new file appears under `api/alembic/versions/` (likely `003_*.py`) containing `create_table("asset_meta_snapshots")`, `create_table("asset_meta_values")`, `create_table("asset_meta_closures")`, and matching indexes.

- [ ] **Step 1.2.3: Inspect the generated migration** and confirm it matches §4.1 exactly (3 tables, FK cascades, correct index columns, correct uniques). Do NOT edit it by hand — if something is wrong, fix the ORM model and re-run the script.

- [ ] **Step 1.2.4: Apply migrations to dev DB.**
  Run: `just migrate`
  Expected: "alembic upgrade head" succeeds.

- [ ] **Step 1.2.5: Apply migrations to test DB.** (Test infra must be up — if not, `just test-env`.)
  Run: `just migrate-test`
  Expected: success.

- [ ] **Step 1.2.6: Commit**
  ```bash
  git add api/alembic/versions/
  git commit -m "feat(db): regenerate migration for asset meta tables"
  ```

### Task 1.3: Write the repository layer (spec §8.1)

- [ ] **Step 1.3.1: Read** `api/tropek/modules/assets/repository.py:1-150` for the existing repo style (async SQLAlchemy, `self._session`, docstrings, `flush` without commit).

- [ ] **Step 1.3.2: Create `api/tropek/modules/asset_meta/__init__.py`** as an empty file.

- [ ] **Step 1.3.3: Create `api/tropek/modules/asset_meta/repositories.py`** with a single class `AssetMetaRepository(session: AsyncSession)` exposing four async methods:
  - `insert_snapshot(asset_id: UUID, source: str, observed_at: datetime) -> AssetMetaSnapshot` — inserts one row, flushes, returns it.
  - `insert_values(snapshot_id: UUID, entries: Sequence[MetaValueInput]) -> None` — bulk insert via `session.add_all()` or `session.execute(insert(AssetMetaValue), [...])`. Forward reference the Pydantic type via a `TYPE_CHECKING` import — the repo does not validate, it only persists.
  - `insert_closures(snapshot_id: UUID, entries: Sequence[MetaClosureInput]) -> None` — same pattern.
  - `load_snapshots_for_derivation(asset_id: UUID, until: datetime) -> list[SnapshotWithEntries]` — loads all snapshots with `observed_at <= until`, joined with their values and closures rows, grouped in Python into the `SnapshotWithEntries` dataclass that will be defined in Chunk 2. For now, forward-reference the type in `TYPE_CHECKING` or use a typed-dict placeholder that Chunk 2 replaces. Order: `observed_at ASC, id ASC`.

  **Repository decision note:** because `load_snapshots_for_derivation` returns a type defined in the timeline sub-package (Chunk 2), prefer building the return value as `list[dict]` with fields `source`, `observed_at`, `values` (list of `(path_list, value_str)` tuples), `closures` (list of `path_list`). Chunk 2's `SnapshotWithEntries` is a thin `NamedTuple` / `@dataclass(frozen=True)` over exactly those fields — so the repository can stay unchanged after Chunk 2 lands, as long as the field names match. Declare the shape here via a `TypedDict` named `SnapshotRow` to keep typing clean.

- [ ] **Step 1.3.4: Run lint + typecheck.**
  Run: `./scripts/api-test.sh --tail 5` first won't help; instead run `uv run ruff check api/tropek/modules/asset_meta/ && uv run --directory api mypy tropek/modules/asset_meta/`.
  Expected: clean.

### Task 1.4: Repository integration tests

- [ ] **Step 1.4.1: Read** `api/tests/quality_gate/db/conftest.py` and one existing repository integration test (e.g. `test_indicator_repository.py`) to copy the fixture pattern (session fixture, rollback between tests).

- [ ] **Step 1.4.2: Create `api/tests/asset_meta/db/conftest.py`** that re-uses the session fixture from `api/tests/db/conftest.py`. If the existing conftest exposes a session fixture at the right scope, simply `from api.tests.db.conftest import *  # noqa: F401,F403` — or follow whatever pattern the quality_gate tests use.

- [ ] **Step 1.4.3: Create `api/tests/asset_meta/db/test_repository.py`** marked `@pytest.mark.integration` at the module level. Test cases (each creates an Asset fixture first, then exercises the repo):
  1. `test_insert_snapshot_returns_row_with_generated_id` — call `insert_snapshot`, assert `id`, `asset_id`, `source`, `observed_at` populated.
  2. `test_insert_values_persists_all_entries` — insert a snapshot, insert 3 values, re-query the table, assert all 3 rows present.
  3. `test_insert_closures_persists_all_entries` — same pattern for closures.
  4. `test_load_snapshots_for_derivation_respects_until_bound` — insert 3 snapshots at T0, T1, T2; load with `until=T1`; assert only T0 and T1 returned.
  5. `test_load_snapshots_for_derivation_orders_by_observed_then_id` — insert 2 snapshots with identical `observed_at` but different `id`s; assert `id ASC` is the tie-break.
  6. `test_load_snapshots_for_derivation_hydrates_values_and_closures` — insert snapshot with 2 values and 1 closure; assert both collections are returned together in one row.
  7. `test_cascade_delete_when_asset_removed` — insert snapshot, delete asset, assert snapshot + its values + closures are gone.

- [ ] **Step 1.4.4: Run the tests.**
  Run: `./scripts/api-test.sh --tail 10 -m integration tests/asset_meta/db/test_repository.py -v`
  Expected: all 7 tests pass.

- [ ] **Step 1.4.5: Commit**
  ```bash
  git add api/tropek/modules/asset_meta/ api/tests/asset_meta/
  git commit -m "feat(asset-meta): add repository with integration tests"
  ```

### Chunk 1 review checkpoint

- [ ] ORM models compile and mypy is clean on `api/tropek/db/models.py`.
- [ ] Migration was regenerated via `db-regen-migrations.sh` and was not hand-edited.
- [ ] `just migrate` and `just migrate-test` both succeed.
- [ ] All 7 repository integration tests pass.
- [ ] `uv run ruff check api/` is clean for the new files.
- [ ] No changes outside `api/tropek/db/models.py`, `api/alembic/versions/`, `api/tropek/modules/asset_meta/`, `api/tests/asset_meta/`.

---

## Chunk 2 — Pure derivation stack (`asset_meta/timeline/` sub-package)

**Why second:** the derivation stack is pure Python with zero I/O, so it can be fully TDD'd before any HTTP surface exists. Every function from §7 gets its own focused test. This is the largest chunk — treat each file as a sub-task.

**Files:**
- Create: `api/tropek/modules/asset_meta/timeline/__init__.py` — re-exports the public top-level functions (`build_timeline_response`, `count_distinct_leaf_paths`).
- Create: `api/tropek/modules/asset_meta/timeline/types.py` — `RawSpan`, `ClippedSpan`, `OpenSpan`, `SnapshotWithEntries`, type aliases.
- Create: `api/tropek/modules/asset_meta/timeline/derivation.py` — §7.1.
- Create: `api/tropek/modules/asset_meta/timeline/conflict_resolution.py` — §7.2.
- Create: `api/tropek/modules/asset_meta/timeline/clipping.py` — §7.3.
- Create: `api/tropek/modules/asset_meta/timeline/tree_builder.py` — §7.4.
- Create: `api/tropek/modules/asset_meta/timeline/item_emitter.py` — §7.5.
- Create: `api/tropek/modules/asset_meta/timeline/summary.py` — §6.7 `count_distinct_leaf_paths`.
- Create: `api/tropek/modules/asset_meta/timeline/orchestrator.py` — §7.6.
- Create: `api/tests/asset_meta/timeline/__init__.py`
- Create: `api/tests/asset_meta/timeline/test_types.py` — smoke test for constructors (1-2 assertions).
- Create: `api/tests/asset_meta/timeline/test_derivation.py` — §10.1 rows for §7.1.
- Create: `api/tests/asset_meta/timeline/test_conflict_resolution.py` — §10.1 rows for §7.2.
- Create: `api/tests/asset_meta/timeline/test_clipping.py` — §10.1 rows for §7.3.
- Create: `api/tests/asset_meta/timeline/test_tree_builder.py` — §10.1 rows for §7.4.
- Create: `api/tests/asset_meta/timeline/test_item_emitter.py` — §10.1 rows for §7.5.
- Create: `api/tests/asset_meta/timeline/test_summary.py` — §6.7.
- Create: `api/tests/asset_meta/timeline/test_orchestrator.py` — §10.1 end-to-end + §10.1 scenarios 1–19.

**Test discipline for every task below:**
- TDD: write the failing test(s) first, run to see them fail, implement, re-run to see them pass, commit.
- One file per commit when possible; if a file is small (< 40 lines), combine its tests and implementation into one commit.
- Tests run via: `./scripts/api-test.sh --tail 10 tests/asset_meta/timeline/test_<name>.py -v`

### Task 2.1: `types.py`

- [ ] **Step 2.1.1: Read spec §7.1 and §8.1** to confirm the exact field names and types. The public types are:
  - `RawSpan` — `source: str`, `path: list[str]`, `value: str`, `start: datetime`, `end: datetime | None`, `end_reason: Literal["value_change", "closed", "open"]`.
  - `ClippedSpan` — `source: str`, `path: list[str]`, `value: str`, `start: datetime`, `end: datetime`, `className: str`.
  - `OpenSpan` — `value: str`, `span_start: datetime` (private to derivation but defined here so it can be imported by tests).
  - `SnapshotWithEntries` — `source: str`, `observed_at: datetime`, `values: list[tuple[list[str], str]]`, `closures: list[list[str]]`.
  - Type alias: `OpenSpanMap = dict[tuple[str, tuple[str, ...]], OpenSpan]`.

  All concrete types are `@dataclass(frozen=True)` (or Pydantic per the memory rule if any field needs validation — the spec uses plain dataclasses, which is fine here because input is already validated at the Pydantic boundary).

- [ ] **Step 2.1.2: Write `test_types.py`** with one constructor test per dataclass asserting the field values round-trip. This catches rename typos quickly.

- [ ] **Step 2.1.3: Run** `./scripts/api-test.sh --tail 5 tests/asset_meta/timeline/test_types.py -v` — expect import error.

- [ ] **Step 2.1.4: Implement `types.py`** per the spec's type definitions. Keep the module small — <60 lines.

- [ ] **Step 2.1.5: Run tests** — expect pass.

- [ ] **Step 2.1.6: Commit**
  ```bash
  git add api/tropek/modules/asset_meta/timeline/__init__.py api/tropek/modules/asset_meta/timeline/types.py api/tests/asset_meta/timeline/
  git commit -m "feat(asset-meta): add timeline types module"
  ```

### Task 2.2: `derivation.py` (§7.1)

Functions to implement (names must match §7.1 exactly — they are a binding contract):
1. `is_prefix(prefix: tuple, full: tuple) -> bool`
2. `apply_value(open_spans, source, path, value, observed_at, emitted) -> None`
3. `close_cascade(open_spans, source, ancestor, closed_at, emitted) -> None`
4. `apply_snapshot(open_spans, snapshot, emitted) -> None`
5. `finalize_open_spans(open_spans, emitted) -> None`
6. `derive_raw_spans(snapshots) -> list[RawSpan]`

Test cases (§10.1 minimums — the test file MUST have at least these and may add more):

- [ ] **Step 2.2.1: Write `test_derivation.py` with failing tests for `is_prefix`** covering: equal prefix, strict prefix, suffix-not-prefix, disjoint, empty prefix on non-empty, empty prefix on empty. Run — expect `ImportError`.

- [ ] **Step 2.2.2: Implement `is_prefix`.** Per §7.1 pseudocode. Run — expect pass.

- [ ] **Step 2.2.3: Add failing tests for `apply_value`** covering: new key opens a span (no emission, open_spans grows); same value no-op (no emission, no state change); different value closes old + opens new (one RawSpan emitted with `end_reason="value_change"`). Run — expect fail.

- [ ] **Step 2.2.4: Implement `apply_value`.** Run — expect pass.

- [ ] **Step 2.2.5: Add failing tests for `close_cascade`** covering: closes exact match; closes descendants of same source; does not touch other sources' spans at the same path; no-op when path has no open span (idempotent-safe per §7.1 invariant). Run — expect fail.

- [ ] **Step 2.2.6: Implement `close_cascade`.** Run — expect pass.

- [ ] **Step 2.2.7: Add failing tests for `apply_snapshot`** covering: closures-before-values ordering (fixture: open `("foo",)` at T0, snapshot at T1 with both `closed=[["foo"]]` AND `values=[(["foo"], "new")]`; expected: one emitted span `[T0, T1, end_reason="closed"]` AND one still-open span starting T1 with value "new"); plain values-only snapshot; plain closed-only snapshot. Run — expect fail.

- [ ] **Step 2.2.8: Implement `apply_snapshot`.** Run — expect pass.

- [ ] **Step 2.2.9: Add failing tests for `finalize_open_spans`** covering: converts each remaining open_span entry to a `RawSpan` with `end=None` and `end_reason="open"`; empty map produces nothing. Run — expect fail.

- [ ] **Step 2.2.10: Implement `finalize_open_spans`.** Run — expect pass.

- [ ] **Step 2.2.11: Add failing tests for `derive_raw_spans`** — 3–4 integration fixtures exercising the whole walk end-to-end (per §10.1 "derive_raw_spans: 3–4 integration fixtures"):
  - `test_single_value_snapshot` — one snapshot with one value → one RawSpan with `end=None, end_reason="open"`.
  - `test_value_then_value_change` — two snapshots same path, different values → two RawSpans, back-to-back.
  - `test_daily_heartbeat_collapses` — 30 snapshots identical values → exactly one open-ended span (scenario 9 in §10.1).
  - `test_cascading_close` — open `["app"]`, `["app","plug"]`, `["app","plug","alpha"]`, then close `["app"]` → three spans all with `end_reason="closed"` at the close time (scenario 19 in §10.1).

  Run — expect fail.

- [ ] **Step 2.2.12: Implement `derive_raw_spans` + `apply_snapshot` wiring** (it's a 5-line loop). Run — expect pass.

- [ ] **Step 2.2.13: Run lint + typecheck** for the new file.
  Run: `uv run ruff check api/tropek/modules/asset_meta/timeline/derivation.py && uv run --directory api mypy tropek/modules/asset_meta/timeline/derivation.py`
  Expected: clean.

- [ ] **Step 2.2.14: Commit**
  ```bash
  git add api/tropek/modules/asset_meta/timeline/derivation.py api/tests/asset_meta/timeline/test_derivation.py
  git commit -m "feat(asset-meta): add span derivation with §7.1 function tests"
  ```

### Task 2.3: `conflict_resolution.py` (§7.2)

Functions:
1. `group_spans_by_path(spans) -> dict[tuple, list[RawSpan]]`
2. `compute_latest_observation_per_source(path_spans) -> dict[str, datetime]`
3. `pick_winning_source(sources_latest) -> str`
4. `log_source_conflict(logger, asset_id, path, sources_latest, winner) -> None`
5. `resolve_multi_source_conflicts(spans, asset_id, logger) -> list[RawSpan]`

- [ ] **Step 2.3.1: Write failing tests for `group_spans_by_path`** — empty input, single-path input, multi-path input with duplicates within a path. Run — expect fail.

- [ ] **Step 2.3.2: Implement `group_spans_by_path`.** Run — expect pass.

- [ ] **Step 2.3.3: Write failing tests for `compute_latest_observation_per_source`** — two sources each with their own spans (winner based on latest end); an open span (`end=None`) beats a closed past span (tests the `_SENTINEL_OPEN_END` logic from §7.2). Run — expect fail.

- [ ] **Step 2.3.4: Implement `compute_latest_observation_per_source`** with the `_SENTINEL_OPEN_END = datetime.max.replace(tzinfo=UTC)` module constant from §7.2. Run — expect pass.

- [ ] **Step 2.3.5: Write failing tests for `pick_winning_source`** — unambiguous winner; tie on timestamp → alphabetical source name wins; single source returns itself. ~5 cases. Run — expect fail.

- [ ] **Step 2.3.6: Implement `pick_winning_source`.** Run — expect pass.

- [ ] **Step 2.3.7: Write failing tests for `log_source_conflict`** using pytest's `caplog` fixture — assert the warning message key is `"asset_meta_timeline.multi_source_conflict"` and `extra` carries `asset_id`, `path`, `sources`, `winner`. Run — expect fail.

- [ ] **Step 2.3.8: Implement `log_source_conflict`.** Run — expect pass.

- [ ] **Step 2.3.9: Write failing tests for `resolve_multi_source_conflicts`** — single-source path passes through unchanged; two-source conflict drops loser's spans and emits warning; three sources all contributing to same path picks correct winner. Run — expect fail.

- [ ] **Step 2.3.10: Implement `resolve_multi_source_conflicts`** as a thin composition per §7.2. Run — expect pass.

- [ ] **Step 2.3.11: Commit**
  ```bash
  git add api/tropek/modules/asset_meta/timeline/conflict_resolution.py api/tests/asset_meta/timeline/test_conflict_resolution.py
  git commit -m "feat(asset-meta): add multi-source conflict resolution with tests"
  ```

### Task 2.4: `clipping.py` (§7.3)

Functions:
1. `compute_span_classes(span, window_from, window_to, clipped_start) -> list[str]`
2. `clip_one_span(span, window_from, window_to) -> ClippedSpan | None`
3. `clip_spans(spans, window_from, window_to) -> list[ClippedSpan]`

- [ ] **Step 2.4.1: Write failing tests for `compute_span_classes`** — exhaust every combination of:
  - `clipped_start > span.start` vs `==` (clipped-left yes/no)
  - `span.end is None` vs `span.end > window_to` vs `span.end <= window_to` (open / clipped-right / neither)
  - `end_reason == "closed"` vs not (closed class yes/no)

  That's 2 × 3 × 2 = 12 cases minimum. Each asserts the exact class list returned (order: base first, then `meta-span-clipped-left`, then `-open`/`-clipped-right`, then `-closed`). Run — expect fail.

- [ ] **Step 2.4.2: Implement `compute_span_classes`** per §7.3 pseudocode. Run — expect pass.

- [ ] **Step 2.4.3: Write failing tests for `clip_one_span`** — span entirely before window (returns None); entirely after window (returns None); span exactly at `window_from` boundary; span exactly at `window_to` boundary; zero-length span inside window; span with `end=None` (open) → clipped to `window_to` with `meta-span-open` class. Run — expect fail.

- [ ] **Step 2.4.4: Implement `clip_one_span`.** Run — expect pass.

- [ ] **Step 2.4.5: Write failing tests for `clip_spans`** — composition over a list with a mix of in-window, before-window, and after-window spans; assert length of result matches the in-window count. Run — expect fail.

- [ ] **Step 2.4.6: Implement `clip_spans`.** Run — expect pass.

- [ ] **Step 2.4.7: Commit**
  ```bash
  git add api/tropek/modules/asset_meta/timeline/clipping.py api/tests/asset_meta/timeline/test_clipping.py
  git commit -m "feat(asset-meta): add window clipping with class vocabulary tests"
  ```

### Task 2.5: `tree_builder.py` (§7.4)

Functions:
1. `encode_path_as_group_id(path) -> str`
2. `collect_distinct_paths(spans) -> set[tuple]`
3. `expand_with_synthetic_ancestors(paths) -> set[tuple]`
4. `compute_children_map(paths) -> dict[tuple, list[tuple]]`
5. `sort_groups_deterministically(paths) -> list[tuple]`
6. `build_group_entry(path, children_map) -> dict`
7. `build_groups_wire(clipped_spans) -> list[dict]`

- [ ] **Step 2.5.1: Write failing tests for `encode_path_as_group_id`** — simple path; path with quotes; path with `/`; path with `:`; path with Unicode (e.g. `"café"`). Each test asserts `json.loads(encode_path_as_group_id(path))` round-trips to the original list. Run — expect fail.

- [ ] **Step 2.5.2: Implement `encode_path_as_group_id`** using `json.dumps(..., ensure_ascii=False, separators=(",", ":"))` per §7.4. Run — expect pass.

- [ ] **Step 2.5.3: Write failing tests for `collect_distinct_paths`** — empty; duplicates deduplicated; different paths preserved. Run — expect fail.

- [ ] **Step 2.5.4: Implement `collect_distinct_paths`.** Run — expect pass.

- [ ] **Step 2.5.5: Write failing tests for `expand_with_synthetic_ancestors`** — leaf-only input (one deep path) → produces all prefixes; already-expanded input is a no-op (idempotent). Run — expect fail.

- [ ] **Step 2.5.6: Implement `expand_with_synthetic_ancestors`.** Run — expect pass.

- [ ] **Step 2.5.7: Write failing tests for `compute_children_map`** — parent with two children in the full set returns both as its children; leaf is absent as a key; root path's parent is not emitted. Run — expect fail.

- [ ] **Step 2.5.8: Implement `compute_children_map`.** Run — expect pass.

- [ ] **Step 2.5.9: Write failing tests for `sort_groups_deterministically`** — same input in different initial orderings produces identical output; roots (depth 1) come before depth 2; lexicographic within depth. Run — expect fail.

- [ ] **Step 2.5.10: Implement `sort_groups_deterministically`.** Run — expect pass.

- [ ] **Step 2.5.11: Write failing tests for `build_group_entry`** — leaf (no children) returns dict with only `id` and `content`; parent returns dict with `id`, `content`, `nestedGroups` (sorted child ids), `showNested: False`. Run — expect fail.

- [ ] **Step 2.5.12: Implement `build_group_entry`.** Run — expect pass.

- [ ] **Step 2.5.13: Write failing end-to-end test for `build_groups_wire`** using a fixture of three clipped spans covering `["app-A"]`, `["app-A","plug-1","alpha"]`, `["cpu-cores"]`. Assert the output includes synthetic `["app-A","plug-1"]` with `nestedGroups` pointing at alpha; assert `["app-A"]` has `plug-1` in its `nestedGroups`; assert `cpu-cores` has no `nestedGroups`. Run — expect fail.

- [ ] **Step 2.5.14: Implement `build_groups_wire`** as the §7.4 composition. Run — expect pass.

- [ ] **Step 2.5.15: Commit**
  ```bash
  git add api/tropek/modules/asset_meta/timeline/tree_builder.py api/tests/asset_meta/timeline/test_tree_builder.py
  git commit -m "feat(asset-meta): add tree builder with per-helper unit tests"
  ```

### Task 2.6: `item_emitter.py` (§7.5)

Functions:
1. `item_from_span(span, index) -> dict`
2. `build_items_wire(spans) -> list[dict]`

- [ ] **Step 2.6.1: Write failing tests for `item_from_span`** — one test per output field (`id`, `group`, `content`, `start`, `end`, `type`, `className`, `source`). Each test builds a `ClippedSpan` fixture, calls `item_from_span(span, index=7)`, and asserts the corresponding field. Run — expect fail.

- [ ] **Step 2.6.2: Implement `item_from_span`** importing `encode_path_as_group_id` from `.tree_builder` (DRY per §7.5). Run — expect pass.

- [ ] **Step 2.6.3: Write failing test for `build_items_wire`** — composition over a list of 3 clipped spans; assert result is length 3 and `id`s are `"s0"`, `"s1"`, `"s2"`. Run — expect fail.

- [ ] **Step 2.6.4: Implement `build_items_wire`.** Run — expect pass.

- [ ] **Step 2.6.5: Commit**
  ```bash
  git add api/tropek/modules/asset_meta/timeline/item_emitter.py api/tests/asset_meta/timeline/test_item_emitter.py
  git commit -m "feat(asset-meta): add vis-timeline item emitter with field-level tests"
  ```

### Task 2.7: `summary.py` (§6.7)

- [ ] **Step 2.7.1: Write failing test for `count_distinct_leaf_paths`** — input of 3 clipped spans with paths `[A, B, B]` (B appears twice) returns 2. Run — expect fail.

- [ ] **Step 2.7.2: Implement `count_distinct_leaf_paths`** as a one-liner per §6.7. Run — expect pass.

- [ ] **Step 2.7.3: Commit**
  ```bash
  git add api/tropek/modules/asset_meta/timeline/summary.py api/tests/asset_meta/timeline/test_summary.py
  git commit -m "feat(asset-meta): add distinct-leaf count for summary endpoint"
  ```

### Task 2.8: `orchestrator.py` (§7.6) — end-to-end scenarios from §10.1

- [ ] **Step 2.8.1: Write `test_orchestrator.py`** covering the **full §10.1 end-to-end scenario list**. Each test is a small fixture of `SnapshotWithEntries` → expected `{"groups": [...], "items": [...]}`. The scenarios (all 19) MUST be covered here — either inline in this file or split across this file and `test_derivation.py`. The complete list:

  1. Single snapshot with one value → one still-open span clipped to `to`.
  2. Two snapshots with identical value → one long span.
  3. Two snapshots with different values for same path → two back-to-back spans.
  4. Snapshot with explicit closure → span ends at closure time.
  5. Cascading closure: parent closes all open descendants in same source.
  6. Cascading closure does NOT affect other sources.
  7. Close-and-reopen in same snapshot.
  8. Collection-gap case: silent source does not cause spurious close/reopen.
  9. Consecutive identical-value snapshots collapse into one span.
  10. Multi-source conflict on same path: most-recent-wins, warning logged.
  11. Synthetic intermediates: only leaf pushed → ancestor groups emitted.
  12. Left-edge clipping: span started before `from` → `meta-span-clipped-left`.
  13. Right-edge clipping distinct cases: `meta-span-open` vs `-clipped-right` vs `-closed`.
  14. Empty asset → `{"groups": [], "items": []}`.
  15. (Handled by Pydantic layer, noted here for completeness — add a comment explaining why no test.)
  16. `closed`-only snapshot terminates an existing span.
  17. `closed`-only targeting an already-closed path is a no-op.
  18. `closed`-only targeting a never-opened path is a no-op.
  19. `closed`-only cascading works across a subtree.

  Scenarios 1–3, 9, 19 may be covered in `test_derivation.py::test_derive_raw_spans` — if so, add a one-line comment in `test_orchestrator.py` cross-referencing the test that covers each. No scenario may go uncovered.

  Run — expect import errors / fails.

- [ ] **Step 2.8.2: Implement `orchestrator.py`** as the 5-line composition from §7.6. Import from the five sibling modules. Run — expect tests pass.

- [ ] **Step 2.8.3: Update `api/tropek/modules/asset_meta/timeline/__init__.py`** to re-export `build_timeline_response` and `count_distinct_leaf_paths` as the public API surface. Also import `SnapshotWithEntries` so the repository layer can use it without reaching into `types.py`.

- [ ] **Step 2.8.4: Run the full test subtree.**
  Run: `./scripts/api-test.sh --tail 20 tests/asset_meta/timeline/ -v`
  Expected: every §7 function has at least one passing test AND every §10.1 scenario 1–19 has a passing test.

- [ ] **Step 2.8.5: Run lint + mypy on the whole sub-package.**
  Run: `uv run ruff check api/tropek/modules/asset_meta/ && uv run --directory api mypy tropek/modules/asset_meta/`
  Expected: clean.

- [ ] **Step 2.8.6: Commit**
  ```bash
  git add api/tropek/modules/asset_meta/timeline/ api/tests/asset_meta/timeline/
  git commit -m "feat(asset-meta): add orchestrator and §10.1 end-to-end scenarios"
  ```

### Chunk 2 review checkpoint

- [ ] Every function listed in §7 has a matching implementation with the exact name from the spec.
- [ ] Every function listed in the §10.1 "Per-function test coverage" table has at least one dedicated test section.
- [ ] Every end-to-end scenario 1–19 in §10.1 is covered by a passing test (in `test_orchestrator.py` or `test_derivation.py`).
- [ ] The timeline sub-package imports nothing that requires I/O (no `AsyncSession`, no `httpx`, no `redis`).
- [ ] `./scripts/api-test.sh --tail 20 tests/asset_meta/timeline/ -v` shows all tests passing.
- [ ] `uv run ruff check api/tropek/modules/asset_meta/` clean.
- [ ] `uv run --directory api mypy tropek/modules/asset_meta/` clean.

---

## Chunk 3 — Ingest path (schemas + service + router)

**Why third:** derivation is provably correct and the repository exists; now expose the write path.

**Files:**
- Create: `api/tropek/modules/asset_meta/schemas.py` — Pydantic request/response models per §8.2.
- Create: `api/tropek/modules/asset_meta/service.py` — `create_meta_snapshot`, `_validate_payload_has_content`, `_ensure_asset_exists`, `_write_snapshot_rows`.
- Create: `api/tropek/modules/asset_meta/router.py` — FastAPI routes, starting with POST.
- Modify: `api/tropek/main.py` — register the new router.
- Create: `api/tests/asset_meta/test_schemas.py` — Pydantic validation unit tests.
- Create: `api/tests/asset_meta/test_service.py` — service-layer tests with in-memory fake repo (no DB).
- Create: `api/tests/asset_meta/db/test_ingest_endpoint.py` — integration tests hitting the real endpoint.

### Task 3.1: Pydantic schemas (§8.2)

- [ ] **Step 3.1.1: Read spec §5.2 (validation rules table) and §8.2 (schema code).** Re-read `api/tropek/modules/common/schemas.py` to confirm how `StrictInput` is defined and used by other modules.

- [ ] **Step 3.1.2: Write `test_schemas.py`** with failing unit tests for every validation rule in §5.2:
  - `source` pattern: valid passes; empty rejected; too-long rejected; invalid chars (space, `!`) rejected.
  - `observed_at`: naive datetime rejected; tz-aware accepted.
  - `values[].path`: `[]` rejected (length < 1); path with 7 entries rejected (> 6); entry with empty string rejected.
  - `values[].value`: empty string accepted (explicit per §5.2); 1025-char string rejected.
  - `closed[].path`: same rules as values path.
  - Duplicate path within `values` rejected.
  - Duplicate path within `closed` rejected.
  - Same path in both `values` and `closed` accepted (close-and-reopen, rule 3).
  - `values=[]` AND `closed=[]` — this validation is NOT part of the Pydantic schema per spec §8.2 note ("A service-layer check enforces 'values OR closed non-empty'"). Add an explicit comment in the test file stating this and cross-referencing `test_service.py::test_validate_payload_has_content_rejects_empty`.
  - Strict-input: unknown field in request is rejected (inherited from `StrictInput`).

  Run — expect import errors.

- [ ] **Step 3.1.3: Implement `schemas.py`** with `MetaValueInput`, `MetaClosureInput`, `MetaSnapshotCreate`, `MetaSnapshotCreated` per §8.2. Plus the read-side types (so Chunk 4 can pick them up without another import churn): `TimelineGroup`, `TimelineItem`, `TimelineResponse`, `TimelineSummaryResponse`. The read types are plain `BaseModel`, not `StrictInput` (they are responses). Use field names that exactly match §6.3/§6.7 wire format — the JSON emission goes through Pydantic so field aliases may be needed for `nestedGroups`/`showNested`/`className` (camelCase). Use `Field(alias=...)` with `model_config = ConfigDict(populate_by_name=True)`.

- [ ] **Step 3.1.4: Run tests.** Run: `./scripts/api-test.sh --tail 10 tests/asset_meta/test_schemas.py -v`. Expected: pass.

- [ ] **Step 3.1.5: Commit**
  ```bash
  git add api/tropek/modules/asset_meta/schemas.py api/tests/asset_meta/test_schemas.py
  git commit -m "feat(asset-meta): add Pydantic schemas with validation tests"
  ```

### Task 3.2: Service layer (§8.3)

- [ ] **Step 3.2.1: Write `test_service.py` failing tests** for each helper:
  - `test_validate_payload_has_content_rejects_empty` — payload with both `values=[]` and `closed=[]` raises `DomainValidationError`.
  - `test_validate_payload_has_content_accepts_values_only`.
  - `test_validate_payload_has_content_accepts_closed_only`.
  - `test_validate_payload_has_content_accepts_both`.
  - `test_ensure_asset_exists_raises_not_found_error` — fake repo returns False → raises `NotFoundError`.
  - `test_ensure_asset_exists_is_silent_when_present` — fake repo returns True → returns None.
  - `test_write_snapshot_rows_values_only` — fake repo records the calls; assert `insert_snapshot` called once, `insert_values` called once, `insert_closures` NOT called.
  - `test_write_snapshot_rows_closed_only` — symmetric.
  - `test_write_snapshot_rows_both` — both insert_values and insert_closures called.

  Use a simple dataclass-based fake repo (no `unittest.mock`) — the fake records invocation lists that tests assert on.

  Run — expect fails.

- [ ] **Step 3.2.2: Implement `service.py`** per §8.3 exactly. `create_meta_snapshot` is the thin orchestrator; the three helpers are its body split out. Use the existing `NotFoundError` and `DomainValidationError` from `tropek.modules.common.exceptions`. For `logger`, use `logging.getLogger(__name__)` at module level — the read path (Chunk 4) will pass it through to `build_timeline_response`.

- [ ] **Step 3.2.3: Run tests.** Run: `./scripts/api-test.sh --tail 10 tests/asset_meta/test_service.py -v`. Expected: pass.

- [ ] **Step 3.2.4: Commit**
  ```bash
  git add api/tropek/modules/asset_meta/service.py api/tests/asset_meta/test_service.py
  git commit -m "feat(asset-meta): add ingest service with decomposed helpers"
  ```

### Task 3.3: FastAPI router (POST only in this chunk)

- [ ] **Step 3.3.1: Read `api/tropek/modules/assets/router.py:1-60`** for the router style.

- [ ] **Step 3.3.2: Create `router.py`** with:
  ```
  router = APIRouter(prefix="/assets", tags=["asset-meta"])

  @router.post("/{asset_id}/meta/snapshots", status_code=201, response_model=MetaSnapshotCreated)
  async def create_snapshot(asset_id: uuid.UUID, payload: MetaSnapshotCreate, session: AsyncSession = Depends(get_session)):
      return await service.create_meta_snapshot(session, asset_id, payload)
  ```
  Keep this minimal — all logic lives in `service.py`.

- [ ] **Step 3.3.3: Register the router in `api/tropek/main.py`** alongside the existing `app.include_router(...)` calls (see line 60-67). Import: `from tropek.modules.asset_meta.router import router as asset_meta_router` and `app.include_router(asset_meta_router)`.

- [ ] **Step 3.3.4: Run the unit test suite to catch any import breakage.**
  Run: `./scripts/api-test.sh --tail 10`
  Expected: all existing tests still pass.

### Task 3.4: Integration tests for the ingest endpoint

- [ ] **Step 3.4.1: Read `api/tests/quality_gate/endpoints/test_smoke.py`** to see the FastAPI TestClient + DB fixture pattern used for endpoint integration tests.

- [ ] **Step 3.4.2: Write `api/tests/asset_meta/db/test_ingest_endpoint.py`** marked `@pytest.mark.integration`. Test cases (subset of §10.2 scoped to writes; read-path cases land in Chunk 4):
  1. `test_post_snapshot_values_only_returns_201_with_snapshot_id`.
  2. `test_post_snapshot_closed_only_returns_201`.
  3. `test_post_snapshot_empty_body_returns_400` — `values=[], closed=[]`.
  4. `test_post_snapshot_unknown_asset_returns_404`.
  5. `test_post_snapshot_invalid_source_returns_400` — `source="has space"`.
  6. `test_post_snapshot_naive_datetime_returns_400`.
  7. `test_post_snapshot_path_too_deep_returns_400` — 7-entry path.
  8. `test_post_snapshot_duplicate_path_in_values_returns_400`.
  9. `test_post_snapshot_persists_values_and_closures_to_db` — POST, then query the tables directly to confirm rows present.

- [ ] **Step 3.4.3: Run the integration tests.**
  Run: `./scripts/api-test.sh --tail 10 -m integration tests/asset_meta/db/test_ingest_endpoint.py -v`
  Expected: all 9 pass.

- [ ] **Step 3.4.4: Run lint + typecheck on everything touched.**
  Run: `uv run ruff check api/ && uv run --directory api mypy tropek/modules/asset_meta/`
  Expected: clean.

- [ ] **Step 3.4.5: Commit**
  ```bash
  git add api/tropek/modules/asset_meta/router.py api/tropek/main.py api/tests/asset_meta/db/test_ingest_endpoint.py
  git commit -m "feat(asset-meta): expose POST /assets/{id}/meta/snapshots endpoint"
  ```

### Chunk 3 review checkpoint

- [ ] POST ingest endpoint is live and all documented validation rules (§5.2) are enforced.
- [ ] Service layer helpers (`_validate_payload_has_content`, `_ensure_asset_exists`, `_write_snapshot_rows`) each have dedicated unit tests per §10.1 service-layer table.
- [ ] Integration tests at `api/tests/asset_meta/db/test_ingest_endpoint.py` pass.
- [ ] No read path yet (Chunk 4). `GET /meta/timeline` returns 404 or is simply not registered.

---

## Chunk 4 — Read + summary endpoints

**Why fourth:** derivation and ingest are in; now compose them into the read surface and re-export the OpenAPI schema.

**Files:**
- Modify: `api/tropek/modules/asset_meta/service.py` — add `get_timeline`, `get_timeline_summary`.
- Modify: `api/tropek/modules/asset_meta/router.py` — add GET endpoints.
- Create: `api/tests/asset_meta/db/test_read_endpoint.py` — integration tests for full timeline endpoint.
- Create: `api/tests/asset_meta/db/test_summary_endpoint.py` — integration tests for summary endpoint.
- Modify: `api/openapi.json` — regenerated.
- Modify: `ui/src/generated/api.ts` — regenerated.

### Task 4.1: Read service methods

- [ ] **Step 4.1.1: Read spec §6.3 (response body), §6.7 (summary endpoint), §8.3 (service code).**

- [ ] **Step 4.1.2: Extend `test_service.py` with failing tests** for:
  - `test_get_timeline_returns_empty_for_asset_with_no_snapshots` — fake repo returns `[]`, service returns `{groups: [], items: []}`.
  - `test_get_timeline_raises_not_found_for_missing_asset` — fake repo says asset doesn't exist.
  - `test_get_timeline_summary_returns_zero_for_empty_asset`.
  - `test_get_timeline_summary_raises_not_found_for_missing_asset`.

  Each fake repo implements both `asset_exists` and `load_snapshots_for_derivation`. Run — expect fails.

- [ ] **Step 4.1.3: Implement `get_timeline` and `get_timeline_summary`** per §8.3 (and §6.7 for summary). Both are thin orchestrators over `_ensure_asset_exists` + the pure derivation stack. The summary method calls `derive_raw_spans → resolve_multi_source_conflicts → clip_spans → count_distinct_leaf_paths` exactly as §6.7 prescribes — reuse the existing helpers, no new code path.

- [ ] **Step 4.1.4: Run service tests.** Run: `./scripts/api-test.sh --tail 10 tests/asset_meta/test_service.py -v`. Expected: pass.

### Task 4.2: Router GET endpoints

- [ ] **Step 4.2.1: Add GET endpoints to `router.py`:**
  - `GET /{asset_id}/meta/timeline?from=&to=` → `TimelineResponse`
  - `GET /{asset_id}/meta/timeline/summary?from=&to=` → `TimelineSummaryResponse`

  Both use `from` and `to` as `datetime` query params. Both validate `from < to` and return 400 otherwise — implement this in a tiny helper at the top of `router.py` (`_validate_window_params(from_, to) -> None` raising `DomainValidationError`). Both are thin wrappers: `await service.get_timeline(session, asset_id, window_from=from_, window_to=to)`. Use Python-reserved-word avoidance: the query param must be declared as `from_: datetime = Query(..., alias="from")`.

- [ ] **Step 4.2.2: Run `./scripts/api-test.sh --tail 10`** to catch any regressions or import errors.

### Task 4.3: Integration tests — full timeline (§10.2)

- [ ] **Step 4.3.1: Write `test_read_endpoint.py`** marked `@pytest.mark.integration`. Cases per §10.2:
  1. `test_round_trip_single_snapshot_shows_up_in_timeline` — POST values-only, GET, assert one item in response.
  2. `test_validation_errors_for_missing_from_or_to` — returns 400.
  3. `test_validation_error_when_from_equals_or_exceeds_to` — 400.
  4. `test_unknown_asset_returns_404`.
  5. `test_multi_source_spans_both_appear` — two different paths pushed by two sources; both appear in response (no conflict because paths differ).
  6. `test_cascading_closure_round_trip` — push `app + 2 plugins`, then `closed: [app]`, GET, assert all three items end at closure time with `meta-span-closed` class.
  7. `test_large_snapshot_roundtrips` — POST a payload with 500 values, assert 201, GET, assert 500 items.
  8. `test_window_clipping_left_and_open_right` — push a span starting 60 days ago with no close; GET with `from = now - 30d, to = now`; assert response has one item with `meta-span-clipped-left meta-span-open` in its `className`.
  9. `test_closed_only_snapshot_round_trip` — per §10.2 case 8; span ends at closure time, class contains `meta-span-closed`.

  Run — expect fail until implementation lands.

- [ ] **Step 4.3.2: Run** `./scripts/api-test.sh --tail 15 -m integration tests/asset_meta/db/test_read_endpoint.py -v`. Expected: all 9 pass.

### Task 4.4: Integration tests — summary + parity (§10.2 cases 9, 10)

- [ ] **Step 4.4.1: Write `test_summary_endpoint.py`** marked `@pytest.mark.integration`. Cases:
  1. `test_summary_returns_zero_for_empty_asset`.
  2. `test_summary_count_grows_with_distinct_paths` — push 3 distinct paths → `itemCount=3`; push a 4th → `itemCount=4`.
  3. `test_summary_404_for_unknown_asset`.
  4. `test_summary_and_timeline_count_parity` — for a fixture with 4 distinct paths in the window, assert `summary.itemCount == len({tuple(item.group JSON-decoded) for item in timeline.items})` (the collapsed strip and expanded timeline never disagree).
  5. `test_summary_validation_error_when_from_equals_or_exceeds_to`.

- [ ] **Step 4.4.2: Run** `./scripts/api-test.sh --tail 10 -m integration tests/asset_meta/db/test_summary_endpoint.py -v`. Expected: all 5 pass.

### Task 4.5a: Add `asset_id` to `AssetSnapshot` (prerequisite for UI)

The meta timeline endpoint is `GET /assets/{asset_id}/meta/timeline`, but the evaluation detail response only exposes `asset_snapshot.name` — no UUID. The UI needs the UUID to call the endpoint.

- [ ] **Step 4.5a.1: Add `asset_id` to the backend `AssetSnapshot` Pydantic schema.**
  File: `api/tropek/modules/quality_gate/schemas/evaluations.py:14`. Add `asset_id: UUID` as the first field. This is a response-only schema (`from_attributes=True`), so the field is populated from whatever dict is passed in.

- [ ] **Step 4.5a.2: Populate `asset_id` in the trigger service.**
  File: `api/tropek/modules/quality_gate/workflows/trigger/trigger_service.py:79-84`. The `asset_snapshot` dict already has `name`, `display_name`, `tags`, `variables`. Add `'asset_id': str(ctx.asset_id)` to the dict. Note: `ctx.asset_id` is already available at line 86 of the same function — it's passed as a sibling field today. Moving it inside the snapshot means the evaluation record carries the UUID alongside the snapshot, which is the right home.

- [ ] **Step 4.5a.3: Verify existing tests still pass** — the new field is additive.
  Run: `./scripts/api-test.sh --tail 5`
  Expected: pass (no existing test asserts the exact shape of `asset_snapshot`; adding a field is backward-compatible).

- [ ] **Step 4.5a.4: Commit**
  ```bash
  git add api/tropek/modules/quality_gate/schemas/evaluations.py api/tropek/modules/quality_gate/workflows/trigger/trigger_service.py
  git commit -m "feat(evaluations): expose asset_id in AssetSnapshot schema"
  ```

### Task 4.5: Regenerate OpenAPI schema + UI types

- [ ] **Step 4.5.1: Export the schema.**
  Run: `just export-schema`
  Expected: `api/openapi.json` updated; diff shows three new paths under `/assets/{asset_id}/meta/*` and four new schema components (`MetaSnapshotCreate`, `MetaSnapshotCreated`, `TimelineResponse`, `TimelineSummaryResponse`).

- [ ] **Step 4.5.2: Regenerate UI types.**
  Run: `just codegen`
  Expected: `ui/src/generated/api.ts` updated with matching types.

- [ ] **Step 4.5.3: Run the contract freshness check.**
  Run: `just check-schema-fresh`
  Expected: clean.

### Task 4.6: Full test sweep

- [ ] **Step 4.6.1: Full unit tests.**
  Run: `./scripts/api-test.sh --tail 5`
  Expected: all green.

- [ ] **Step 4.6.2: Full integration tests.**
  Run: `./scripts/api-test.sh --tail 10 -m integration -v`
  Expected: all green.

- [ ] **Step 4.6.3: Lint + typecheck.**
  Run: `uv run ruff check api/ && uv run --directory api mypy tropek/modules/asset_meta/`
  Expected: clean.

- [ ] **Step 4.6.4: Commit**
  ```bash
  git add api/tropek/modules/asset_meta/ api/tests/asset_meta/ api/openapi.json ui/src/generated/api.ts
  git commit -m "feat(asset-meta): add read and summary endpoints with integration tests"
  ```

### Chunk 4 review checkpoint

- [ ] `GET /assets/{id}/meta/timeline?from=&to=` returns §6.3 shape.
- [ ] `GET /assets/{id}/meta/timeline/summary?from=&to=` returns `{itemCount: N}`.
- [ ] All §10.2 integration cases (1–10) pass.
- [ ] `AssetSnapshot` schema now includes `asset_id` (Task 4.5a); populated by trigger service.
- [ ] `api/openapi.json` and `ui/src/generated/api.ts` regenerated; contract freshness check passes.
- [ ] §14 acceptance criteria 1–4 satisfied.

---

## Chunk 5 — UI feature scaffolding

**Why fifth:** read endpoint exists and codegen has run, so the UI can build against real types. This chunk stops at the feature module boundary — no components yet.

**Files:**
- Modify: `ui/package.json` — add `vis-timeline` dependency.
- Create: `ui/src/features/meta_timeline/domain.ts`
- Create: `ui/src/features/meta_timeline/mappers.ts`
- Create: `ui/src/features/meta_timeline/mappers.test.ts`
- Create: `ui/src/features/meta_timeline/api.ts`
- Create: `ui/src/features/meta_timeline/hooks.ts`
- Create: `ui/src/features/meta_timeline/ui-types.ts`
- Create: `ui/src/features/meta_timeline/index.ts`

### Task 5.1: Install vis-timeline

- [ ] **Step 5.1.1: Read spec §13.2.** Confirmed version pin: v8.x, exact minor 8.5.0 at spec time — use the latest 8.x available via pnpm.

- [ ] **Step 5.1.2: Add the dependency.**
  Run: `cd ui && pnpm add vis-timeline` (or use `--directory` equivalent; this command is genuinely one command so no script wrapper needed).
  Expected: `ui/package.json` lists `vis-timeline` under `dependencies`; `ui/pnpm-lock.yaml` updated.

- [ ] **Step 5.1.3: Confirm no type-package install is needed** (vis-timeline ships its own types per §13.2).

- [ ] **Step 5.1.4: Commit**
  ```bash
  git add ui/package.json ui/pnpm-lock.yaml
  git commit -m "chore(ui): add vis-timeline dependency"
  ```

### Task 5.2: Domain types + mapper (§9.1)

- [ ] **Step 5.2.1: Read spec §9.1** and `docs/superpowers/specs/2026-04-12-ui-layering-design.md` §5 (directory structure) and §6 (mapper placement).

- [ ] **Step 5.2.2: Create `domain.ts`** defining:
  - `MetaTimelineGroup` — `{id: string, content: string, nestedGroups?: string[], showNested?: boolean}` — almost identical to the DTO; the `id` is kept as the JSON-encoded group id string because vis-timeline needs it verbatim.
  - `MetaTimelineItem` — `{id: string, group: string, content: string, start: Date, end: Date, type: 'range', className: string, source: string}` — `start` and `end` are `Date` objects (converted from ISO strings in the mapper).
  - `MetaTimelineResponse` — `{groups: MetaTimelineGroup[], items: MetaTimelineItem[]}`.
  - `MetaTimelineSummary` — `{itemCount: number}`.

  Add a short header comment matching the style of `ui/src/features/evaluations/domain.ts:1-11`.

- [ ] **Step 5.2.3: Write `mappers.test.ts`** with failing unit tests for:
  - `dtoToMetaTimelineResponse` — input with 2 groups (one with `nestedGroups`, one without) and 3 items; assert items' `start` and `end` are real `Date` instances; assert groups pass through unchanged.
  - Empty input → empty arrays.
  - `dtoToMetaTimelineSummary` — input `{item_count: 7}` → `{itemCount: 7}` (snake_case → camelCase rename).

  Run: `./scripts/ui-test.sh --tail 10 src/features/meta_timeline/mappers.test.ts` — expect fail.

- [ ] **Step 5.2.4: Create `mappers.ts`** with sync functions `dtoToMetaTimelineResponse` and `dtoToMetaTimelineSummary`. No `await`, no `fetch`. Import DTO types from `@/generated/api`.

- [ ] **Step 5.2.5: Run the test** — expect pass.

- [ ] **Step 5.2.6: Commit**
  ```bash
  git add ui/src/features/meta_timeline/domain.ts ui/src/features/meta_timeline/mappers.ts ui/src/features/meta_timeline/mappers.test.ts
  git commit -m "feat(ui/meta-timeline): add domain types and DTO mappers"
  ```

### Task 5.2a: Flow `assetId` through the evaluations mapper

Task 4.5a added `asset_id` to the backend `AssetSnapshot` schema and regenerated the DTO types. Now the UI evaluation mapper and domain type need to pick it up so `MetaTimelineSection` can read `ev.assetSnapshot.assetId`.

- [ ] **Step 5.2a.1: Add `assetId: string` to `AssetSnapshot`** in `ui/src/features/evaluations/domain.ts:21`.

- [ ] **Step 5.2a.2: Map the new field in `dtoToAssetSnapshot`** in `ui/src/features/evaluations/mappers.ts:79`. Add: `assetId: dto.asset_id`.

- [ ] **Step 5.2a.3: Update the exhaustiveness check** in `mappers.ts:265-278`. Add `'asset_id'` to the `MappedAssetSnapshotKeys` union.

- [ ] **Step 5.2a.4: Update the mapper test** in `ui/src/features/evaluations/mappers.test.ts` — add `asset_id` to the DTO fixture input and assert `assetId` appears on the domain output.

- [ ] **Step 5.2a.5: Run mapper tests.**
  Run: `./scripts/ui-test.sh --tail 10 src/features/evaluations/mappers.test.ts`
  Expected: pass.

- [ ] **Step 5.2a.6: Run typecheck** to confirm no type errors from the new field.
  Run: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json`
  Expected: clean.

- [ ] **Step 5.2a.7: Commit**
  ```bash
  git add ui/src/features/evaluations/domain.ts ui/src/features/evaluations/mappers.ts ui/src/features/evaluations/mappers.test.ts
  git commit -m "feat(ui/evaluations): flow assetId through AssetSnapshot domain type"
  ```

### Task 5.3: api.ts + hooks.ts + index.ts + ui-types.ts

- [ ] **Step 5.3.1: Read `ui/src/features/evaluations/api.ts` and `hooks.ts`** for the mapper-inside-fetch and React Query wrapper conventions.

- [ ] **Step 5.3.2: Create `api.ts`** exposing two fetch functions:
  - `fetchMetaTimeline(assetId: string, from: Date, to: Date): Promise<MetaTimelineResponse>` — fetches `/assets/{id}/meta/timeline?from=&to=`, runs `dtoToMetaTimelineResponse` on the result before returning.
  - `fetchMetaTimelineSummary(assetId: string, from: Date, to: Date): Promise<MetaTimelineSummary>` — same pattern for the summary endpoint.

  Dates are converted to ISO strings (`.toISOString()`) in query params.

- [ ] **Step 5.3.3: Create `hooks.ts`** with:
  - `useMetaTimeline(assetId, from, to, options?: {enabled?: boolean})` — `useQuery` wrapper; query key `['meta-timeline', assetId, from.toISOString(), to.toISOString()]`.
  - `useMetaTimelineSummary(assetId, from, to)` — always enabled; query key `['meta-timeline-summary', ...]`.

  These hooks MUST NOT import from `@/generated/api` (hard rule from the layering spec).

- [ ] **Step 5.3.4: Create `ui-types.ts`** with types used only by components (component prop shapes). At this chunk's scope, define:
  - `MetaTimelineSectionProps` — `{assetId: string, focusEval: {id: string, periodEnd: Date}}`.
  - `CollapsedStripProps` — `{itemCount: number, expanded: boolean, onToggle: () => void}`.

  These are placeholder exports — Chunk 7 consumes them.

- [ ] **Step 5.3.5: Create `index.ts`** re-exporting domain types (from `./domain`) and hooks (from `./hooks`) only. No mapper re-exports, no DTO re-exports. This barrel is the public surface.

- [ ] **Step 5.3.6: Run typecheck + lint.**
  Run: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json` and `./scripts/ui-lint.sh --tail 10 src/features/meta_timeline/`
  Expected: clean. Resolve any `no-restricted-imports` violations by keeping DTO imports inside `api.ts` and `mappers.ts` only.

- [ ] **Step 5.3.7: Commit**
  ```bash
  git add ui/src/features/meta_timeline/
  git commit -m "feat(ui/meta-timeline): add api, hooks, index barrel, and ui-types"
  ```

### Chunk 5 review checkpoint

- [ ] `features/meta_timeline/` follows the exact layering structure from §9.1.
- [ ] No component imports from `@/generated/api`; only `api.ts` and `mappers.ts` do.
- [ ] `mappers.test.ts` passes.
- [ ] Typecheck and lint clean.
- [ ] No components yet — `components/` directory does not exist at this chunk boundary (Chunk 6 creates it).

---

## Chunk 6 — MetaTimeline React wrapper

**Why sixth:** imperative vis-timeline wiring has the highest risk of getting tangled with React's reconciliation; isolate it before wrapping it in a section.

**Files:**
- Create: `ui/src/features/meta_timeline/components/MetaTimeline.tsx` — the create-once React wrapper from §9.3.
- Create: `ui/src/features/meta_timeline/components/renderSpanTooltip.tsx` — per §9.5.
- Create: `ui/src/features/meta_timeline/components/meta-timeline.css` — per §9.4.
- Create: `ui/src/features/meta_timeline/components/MetaTimeline.test.tsx` — scope-limited tests per §10.3 case 3.
- Create: `ui/src/features/meta_timeline/components/renderSpanTooltip.test.tsx` — per §10.3 case 4.

### Task 6.1: Tooltip renderer (§9.5)

- [ ] **Step 6.1.1: Read spec §9.5.**

- [ ] **Step 6.1.2: Write `renderSpanTooltip.test.tsx`** with failing tests:
  - Tooltip for a `meta-span` (in-window, value-change): `From:` and `To:` lines without annotations.
  - Tooltip for `meta-span meta-span-clipped-left`: `From:` line has `(started before window)` suffix.
  - Tooltip for `meta-span meta-span-open`: `To:` line has `(still open)` suffix.
  - Tooltip for `meta-span meta-span-clipped-right`: `To:` line has `(continues after window)`.
  - Tooltip for `meta-span meta-span-closed`: `To:` line has `(explicit closure)`.
  - HTML escaping — value `<script>` appears as `&lt;script&gt;`.
  - Group label decoding — group id `'["app-A","plugin-alpha"]'` renders as `"app-A > plugin-alpha"` in the header.

- [ ] **Step 6.1.3: Implement `renderSpanTooltip.tsx`** per §9.5 including helpers `decodeGroupLabel`, `escapeHtml`, `parseIsoDate`. Use `date-fns` (already in dependencies). Run tests — expect pass.

- [ ] **Step 6.1.4: Commit**
  ```bash
  git add ui/src/features/meta_timeline/components/renderSpanTooltip.tsx ui/src/features/meta_timeline/components/renderSpanTooltip.test.tsx
  git commit -m "feat(ui/meta-timeline): add rich span tooltip renderer"
  ```

### Task 6.2: Base CSS (§9.4)

- [ ] **Step 6.2.1: Create `meta-timeline.css`** with the CSS from §9.4 verbatim. The file references CSS variables (`--color-meta-span-bg`, `--color-focus-eval-marker`, etc.) that Chunk 8 defines. Referencing an undefined variable gives a safe fallback to `inherit`; visual rendering is wrong until Chunk 8 lands, which is expected.

- [ ] **Step 6.2.2: Commit**
  ```bash
  git add ui/src/features/meta_timeline/components/meta-timeline.css
  git commit -m "feat(ui/meta-timeline): add span and marker CSS vocabulary"
  ```

### Task 6.3: MetaTimeline React wrapper (§9.3)

- [ ] **Step 6.3.1: Read spec §9.3** and `ui/src/features/evaluations/components/EvaluationHeatmap.tsx` (for an example of a component that mutates DOM imperatively, if present — otherwise just the vis-timeline docs at https://visjs.github.io/vis-timeline/docs/timeline/).

- [ ] **Step 6.3.2: Write `MetaTimeline.test.tsx`** with failing tests — scope-limited per §10.3 case 3 because happy-dom does not render vis-timeline faithfully:
  - Mount the component with a small groups/items fixture; assert the `<div>` with class `meta-timeline-container` is in the DOM.
  - Re-render with different `items`; assert no thrown errors (the create-once effect did not re-run; the data-update effect ran).
  - Unmount; assert no thrown errors (destroy cleanup ran).
  - Do NOT assert pixel-level rendering. Add an explicit comment citing §10.3 case 3 explaining why.

  Stub the `vis-timeline` module at the top of the test file using `vi.mock('vis-timeline/esnext', () => ({...}))` with a minimal `Timeline` class that records constructor calls + tracks `destroy`/`setCustomTime` invocations, and a `DataSet` class that records `clear` / `add`. Assert on these records instead of real DOM.

  Run — expect fails.

- [ ] **Step 6.3.3: Implement `MetaTimeline.tsx`** per §9.3 verbatim. Import `'vis-timeline/styles/vis-timeline-graph2d.min.css'` once at the top of the file (per §13.2) and `./meta-timeline.css` for our overrides. The three useEffects are: create-once (`[]` deps), data-update (`[groups, items]`), focus-time-update (`[focusTime]`).

- [ ] **Step 6.3.4: Run tests.**
  Run: `./scripts/ui-test.sh --tail 10 src/features/meta_timeline/components/MetaTimeline.test.tsx`
  Expected: pass.

- [ ] **Step 6.3.5: Follow the happy-dom React Query cleanup protocol** from CLAUDE.md if the test ends up using a `QueryClient` — use `beforeEach`/`afterEach` with `cancelQueries` + `clear` + `cleanup`.

- [ ] **Step 6.3.6: Run typecheck + lint.**
  Run: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json && ./scripts/ui-lint.sh --tail 10 src/features/meta_timeline/`
  Expected: clean.

- [ ] **Step 6.3.7: Commit**
  ```bash
  git add ui/src/features/meta_timeline/components/MetaTimeline.tsx ui/src/features/meta_timeline/components/MetaTimeline.test.tsx
  git commit -m "feat(ui/meta-timeline): add create-once vis-timeline React wrapper"
  ```

### Chunk 6 review checkpoint

- [ ] `MetaTimeline.tsx` follows the create-once pattern from §9.3 (single `useEffect` with `[]` deps for construction; separate effects for data and focus updates).
- [ ] Destroy cleanup runs on unmount.
- [ ] `renderSpanTooltip.test.tsx` covers every class combination.
- [ ] No pixel-level assertions on vis-timeline internals.
- [ ] Tests green, typecheck clean, lint clean.

---

## Chunk 7 — CollapsedStrip + MetaTimelineSection + EvaluationDetail integration

**Why seventh:** the wrapper exists; now build the container it lives in and wire it into the page.

**Files:**
- Create: `ui/src/features/meta_timeline/components/CollapsedStrip.tsx`
- Create: `ui/src/features/meta_timeline/components/CollapsedStrip.test.tsx`
- Create: `ui/src/features/meta_timeline/components/MetaTimelineSection.tsx`
- Create: `ui/src/features/meta_timeline/components/MetaTimelineSection.test.tsx`
- Modify: `ui/src/features/meta_timeline/index.ts` — add `MetaTimelineSection` to the barrel re-exports (component exports are allowed from the barrel; DTOs/mappers are not).
- Modify: `ui/src/pages/EvaluationDetailPage.tsx` — insert the section between heatmap block and first table.

### Task 7.1: CollapsedStrip component (§9.2)

- [ ] **Step 7.1.1: Write `CollapsedStrip.test.tsx`** with failing tests per §10.3 case 2:
  - `itemCount=0` renders "no items tracked".
  - `itemCount=1` renders "1 item tracked" (singular).
  - `itemCount=5` renders "5 items tracked".
  - `aria-expanded` attribute reflects the `expanded` prop.
  - Click on strip fires `onToggle`.
  - Investigation hint ("click to investigate…") visible when `expanded=false`, hidden when `expanded=true`.

- [ ] **Step 7.1.2: Implement `CollapsedStrip.tsx`** per §9.2. Use the chevron from `lucide-react` (`ChevronRight` / `ChevronDown`). Inline `fontFamily` per CLAUDE.md UI rule about sans-serif for chrome.

- [ ] **Step 7.1.3: Run tests — expect pass.**
  Run: `./scripts/ui-test.sh --tail 10 src/features/meta_timeline/components/CollapsedStrip.test.tsx`

- [ ] **Step 7.1.4: Commit**
  ```bash
  git add ui/src/features/meta_timeline/components/CollapsedStrip.tsx ui/src/features/meta_timeline/components/CollapsedStrip.test.tsx
  git commit -m "feat(ui/meta-timeline): add CollapsedStrip with pluralization tests"
  ```

### Task 7.2: MetaTimelineSection container (§9.2, §10.3 case 1)

- [ ] **Step 7.2.1: Write `MetaTimelineSection.test.tsx`** with failing tests per §10.3 case 1:
  - Default collapsed: timeline container not in DOM; only CollapsedStrip visible; empty summary query state → strip shows "no items tracked".
  - Summary query runs on mount; when the mock returns `{itemCount: 3}` the strip shows "3 items tracked".
  - Click strip → full-data query fires (mock verifies call happened); timeline container appears.
  - Click strip again → collapses back; timeline container removed from DOM.
  - Mock response with `items: []` when expanded → empty-state copy visible.
  - Mock network error when expanded → error-state copy visible.
  - Height when collapsed is ≤ 40px — use `getBoundingClientRect` on the rendered node (§10.3 case 1 last bullet).

  Use MSW or a manual `fetch` mock — check what pattern other tests use (e.g. `EvaluationIndicatorSection.test.tsx`) and mirror it. Wrap the component in `QueryClientProvider` with the fresh-client pattern from CLAUDE.md.

- [ ] **Step 7.2.2: Implement `MetaTimelineSection.tsx`** per §9.2:
  - `useState(false)` for `isExpanded`.
  - `useMemo` for `from = subDays(focusEval.periodEnd, 30)` and `to = addDays(focusEval.periodEnd, 7)`.
  - Unconditional `useMetaTimelineSummary(assetId, from, to)`.
  - Gated `useMetaTimeline(assetId, from, to, {enabled: isExpanded})`.
  - Renders `CollapsedStrip` then, when expanded, either `<LoadingIndicator/>`, `<ErrorState/>`, `<EmptyState/>`, or `<MetaTimeline .../>`.
  - Empty-state copy: "No meta data recorded for this asset yet." (per §6.5 — the "See docs" link is optional; pick what matches other empty states in the UI).

  Reuse existing loading/error/empty primitives if they already exist in the UI; otherwise inline the markup (this is not where to invent a new design system).

- [ ] **Step 7.2.3: Run tests — expect pass.**
  Run: `./scripts/ui-test.sh --tail 10 src/features/meta_timeline/components/MetaTimelineSection.test.tsx`

- [ ] **Step 7.2.4: Commit**
  ```bash
  git add ui/src/features/meta_timeline/components/MetaTimelineSection.tsx ui/src/features/meta_timeline/components/MetaTimelineSection.test.tsx ui/src/features/meta_timeline/index.ts
  git commit -m "feat(ui/meta-timeline): add MetaTimelineSection with collapsed default"
  ```

### Task 7.3: Wire into the evaluation detail page (§9.6)

- [ ] **Step 7.3.1: Locate the insertion point.** Per §9.6: "between the heatmap and the first table in the eval detail view." Read `ui/src/pages/EvaluationDetailPage.tsx` and `ui/src/features/evaluations/components/EvaluationIndicatorSection.tsx` to find:
  - Where the heatmap / summary block renders (in the current layout, the top header + `EvaluationHeatmap` usage).
  - Where the first table renders (`SLIBreakdownTable` via `EvaluationIndicatorSection`, which is the block immediately before `MetricTrendBlock` and after `EvaluationNotesSection`).

  The `MetaTimelineSection` goes between these two. If the existing layout renders `EvaluationNotesSection` between the heatmap and the first table, the section still goes between the heatmap and `EvaluationIndicatorSection` — confirm during implementation, and if unclear, flag in PR review which of the two placements matches the spec diagram at §9.6 lines 1850–1862.

- [ ] **Step 7.3.2: Import and render** `<MetaTimelineSection assetId={ev.assetSnapshot.assetId} focusEval={{id: ev.id, periodEnd: new Date(ev.period.to)}} />` at the chosen point. The `assetId` field was added to `AssetSnapshot` in Task 5.2a and is available on the evaluation domain type.

- [ ] **Step 7.3.3: Update `EvaluationDetailPage.test.tsx` or equivalent** — add a test that confirms the section renders. If the page test uses MSW, add mock handlers for `/meta/timeline/summary` returning `{item_count: 0}` so the test doesn't explode on a missing endpoint.

- [ ] **Step 7.3.4: Start the dev server and manually verify the layout.** (Per CLAUDE.md UI rule: "start the dev server and use the feature in a browser before reporting the task as complete".)
  Run: `cd ui && pnpm exec vite --host` (in a separate terminal, or background with `run_in_background=true`)
  Navigate to an evaluation detail page. Confirm the collapsed strip appears between the heatmap and the first table. Click it to expand (expect the timeline to be unstyled until Chunk 8 lands). Click to collapse. No console errors. Stop the dev server.

- [ ] **Step 7.3.5: Run the full UI test suite.**
  Run: `./scripts/ui-test.sh --tail 10`
  Expected: all pass.

- [ ] **Step 7.3.6: Run lint + typecheck.**
  Run: `./scripts/ui-lint.sh --tail 10 && cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json`
  Expected: clean.

- [ ] **Step 7.3.7: Commit**
  ```bash
  git add ui/src/pages/EvaluationDetailPage.tsx ui/src/pages/EvaluationDetailPage.test.tsx
  git commit -m "feat(ui/evaluations): mount MetaTimelineSection between heatmap and first table"
  ```

### Chunk 7 review checkpoint

- [ ] Strip is default-collapsed on mount, shows "N items tracked".
- [ ] Click expands in place; full timeline query fires only on first expand (verified via network tab or mock assertion).
- [ ] `isExpanded=false` → timeline container not in DOM.
- [ ] Empty response → empty state copy.
- [ ] Section renders between the heatmap and the first table.
- [ ] All UI tests pass; lint + typecheck clean.
- [ ] Manual visual check confirmed layout is correct (structure, not colour — colour lands in Chunk 8).

---

## Chunk 8 — CSS theme variables

**Why eighth:** structure and behaviour are done; colour is a small, isolated polish pass.

**Files:**
- Modify: `ui/src/index.css` — add CSS variables for meta-span and focus-eval marker to the `dark`, `current`, and `light` theme blocks.

### Task 8.1: Theme tokens — cycling span palette + marker

- [ ] **Step 8.1.1: Read `ui/src/index.css` theme blocks.** The file uses `[data-theme="dark"]`, `[data-theme="current"]`, `[data-theme="light"]` blocks. Locate each one.

- [ ] **Step 8.1.2: Define the cycling span palette.** Instead of a single `--color-meta-span-bg`, define a rotating palette of 6–8 distinguishable span colours so consecutive different values pop visually. Each theme block gets:
  - `--color-meta-span-0` through `--color-meta-span-7` — 8 distinct background colours for span bars.
  - `--color-meta-span-border` — shared border colour (one per theme).
  - `--color-meta-span-fg` — text colour inside spans (one per theme, high-contrast against all palette entries).
  - `--color-focus-eval-marker` — marker line + tag background.
  - `--color-focus-eval-marker-fg` — marker tag text.

  Suggested palette strategy (adjust in PR review):
  - `dark`: muted jewel tones against slate backgrounds. Draw from Radix scales (jade, cyan, amber, plum, orange, sky, grass, tomato) at low-alpha or the `9`/`10` steps.
  - `current`: Dynatrace-aligned muted tones, similar hue spread.
  - `light`: saturated pastels, readable on white.

  Critical constraint per CLAUDE.md colour conventions: span palette MUST NOT overlap with the status palette (`--status-pass/warning/fail`) — those are reserved for evaluation outcomes only.
  Marker colour MUST NOT overlap with the span palette — it must read as "viewport metadata", not "another span".

- [ ] **Step 8.1.3: Create `ui/src/features/meta_timeline/components/spanColor.ts`** — a small pure function `getSpanColorIndex(value: string): number` that hashes the span's `content` (value string) to an index `0..N-1` into the palette. A simple string hash (djb2 or similar) modulo palette size is sufficient. Same value = same colour everywhere on the timeline.

  The MetaTimeline wrapper (or the mapper) uses this to append a data attribute or CSS variable (`style={{ '--span-color': 'var(--color-meta-span-${index})' }}`) to each item. Implementation options:
  - **Option A (recommended):** The mapper in `mappers.ts` computes the index at mapping time and injects it into `className` (e.g. `meta-span meta-span-color-3`). Then CSS rules `.meta-span-color-0 { background: var(--color-meta-span-0); }` through `.meta-span-color-7` handle theming.
  - **Option B:** vis-timeline's `template` callback applies the style inline per item.

  Pick Option A — it's pure CSS, no runtime style injection, and theme-switch works automatically.

- [ ] **Step 8.1.4: Update the server-side `compute_span_classes`** to NOT emit the colour class — colour is a UI concern based on value, not a server concern. The colour index is computed client-side by the mapper, not by the server.

  Wait — this means the UI mapper needs to append the colour class to each item's `className`. Update `dtoToMetaTimelineResponse` in `mappers.ts` to call `getSpanColorIndex(item.content)` and append `meta-span-color-${index}` to each item's `className` during mapping.

- [ ] **Step 8.1.5: Write `spanColor.test.ts`** with tests:
  - Same value always returns the same index.
  - Different values return at least 2 distinct indices (not all collide).
  - Return value is in range `[0, PALETTE_SIZE)`.

- [ ] **Step 8.1.6: Add the 8 `.meta-span-color-N` CSS rules** to `meta-timeline.css`:
  ```css
  .vis-item.meta-span-color-0 { background-color: var(--color-meta-span-0); }
  .vis-item.meta-span-color-1 { background-color: var(--color-meta-span-1); }
  /* ... through 7 */
  ```

- [ ] **Step 8.1.7: Start the dev server and cycle themes.** Confirm:
  - Spans with different values have visually distinct colours.
  - Spans with the same value have the same colour.
  - Marker is clearly distinguishable from all span colours.
  - No flicker on theme switch.

- [ ] **Step 8.1.8: Run all UI tests to confirm nothing regressed.**
  Run: `./scripts/ui-test.sh --tail 5`
  Expected: all pass.

- [ ] **Step 8.1.9: Commit**
  ```bash
  git add ui/src/index.css ui/src/features/meta_timeline/components/spanColor.ts ui/src/features/meta_timeline/components/spanColor.test.ts ui/src/features/meta_timeline/components/meta-timeline.css ui/src/features/meta_timeline/mappers.ts
  git commit -m "feat(ui/meta-timeline): add value-hashed cycling span colours across themes"
  ```

### Chunk 8 review checkpoint

- [ ] All three themes define `--color-meta-span-0` through `--color-meta-span-7` plus `--color-meta-span-border`, `--color-meta-span-fg`, and `--color-focus-eval-marker*` tokens.
- [ ] Same value = same colour; consecutive different values = visually distinct colours.
- [ ] Span palette does not clash with status palette; marker does not clash with span palette.
- [ ] Theme switch does not remount the timeline (verified manually).
- [ ] `spanColor.test.ts` passes.

---

## Chunk 9 — Manual verification

**Why last:** everything is in place; now confirm the full spec checklist.

**No code changes.** This is a PR review gate.

### Task 9.1: §10.4 manual checklist

Run through the full §10.4 checklist from the spec, testing each bullet in a live browser against real data. Push a few hand-crafted snapshots via `curl` against a running stack to get realistic data.

- [ ] The Gantt renders inside the eval detail page.
- [ ] The focus-eval marker is positioned exactly at the eval's `period_end`.
- [ ] The marker cannot be dragged.
- [ ] Hovering a span shows the rich tooltip with key, value, from, to, duration, source.
- [ ] Clicking a parent group chevron expands / collapses children.
- [ ] Spans that started before the window show a dashed left edge.
- [ ] Open-ended spans (no closure) show a faded right edge.
- [ ] Closed spans show a solid right cap.
- [ ] The section collapses and re-expands cleanly without console errors.
- [ ] Theme switch (dark ↔ current) re-styles spans and marker without re-mount glitches.

### Task 9.2: §14 acceptance criteria

Walk through each of the 12 numbered acceptance criteria in §14 and tick them off. Any criterion not met goes back to the relevant chunk's task list.

- [ ] 1. New tables exist and are reachable via the repositories layer.
- [ ] 2. `POST /assets/{id}/meta/snapshots` accepts the documented contract, validates all §5.2 rules, and inserts rows transactionally.
- [ ] 3. `GET /assets/{id}/meta/timeline?from=&to=` returns vis-timeline-shaped JSON per §6.3.
- [ ] 4. `GET /assets/{id}/meta/timeline/summary?from=&to=` returns `{itemCount: N}` per §6.7.
- [ ] 5. Unit tests for derivation, conflict, clipping, tree-building, and item-emitter functions cover all cases in the §10.1 per-function table and pass.
- [ ] 6. Integration tests in §10.2 pass against real TimescaleDB.
- [ ] 7. UI shows `MetaTimelineSection` as a single-row collapsed strip between the heatmap and the first table in the eval detail page.
- [ ] 8. Collapsed strip shows `Asset meta · N items tracked · click to investigate…` where N comes from the summary endpoint.
- [ ] 9. Clicking the strip expands it in place; full timeline query is fetched only on first expansion and cached thereafter.
- [ ] 10. The focus-eval marker is pinned, non-draggable, labelled.
- [ ] 11. Nested groups expand/collapse on chevron click; parent's own bar always visible.
- [ ] 11. Theme switch works without re-mount artifacts. (Spec has two #11s — list both.)
- [ ] 12. `docs/meta-gantt/asset_version_gantt_spec.docx` is left in place untouched. Confirm via `git status` that this file has not changed. **Do not edit it.**

### Task 9.3: Final confirmation

- [ ] **Step 9.3.1: Full test sweep.**
  Run: `./scripts/api-test.sh --tail 5 && ./scripts/api-test.sh --tail 5 -m integration -v && ./scripts/ui-test.sh --tail 5`
  (These are three separate commands — run them sequentially; do NOT chain with `&&` in one Bash call per CLAUDE.md shell discipline.)
  Expected: all pass.

- [ ] **Step 9.3.2: Lint + typecheck sweep.**
  Run: `uv run ruff check api/ && uv run --directory api mypy tropek/modules/asset_meta/` then separately `./scripts/ui-lint.sh --tail 5` and `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json`.
  Expected: clean.

- [ ] **Step 9.3.3: Contract freshness.**
  Run: `just check-schema-fresh`
  Expected: clean.

---

## Resolved questions

These were open during initial planning; all are now resolved.

1. **Test directory convention.** Spec §10.1 says tests live at `api/tests/engine/asset_meta/`. The existing codebase pattern is `api/tests/<module>/` (e.g. `api/tests/quality_gate/evaluation_engine/`). This plan uses `api/tests/asset_meta/timeline/` to match the existing convention.

2. **`EvaluationDetail` domain type and the asset id.** The `MetaTimelineSection` needs an `assetId` (UUID) to call `GET /assets/{id}/meta/timeline`. Currently `AssetSnapshot` (both the backend Pydantic schema at `api/tropek/modules/quality_gate/schemas/evaluations.py:14` and the UI domain type at `ui/src/features/evaluations/domain.ts:21`) only carries `name` / `display_name` / `tags` — no UUID. **Resolution:** add `asset_id: UUID` to the backend `AssetSnapshot` schema, populate it in the trigger service (which already has `ctx.asset_id` at `trigger_service.py:86`), then flow it through the evaluation mapper into the UI domain type. Chunk 4 handles the backend + codegen; Chunk 5 handles the UI mapper update. See **Task 4.5a** for the exact steps.

3. **Placement relative to `EvaluationNotesSection`.** **Resolved:** the meta timeline strip goes directly before `EvaluationIndicatorSection` (which contains `SLIBreakdownTable`). Notes stay where they are — above the strip. Notes describe _what happened_; the timeline shows _when/what changed on the asset_. As meta timeline matures, users will rely less on notes for marking asset changes.

4. **Span colours — value-hashed cycling.** The spec describes a single `--color-meta-span-bg` token. **Resolved:** instead of one flat colour, implement value-hashed cycling colours. A small JS helper hashes the span's `content` (value string) to an index into a rotating palette (6–8 colours). Same value = same colour everywhere on the timeline, so consecutive different versions pop visually. The palette uses CSS variables (`--color-meta-span-0` through `--color-meta-span-N`) defined per theme in `index.css`. Phase 2 can refine to strict zebra alternation. See updated **Task 6.2** and **Chunk 8** for details.

5. **`vis-timeline` typing.** vis-timeline's TypeScript declarations may not include our extra `source` field on item objects. The fix is a one-line type cast at the call site — vis-timeline passes through all fields at runtime regardless of its type declarations. Compile-time nuisance, not a runtime bug.

---

## Checklist mapping (spec §7 → plan tasks)

Every function from §7 is covered. Traceability:

| §7 function | Implemented in | Unit-tested in |
|---|---|---|
| `derive_raw_spans` | Task 2.2.12 | Task 2.2.11 |
| `apply_snapshot` | Task 2.2.8 | Task 2.2.7 |
| `apply_value` | Task 2.2.4 | Task 2.2.3 |
| `close_cascade` | Task 2.2.6 | Task 2.2.5 |
| `is_prefix` | Task 2.2.2 | Task 2.2.1 |
| `finalize_open_spans` | Task 2.2.10 | Task 2.2.9 |
| `resolve_multi_source_conflicts` | Task 2.3.10 | Task 2.3.9 |
| `group_spans_by_path` | Task 2.3.2 | Task 2.3.1 |
| `compute_latest_observation_per_source` | Task 2.3.4 | Task 2.3.3 |
| `pick_winning_source` | Task 2.3.6 | Task 2.3.5 |
| `log_source_conflict` | Task 2.3.8 | Task 2.3.7 |
| `clip_spans` | Task 2.4.6 | Task 2.4.5 |
| `clip_one_span` | Task 2.4.4 | Task 2.4.3 |
| `compute_span_classes` | Task 2.4.2 | Task 2.4.1 |
| `build_groups_wire` | Task 2.5.14 | Task 2.5.13 |
| `collect_distinct_paths` | Task 2.5.4 | Task 2.5.3 |
| `expand_with_synthetic_ancestors` | Task 2.5.6 | Task 2.5.5 |
| `compute_children_map` | Task 2.5.8 | Task 2.5.7 |
| `sort_groups_deterministically` | Task 2.5.10 | Task 2.5.9 |
| `build_group_entry` | Task 2.5.12 | Task 2.5.11 |
| `encode_path_as_group_id` | Task 2.5.2 | Task 2.5.1 |
| `build_items_wire` | Task 2.6.4 | Task 2.6.3 |
| `item_from_span` | Task 2.6.2 | Task 2.6.1 |
| `build_timeline_response` | Task 2.8.2 | Task 2.8.1 |
| `count_distinct_leaf_paths` (§6.7) | Task 2.7.2 | Task 2.7.1 |
| `_validate_payload_has_content` (§8.3) | Task 3.2.2 | Task 3.2.1 |
| `_ensure_asset_exists` (§8.3) | Task 3.2.2 | Task 3.2.1 |
| `_write_snapshot_rows` (§8.3) | Task 3.2.2 | Task 3.2.1 |

## Checklist mapping (spec §10.1 scenarios → plan tasks)

All 19 end-to-end scenarios are covered in Task 2.8.1 (`test_orchestrator.py`), with some additionally covered by Task 2.2.11 (`test_derive_raw_spans`). Scenario 15 is a Pydantic-layer concern covered by Task 3.1.2 (`test_schemas.py`).
