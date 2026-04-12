# UI Layering Architecture — DTO / Domain / Mapper

**Date:** 2026-04-12
**Status:** Design approved — awaiting discovery phase before implementation planning
**Supersedes:** Parts of `2026-04-12-contract-testing-design.md` Phase 1 — specifically the "incremental migration" scoping that left most UI feature types hand-written.

---

## 1. Problem statement

The current TROPEK UI has no architectural boundary between the API transport layer and the visualization layer. Components import feature-local `types.ts` files that are hand-written guesses at backend shapes. These hand-written types drift silently from the real Pydantic schemas, and the drift is only caught when a user clicks the affected page in production.

Phase 1 of the contract testing rollout generated TypeScript types from the live OpenAPI schema and migrated one feature (`assets`) to alias the generated types directly. That migration surfaced real drift — a Pydantic `dict[str, Any]` that should have been `dict[str, str]`, and six test fixtures missing required fields — which validated the approach. But the same migration also revealed that **aliasing generated types into feature code is not enough**. It fixes the naming gap but doesn't give the UI any place to:

- Use UI vocabulary that diverges from backend vocabulary (e.g. `Evaluation` vs `EvaluationRun`, `Outcome` vs `result`).
- Compute derived fields once at the fetch boundary instead of re-parsing strings in every component render.
- Explicitly declare which backend fields the UI intentionally ignores.
- Insulate components from backend field renames.
- Make UI-only shapes (heatmap state, tree expansion, chart config) visibly different from wire shapes.

The incremental approach originally scoped for Phase 1 — "migrate more features alongside normal feature work" — was a cop-out. It defers the hardest and most valuable work indefinitely and leaves the system in a half-migrated state where some features leak DTOs into components and others don't. This spec replaces that approach with a proper layered architecture applied uniformly across the UI.

---

## 2. Background — what exists now

### 2.1 Current feature layout

Every feature directory under `ui/src/features/<x>/` contains some subset of:

- `types.ts` — hand-written TypeScript interfaces
- `api.ts` — fetch functions returning the hand-written types
- `hooks.ts` — React Query wrappers around the fetch functions
- `components/*.tsx` — React components that import from `types.ts`
- `index.ts` — barrel re-export

The features currently in the tree:

- `assets` (partially migrated — aliased to generated DTOs in Phase 1)
- `datasources`
- `evaluations` — the largest and most complex domain
- `slo-groups`
- `slos`
- `slis`
- `registry` — 3-mode UI with the most derived/UI-only state
- `navigator` — heatmap and tree display

Plus `ui/src/lib/types.ts` which holds cross-feature types (mix of API and UI-only).

### 2.2 What Phase 1 completed

Phase 1 established the OpenAPI export → TypeScript codegen pipeline:

- `scripts/export-schema.py` writes `api/openapi.json` from the FastAPI app object
- `just export-schema` + `just codegen` regenerate `ui/src/generated/api.ts`
- `just check-schema-fresh` fails if the committed schema or types drift from the live app
- `.github/workflows/contract-freshness.yml` runs that check in CI
- `ui/src/features/assets/types.ts` is aliased to generated DTOs as a proof of concept

Phase 1's tooling foundation is correct and stays. What needs to change is the pattern Phase 1 used for feature migration (pure aliases) — which this spec replaces.

---

## 3. The four patterns — honest comparison

Before committing to a pattern, an honest look at what's actually available in the React/TypeScript ecosystem for this problem.

### Pattern A — Flat, no layering

Components import the API response type directly. Fetch functions return the raw backend shape.

**Pros:** Zero ceremony. Single source of truth. Easy to onboard.
**Cons:** UI is welded to API vocabulary and shape. Every backend rename ripples into every component. No place to compute derived fields. No place to drop fields the UI doesn't care about. No seam for answering "what does the UI actually use?"

This is what most small React apps do. It works until the domain gets complex.

### Pattern B — DTO + Domain + Mapper (anti-corruption layer)

Two type universes with an explicit mapping function between them.

- **DTO types** (`@/generated/api`) — the wire format. Generated from OpenAPI. Never imported by components.
- **Domain types** (`features/<x>/domain.ts`) — the UI's vocabulary. Hand-written. Named in UI terms. May rename, enrich, or omit DTO fields.
- **Mappers** (`features/<x>/mappers.ts`) — one function per domain type: `dtoToEvaluation(dto: EvaluationDetailDto): Evaluation`.
- **Fetch functions** call the API, run the mapper, return domain types.
- **Components** import from `features/<x>` — they see only domain types.

**Pros:** UI vocabulary can diverge from API vocabulary. Backend renames ripple into one file (the mapper), not thirty components. The mapper is a natural place to parse dates, compute derived fields, normalize nullability. The mapper is the place where "UI chose less than API" becomes visible — compile-time if done right. Component tests use domain fixtures, not API fixtures, which are smaller and more expressive.
**Cons:** Boilerplate. Two type sources to keep consistent (solved by exhaustiveness check). For purely CRUD features where domain = DTO, the layer is pure ceremony — accepted as a small cost for uniformity.

### Pattern C — Type-level projection

Use TypeScript type operators to derive domain types from DTOs without a runtime mapper.

```typescript
type Evaluation = Omit<EvaluationDetailDto, 'internal_hash'> & {
  period: { from: string; to: string }  // synthesized field
}
```

**Pros:** No runtime cost.
**Cons:** A trap. The synthesized `period` above lies — the DTO still has `period_start`/`period_end` and no one ever constructed the `period` object. The type says the field exists; the runtime data doesn't. You either restrict yourself to pure `Omit`/`Pick` (limiting expressiveness) or you end up writing a runtime mapper anyway. **Rejected.**

### Pattern D — React Query `select` transform

Let the query boundary be the mapping point via `useQuery`'s `select` option.

**Pros:** Lightweight. Incremental adoption. Lives where consumers already are.
**Cons:** Only covers data that goes through React Query. Mutations, imperative fetches, and any non-query usage bypass the transform. `select` runs on every render unless carefully memoized — easy performance footgun. Leaves half the surface uncovered in a codebase that uses `fetch()` directly in places.

---

## 4. Decision — Pattern B

**TROPEK adopts Pattern B: DTO + Domain + Mapper.**

Reasoning:

- The evaluation domain is complex enough to earn a real domain layer. Components currently reach into `evaluation.indicators[i].pass_criteria` and parse criteria strings inline at render time. That's API-shape leaking into render logic. A mapper parses criteria strings once at the fetch boundary and stores them as structured objects in the domain type.
- TROPEK is a dashboard app that will outlive its current single-developer stage. Insulating components from API churn is worth the boilerplate cost.
- Pure CRUD features (datasources, sli_registry lookups) get a trivial identity mapper. That's acceptable — the boundary exists so future changes don't leak, and the cost is ~20 lines per feature.
- Cross-checking (see §7) requires an explicit mapping function to work. Patterns A, C, and D don't give you a single place to enforce "every DTO field is either mapped or explicitly dropped."

---

## 5. Directory structure

Every migrated feature follows this shape:

```
ui/src/features/<feature>/
├── api.ts          # fetch functions, return domain types (run mappers before returning)
├── domain.ts       # domain types — the UI's vocabulary
├── mappers.ts      # dtoToX functions (+ xToDto for write paths if needed)
├── hooks.ts        # React Query wrappers around api.ts
├── fixtures.ts     # domain test fixtures (optional, per-feature)
├── index.ts        # re-exports domain types and hooks ONLY — no mappers, no DTOs
└── components/
    └── *.tsx       # import domain types from '@/features/<feature>'
```

Hard rules:

1. **Components never import from `@/generated/api`.** Enforced by an ESLint rule (see §9) that forbids `import … from '@/generated/api'` anywhere outside `features/*/mappers.ts` and `features/*/api.ts`.
2. **`features/*/index.ts` never re-exports from `mappers.ts` or from `@/generated/api`.** The DTO types stay invisible to consumers.
3. **Domain types live in `domain.ts`, never in `types.ts`.** The file rename is intentional — `types.ts` was the hand-written-guesses file. Renaming to `domain.ts` makes the boundary visible in file listings.
4. **UI-only types (heatmap state, tree expansion, chart config, component prop types) live in a separate file: `features/<x>/ui-types.ts`.** Clearly labeled as UI-only, not exported from `index.ts`, imported directly by the components that need them. No backend equivalent, no mapper.

### Placement of mappers in the fetch flow

```
React Query hook
    ↓ calls
api.ts function (fetchEvaluation)
    ↓ calls
fetch(...)
    ↓ returns
raw JSON → cast to DTO type
    ↓ passed to
mapper (dtoToEvaluation)
    ↓ returns
domain type
    ↓ stored in React Query cache
```

**Mappers run exactly once per network request, in the fetch function, before returning to React Query.** They do NOT run inside React Query's `select` option (which re-runs on every render). See §8 for the performance reasoning.

---

## 6. Naming conventions

### 6.1 DTO suffix for generated types

When a feature references the generated wire type in a mapper or fetch function, it uses the `Dto` suffix:

```typescript
import type { components } from '@/generated/api'

type EvaluationDetailDto = components['schemas']['EvaluationDetail']
type EvaluationSummaryDto = components['schemas']['EvaluationSummary']
```

This keeps the boundary legible — grepping for `Dto` in a component file flags a boundary violation immediately. The generated `components['schemas']['X']` pattern is verbose; the DTO suffix alias stays local to `mappers.ts` and `api.ts`.

### 6.2 Domain types use UI vocabulary

Domain names are chosen for the UI's conceptual model, not for 1:1 mirroring of the DTO:

- `Evaluation` (not `EvaluationRun` — "run" is backend orchestration vocabulary)
- `Outcome` as a typed literal union (not `result: string`)
- `Indicator` with parsed `criteria: Criteria` (not `pass_criteria: string`)
- `Period` / `DateRange` (not `period_start: string, period_end: string`)
- `BaselinePin` (struct, not individual fields scattered on the parent)

The discovery phase (§10) produces a proposed renaming list; the design/spec phase after discovery commits to a final list.

### 6.3 Mapper naming

- `dtoToEvaluation(dto: EvaluationDetailDto): Evaluation` — read path, one per domain type
- `evaluationToDto(evaluation: Evaluation): EvaluationCreateDto` — write path, only when needed (most features are read-only enough that write paths use DTO directly)
- `dtoToEvaluationList(dto: { items: EvaluationSummaryDto[] }): Evaluation[]` — collection helper, often just `.items.map(dtoToEvaluationSummary)`

---

## 7. Cross-checking — "is the UI intentionally covering less than the API?"

Three complementary mechanisms. All three are used; they serve different purposes.

### 7.1 Mapper exhaustiveness (compile-time)

Every mapper asserts via TypeScript that every DTO field is accounted for — either mapped into the domain type or explicitly listed as dropped.

```typescript
// mappers.ts
import type { components } from '@/generated/api'
import type { Evaluation } from './domain'

type EvaluationDetailDto = components['schemas']['EvaluationDetail']

// Explicit list of DTO fields the UI intentionally ignores.
// Every entry MUST have a comment explaining why.
type DroppedKeys =
  | 'internal_hash'          // backend cache key, no UI use
  | 'raw_query_latency_ms'   // backend perf metric, not user-facing
  | 'worker_id'              // backend orchestration detail

// Compile-time check: every non-dropped DTO key must appear in the domain
// type (either directly or via a rename documented in the mapper). If a new
// field is added to the DTO and nobody updates this list, the assertion
// below fails and you're forced to make a decision.
type RequiredKeys = Exclude<keyof EvaluationDetailDto, DroppedKeys>
type _AssertAllMapped = RequiredKeys extends keyof EvaluationMapping ? true : never

// EvaluationMapping is an internal helper listing exactly which DTO keys
// are consumed by the mapper. It's hand-maintained in lock-step with the
// mapper body. When mapper + DroppedKeys + EvaluationMapping all agree,
// TypeScript is happy.
type EvaluationMapping = {
  id: true
  asset_name: true
  slo_name: true
  // ...
}

export function dtoToEvaluation(dto: EvaluationDetailDto): Evaluation {
  return {
    id: dto.id,
    assetName: dto.asset_name,   // UI uses camelCase; mapper does the conversion
    sloName: dto.slo_name,
    // ...
  }
}

const _check: _AssertAllMapped = true
```

The exact TypeScript shape of the exhaustiveness check is a design detail that will be refined during implementation planning. The important property is: **adding a field to the backend Pydantic schema forces a compile-time decision in the mapper on the next `just codegen`**. No silent drops, no silent additions.

### 7.2 UI usage audit (periodic, committed report)

A script walks `features/<x>/components/*.tsx`, extracts property accesses on the domain type, and produces a three-column table:

| DTO field | In domain? | Used by UI? | Decision |
|---|---|---|---|
| `id` | ✓ | ✓ | standard |
| `score` | ✓ | ✓ | standard |
| `baseline_pin.scope` | ✗ | ✗ | **GAP** — backend supports `"all" \| "per_slo"`, UI only pins all |
| `internal_hash` | ✗ (dropped) | ✗ | intentional drop (backend cache key) |

The report is committed as `docs/ui-coverage/<feature>.md`. The script runs as part of the CI freshness check — a new DTO field that's neither mapped nor dropped shows up as "unaccounted" and the job fails.

This is the mechanism that would have surfaced the baseline-pin gap the user originally called out, automatically, from the first Pact-less run.

### 7.3 Coverage-decision tests (executable documentation)

For important "we chose less" decisions, a unit test documents the choice:

```typescript
// features/evaluations/coverage.test.ts
test('baseline pin: UI exposes only whole-evaluation pinning', () => {
  // The backend BaselinePin type has `scope: "all" | "per_slo"`.
  // The UI only offers "all". If per-SLO pinning is added to the UI,
  // update the mapper + component AND delete this test.
  const dto = makeDtoFixture()
  const domain = dtoToEvaluation(dto)
  expect('scope' in (domain.baselinePin ?? {})).toBe(false)
})
```

This is executable documentation that fails loudly when someone accidentally re-expands the coverage. Searchable by grepping for the reason.

---

## 8. Performance considerations

### 8.1 Where mappers run

Mappers run exactly **once per network request**, inside the fetch function in `api.ts`, before returning to React Query. React Query's cache stores the domain type, not the DTO. Rendering components never triggers re-mapping.

### 8.2 Why map at the fetch boundary rather than in `select`

React Query's `select` option is a legitimate tool, and TkDodo (React Query maintainer) actually recommends it *above* `queryFn` for transforms in the general case — his main argument is that `select` enables partial subscriptions, so a component that only reads `evaluation.score` can skip re-rendering when unrelated fields change. See [React Query Data Transformations](https://tkdodo.eu/blog/react-query-data-transformations) and [Selectors, Supercharged](https://tkdodo.eu/blog/react-query-selectors-supercharged).

Despite that, TROPEK maps at the fetch boundary (inside `queryFn`, so the cache stores the domain type). This is a deliberate trade-off, not a dismissal of `select`:

- **Single type system in the cache.** With boundary mapping, the cache stores `Evaluation`, and every consumer — queries, mutations, future `setQueryData` writes, optimistic updates — speaks the same language. With `select`, the cache stores the DTO and transformed views come out on read; mutations writing to the cache must produce DTOs, which either pushes us toward symmetric write-path mappers (§11.3) or creates a two-type-system mental model.
- **TROPEK doesn't exploit partial subscriptions today.** Zero `select` usages exist in the current codebase. The benefit that motivates TkDodo's recommendation is unrealized here, so we pay none of its cost by choosing the other fork.
- **`useQueries` compatibility.** TROPEK uses `useQueries` in the registry and metric-explorer pages for multiplexed fetches. Boundary mapping Just Works; per-query `select` on multiplexed queries is awkward.
- **Existing precedent.** `fetchEvaluations` already performs a fetch-boundary transform (aggregating paginated responses into `{items, total, truncated}`). Boundary mapping extends a pattern that's already in the codebase rather than introducing a new one.
- **Mapper cost is negligible per-render anyway.** Mappers are O(n) in input size with microsecond-scale work (§8.3), so the "don't re-run on every render" argument isn't load-bearing here — the real argument is cache-shape cleanliness, not perf.

`select` remains available and appropriate for **in-component derivation** — e.g. a component reading `useEvaluation(id, { select: e => e.indicators.length })` to subscribe only to the indicator count. It is not used for the DTO → domain boundary crossing.

### 8.3 Mapper cost budget

Mappers for this project should be O(n) in input size with no nested loops. Typical evaluation detail mapper work:

- ~20 field copies (O(1) each)
- Parse 2 date strings with `new Date()` (O(1) each)
- Walk `indicators` array (O(n) where n is the number of indicators, typically 5–30)
- For each indicator, parse one criteria string (O(1) amortized — the criteria grammar is simple)

Total: microseconds per evaluation. Negligible next to React render cost.

### 8.4 Open question — large dataset paths

The user flagged that rendering is already slow for large asset heatmaps. The mapper is not expected to contribute measurably to this, but discovery must confirm by:

1. Locating the largest-response endpoints (heatmap, trend data)
2. Estimating the mapper work for each (field copies, date parses, nested walks)
3. If any mapper touches more than ~10,000 objects, the mapper for that endpoint uses a streaming or in-place strategy, not `.map()`
4. Measuring before and after on a representative dataset if the concern is still live at implementation time

This is a discovery item, not a blocker.

---

## 9. ESLint enforcement

A custom ESLint rule (or a `no-restricted-imports` configuration) enforces that `@/generated/api` is only imported from `features/*/api.ts`, `features/*/mappers.ts`, and (if adopted) `features/*/queryOptions.ts`. Any other file — including `features/*/hooks.ts`, `features/*/components/*.tsx`, and anything outside `features/*` — is a boundary violation and fails lint. `hooks.ts` is explicitly on the forbidden side: if a hook needs the DTO type, that's a signal the mapper boundary is being bypassed.

Configuration sketch (final form decided during implementation):

```js
// eslint.config.js
'no-restricted-imports': ['error', {
  patterns: [{
    group: ['@/generated/api', '@/generated/api/*'],
    message: 'Components must import domain types from features/<x>, never DTOs directly. Use the mapper.',
  }],
}],
```

With a per-directory override allowing `features/*/api.ts` and `features/*/mappers.ts` to import from `@/generated/api`. The exact override mechanism depends on the eslint flat-config layout currently in use.

---

## 10. Discovery phase — what must happen before implementation planning

Implementation planning does not start until discovery is complete and reviewed. Discovery is read-only — no code edits, no file creation beyond the discovery report itself. It happens in a new chat session with a fresh Explore subagent to preserve main-session context.

### 10.1 Discovery deliverables

The discovery phase produces a single committed document:

`docs/superpowers/discovery/2026-04-12-ui-layering-discovery.md`

Containing:

**D1. Feature inventory.** Every `features/<x>/types.ts` (plus `ui/src/lib/types.ts`), listing:
- Every exported type
- Which files in the tree import each type
- Approximate count of consumer files per type

**D2. DTO match table.** Per exported type, one of:
- Direct match — exact name in `@/generated/api` components schemas
- Renamed match — generated schema exists under a different name (e.g. `AssetRead` for UI `Asset`)
- Partial match — some fields overlap, others don't (usually a UI-added derived field)
- No match — purely UI-only

**D3. Drift report.** For every matched type, the shape differences between the hand-written type and the generated DTO, classified as:
- Real backend bug — Pydantic typing that's wrong (e.g., `dict[str, Any]` where it should be `dict[str, str]`) → fix at the source
- Missing-required drift — hand-written marks optional, generated marks required → fix fixtures
- Name divergence — UI renamed something → candidate for domain-level rename
- Derived/synthesized field — UI adds a computed field → belongs in the mapper, not the DTO

**D4. UI-only types.** The list of types with no backend equivalent, each tagged with:
- Why it's UI-only (derived state, prop type, chart config, etc.)
- Whether it references any domain types (and if so, which)

**D5. Proposed domain vocabulary.** A table of proposed domain-layer renames:

| DTO name | Proposed domain name | Reason |
|---|---|---|
| `EvaluationRun` | `Evaluation` | "Run" is backend orchestration vocabulary |
| `result: string` | `outcome: Outcome` | Enum-typed, clearer intent |
| `period_start` + `period_end` | `period: DateRange` | Single domain concept |
| ... | ... | ... |

This table is reviewed and accepted before mapper writing begins.

**D6. Feature migration order.** Proposed order, smallest/simplest first:
1. `datasources` (simple CRUD)
2. `sli_registry` (simple CRUD)
3. `slos` / `slo-groups` (medium complexity)
4. `assets` (already partially done — needs mapper layer added)
5. `registry` (3-mode UI, derived state)
6. `navigator` (heatmap derivations)
7. `evaluations` (largest, most complex, most value)

Order is defensible by: the simplest features validate the pattern with minimum cost; the most complex feature is tackled last when the team has maximum experience with the pattern.

**D7. Mapper cost estimate.** Per feature: approximate lines of boilerplate for domain + mappers. Total tells us the upfront cost of adopting the pattern and identifies features where the boilerplate-to-value ratio is unfavorable.

**D8. Performance audit for large-dataset paths.** Identify endpoints returning >100 domain objects in a typical response. For each, assess whether mapper work is bounded or could become a bottleneck on the largest realistic dataset. Flag any that need custom strategies.

**D9. ESLint current state.** Check whether the current eslint config uses flat-config or legacy, and identify where the `no-restricted-imports` override for `features/*/{api,mappers}.ts` will live.

### 10.2 Discovery scope limits

Discovery does **not** decide:

- Which specific renames to adopt in the domain layer. It proposes; the spec review decides.
- Whether any feature is too complex to migrate. Scope adjustments happen in implementation planning.
- Whether to keep MSW. That's Phase 2 territory.
- Whether React Query `select` is used anywhere outside the planned transform boundary. This informs §11 but isn't a gate.

---

## 11. Resolved questions

The three open questions in earlier drafts of this spec have been resolved via a research + brainstorming session (2026-04-12). The session audited current React Query usage in TROPEK and surveyed community guidance (TkDodo, Josh Karamuth, Jesse Warden, profy.dev). Findings and decisions below.

### 11.1 React Query interaction — RESOLVED: map in `queryFn`

**Decision:** Mappers run inside `api.ts` fetch functions, invoked by `queryFn`. React Query's cache stores domain types. `select` is reserved for in-component derivation and is not used for the DTO → domain boundary.

**Supporting audit findings:**

- Zero current uses of React Query `select` in TROPEK — greenfield decision, no migration burden.
- Zero current uses of `setQueryData` — all cache updates go through `invalidateQueries`. No optimistic updates exist today.
- `useInfiniteQuery` is not used anywhere; `fetchEvaluations` already hand-aggregates pagination inside the fetch function (precedent for boundary transforms).
- `useQueries` is used in 4 locations (registry, metric explorer) for multiplexed fetches where per-query `select` would be awkward.
- `fetchEvaluations` is already doing a fetch-boundary transform today, so boundary mapping extends an existing pattern rather than introducing a new one.

**Consequences:**

- Hooks like `useEvaluation(id)` return `UseQueryResult<Evaluation>`.
- When optimistic updates are eventually added, the cache write produces a domain object directly — no reverse mapper required for the cache path.
- Debugging the raw wire shape requires the browser's Network tab rather than React Query DevTools. Accepted cost.
- The implementation plan should adopt TkDodo's `queryOptions` factory pattern ([The Query Options API](https://tkdodo.eu/blog/the-query-options-api)) as the natural home for the `queryFn` + mapper wiring, matching TROPEK's existing `api.ts` / `hooks.ts` split.

**Follow-up:** if a future change introduces heavy render-time derivations on a specific query that would benefit from `select`-based partial subscriptions, `select` can be added *on top of* the boundary mapping (transforming domain → narrower domain view). The boundary mapping is not incompatible with `select`; it just isn't where `select` lives.

### 11.2 Synchronous vs asynchronous mappers — RESOLVED: strict sync

**Decision:** Mappers are pure synchronous functions. A mapper never performs I/O (no `fetch`, no `await` on anything network-bound).

**Rationale:**

- No authoritative source (TkDodo, TanStack docs, published anti-corruption-layer articles) recommends async mappers. The universal pattern is "compose multiple queries at the hook level," not "let mappers fetch."
- Any plausible async-mapper use case in TROPEK (loading supplementary data for a tooltip, lazily fetching details on user interaction, hydrating cross-entity references) is better modeled as a separate `useQuery` hook that fires on its own trigger. This keeps each network call visible to React Query, individually cacheable, and independently invalidatable.
- Sync mappers are trivially testable as pure functions with no async harness.

**Rule:** multi-resource composition happens at the hook layer via composed queries, never inside a mapper. If a concrete case arises that cannot be solved this way, the decision is revisited via a new spec amendment — not by informally loosening the rule.

### 11.3 Write-path mappers — RESOLVED: pragmatic split (Option 3C)

**Decision:** Forms send backend-shaped request bodies directly by default (Option 3A behavior). A `domainToDto` reverse mapper is written **only** when a specific write path meets one of these triggers:

1. The domain vocabulary (§6.2) legitimately differs from the request body's field names (e.g. domain `period: DateRange` vs request body `period_start` + `period_end`).
2. The domain type uses a typed enum where the request body expects a plain string (e.g. domain `Outcome` → `new_result: string`).
3. The domain type uses a discriminated union where the request body expects a flat either/or shape.
4. The write path performs optimistic updates where the cache write and the network payload need to diverge in shape.

If none of these triggers fire, the form's data type **is** the request body type, and no reverse mapper exists.

**Audit findings.** Every current TROPEK write path (asset CRUD, SLO CRUD, SLI CRUD, datasource CRUD, slo-group CRUD, asset-group membership, asset-type CRUD) sends a snake_case flat body that already matches the Pydantic model. These paths receive no reverse mapper. Three evaluation write paths are flagged for discovery review — they may or may not need reverse mappers depending on the domain vocabulary chosen in §D5:

| Write path | File | Why flagged |
|---|---|---|
| `triggerEvaluation` | `features/evaluations/api.ts` | Form has `period_start` + `period_end`; if domain uses `period: DateRange`, a reverse mapper splits it back into two string fields |
| `reEvaluate` | `features/evaluations/api.ts` | Body has `from_baseline` XOR `from_date`; if domain models this as a discriminated union, a reverse mapper flattens it |
| `overrideStatus` | `features/evaluations/api.ts` | Sends `new_result: string`; if domain uses an `Outcome` enum, a reverse mapper converts enum → string |

These are **inspection points**, not commitments. Discovery §D5 produces the domain vocabulary; the implementation plan for the evaluations migration decides per path whether a reverse mapper is needed.

**Naming:** reverse mappers follow the convention `xInputToDto(input: XInput): XCreateDto` (or `XUpdateDto`) and live next to `dtoToX` in the same `mappers.ts` file. The `XInput` type represents "what the form produces" — which may or may not equal the read-side domain type `X`, depending on whether creation requires fields that reads don't expose or vice versa.

---

## 12. Superseded Phase 1 plan — how existing work fits

The existing Phase 1 plan (`docs/superpowers/plans/2026-04-12-contract-testing-phase-1-openapi-codegen.md`) is partially superseded by this spec. Specifically:

- **Still valid:** Tasks 1–5, 7, 8 — the tooling foundation (schema export, codegen, freshness check, CI workflow, generated types README). These remain the base everything builds on.
- **Superseded by this spec:** Task 6 (the assets migration to pure aliases). Under the new pattern, `features/assets/domain.ts` holds domain types, `features/assets/mappers.ts` holds the mapper, and `features/assets/types.ts` is renamed to `domain.ts`. The pure-alias work from Phase 1 becomes the starting point for the mapper — the aliases move into `mappers.ts` as the (currently trivial) domain types, and a proper `dtoToAsset` function is added.

The existing `feat/contract-testing-phase-1` worktree is **kept and expanded**. When the new implementation plan is ready:

1. The worktree rebases onto any new spec changes
2. `features/assets/` is refactored per the new pattern as the first task of the expanded plan (revalidating the pattern before applying to other features)
3. The remaining features are migrated in the order from §10 D6

No work from the existing worktree is discarded. The backend Pydantic fix, the fixture padding, and the tooling setup all remain.

---

## 13. Next session kickoff — what to hand the fresh agent

Because this spec grew long and the main session's context budget is depleted, the discovery phase runs in a new chat. That session should be bootstrapped with:

1. A pointer to this spec (`docs/superpowers/specs/2026-04-12-ui-layering-design.md`)
2. A pointer to the original contract testing design (`docs/superpowers/specs/2026-04-12-contract-testing-design.md`) for broader context
3. A pointer to the existing Phase 1 worktree (`.worktrees/contract-testing-phase-1/`) so the agent can see the tooling already in place and the assets migration as a reference
4. An instruction to produce the discovery document at `docs/superpowers/discovery/2026-04-12-ui-layering-discovery.md` covering sections D1–D9 from §10.1
5. A reminder that discovery is read-only — no code edits, no file creation except the discovery report itself
6. An instruction to use an Explore subagent for the bulk of the reading to keep main-session context clean

Suggested opening prompt for the new session:

> I need to do discovery for a UI layering refactor. The architecture is documented at `docs/superpowers/specs/2026-04-12-ui-layering-design.md` — please read it first. Then dispatch an Explore subagent to produce the discovery document at `docs/superpowers/discovery/2026-04-12-ui-layering-discovery.md` covering sections D1–D9 from §10.1 of the spec. Read-only — no code changes. Existing Phase 1 work is in `.worktrees/contract-testing-phase-1/`.

---

## 14. Acceptance criteria

This spec is considered "complete enough to start discovery" when:

- [x] Problem statement clearly identifies the drift and coverage-gap risk (§1)
- [x] All four patterns are described with honest pros and cons (§3)
- [x] Pattern B is explicitly chosen with reasoning (§4)
- [x] Directory structure is specified (§5)
- [x] Naming conventions are specified including DTO suffix decision (§6)
- [x] Three cross-checking mechanisms are specified (§7)
- [x] Performance rationale for fetch-boundary mapping is captured (§8)
- [x] ESLint enforcement is described (§9)
- [x] Discovery deliverables are enumerated (§10)
- [x] Open questions are captured for future sessions (§11)
- [x] Relationship to existing Phase 1 work is explicit (§12)
- [x] Next-session kickoff instructions are explicit (§13)

This spec is considered "complete enough to start implementation planning" after discovery returns and its findings are reconciled with the spec (which may mean adding a §15: reconciliation notes from discovery).

---

## 15. Reconciliation notes from discovery (2026-04-12)

Discovery ran on 2026-04-12 and produced `docs/superpowers/discovery/2026-04-12-ui-layering-discovery.md`. Four UNCLEAR items from the initial audit were resolved in a targeted follow-up. This section captures the deltas to the earlier spec sections, the execution chunking decided in the same session, and the prerequisites that must land before implementation planning begins.

### 15.1 Backend contract bugs surfaced (9 total, up from 7)

Discovery's D3 found 7 Pydantic `dict[str, Any]` / typing bugs. The Item 2 follow-up confirmed both flagged `SLODefinitionRead` issues at high confidence and surfaced two additional ones (`comparison`, `tags`) while reading. Final count: **9 backend bugs**, all of the same "tighten `dict[str, Any]` to a concrete type" pattern. All nine are fixed in Chunk A (§15.5).

Full list:

| # | Module / file | Field | Fix |
|---|---|---|---|
| 1 | `quality_gate/schemas/evaluations.py` | `EvaluationDetail.asset_snapshot: dict[str, Any]` | new typed model |
| 2 | `quality_gate/schemas/evaluations.py` | `EvaluationDetail.sli_metadata: dict[str, Any] \| None` | `SliMetadata` model |
| 3 | `quality_gate/schemas/evaluations.py` | `EvaluationSummary.variables: dict[str, Any]` | `dict[str, str]` |
| 4 | `quality_gate/schemas/results.py` | `IndicatorResult.pass_targets` / `warning_targets: list[dict[str, Any]] \| None` | `list[PassTarget]` |
| 5 | `quality_gate/schemas/heatmap.py` | `HeatmapCellGrouped.pass_targets` / `warning_targets` | same as (4) |
| 6 | `assets/schemas.py` | `AssetRead.heatmap_config: dict[str, Any] \| None` | **not fixed — stays opaque** (see §15.3) |
| 7 | `quality_gate/schemas/heatmap.py` | `SloGroup` / `SLOGroupRead` name collision in OpenAPI | disambiguate schema names |
| 8 | `slo_registry/schemas.py` | `SLODefinitionRead.variables: dict[str, Any]` (also `SLODefinitionCreate.variables`) | `dict[str, str]` |
| 9 | `slo_registry/schemas.py` | `SLODefinitionRead.method_criteria: dict[str, Any] \| None` (also `SLODefinitionCreate`) | new `MethodCriteriaOverride` model with 4 optional fields — shape fully specified in `docs/old-implemented/specs/2026-03-29-prometheus-sli-adapter-design.md:381` |

Bonus fixes worth bundling into Chunk A because they're the same pattern touching the same files: `SLODefinitionRead.comparison: dict[str, Any]` → `ComparisonConfig` model (5 named optional fields), and `SLODefinitionRead.tags: dict[str, Any]` → `dict[str, str]`.

### 15.2 Item 1 — `evaluation_metadata` is dead code

The UI's hand-written `EvaluationSummary`/`EvaluationDetail` declare `evaluation_metadata` but the backend has no such field. Git history shows commit `7043b1a` renamed `evaluation_metadata` → `variables` in the Pydantic schemas and the DB column. The UI read sites (`features/evaluations/types.ts:54,105`, `hooks.ts:203`, `EvaluationTable.tsx:156`) never caught up. A contract test at `api/tests/test_schema_contracts.py:99-104` already guards the backend against regression.

**Resolution:** delete `evaluation_metadata` from UI types, rename read sites to `variables`, update the 6 test fixtures and `mocks/generate.ts` that still populate the old key. Folded into Chunk A, not the evaluations migration — it's a correctness cleanup, not a mapper concern.

### 15.3 Item 3 — Trigger Evaluation modal is broken

The Trigger Evaluation modal is a real user-facing feature, but was never exercised against a real backend after a rename landed. Current state:

- UI posts `POST /api/evaluations` — that endpoint **does not exist**. Only `POST /api/evaluate` exists (`api/tropek/modules/quality_gate/router.py:56`).
- UI body shape doesn't match `EvaluateSingleRequest` (`quality_gate/schemas/trigger.py:13-20`): missing required `asset_name`, uses wrong field names (`evaluation_name` vs `eval_name`, `metadata` vs `variables`), sends unknown fields (`group_name`, `slo_name`) that `StrictInput` rejects with 422.

Only caller: `TriggerEvaluationModal.tsx:43`. Confirmed by the user that the feature is intended to work — the regression was invisible because no one clicked the button against a real backend.

**Resolution:** fix the UI in Chunk A. Rewrite `TriggerEvaluationPayload` to match `EvaluateSingleRequest`, change the URL, add `asset_name` to the form. A reverse mapper (`triggerEvaluationInputToDto`) is added later during the evaluations migration (Chunk B3) for cosmetic symmetry — not required for the Chunk A fix.

### 15.4 Item 4 — `heatmap_config` stays opaque

`AssetRead.heatmap_config` is `dict[str, Any] | None` by intent, not by accident. Originating plan `docs/old-implemented/plans/2026-03-19-duplicate-evaluation-prevention.md:139-172` describes it as "per-asset default filter preferences" but the shape was never designed and the field has **zero UI consumers today**.

**Resolution:** do NOT fix this one in Chunk A. In the domain layer, type it as `Record<string, unknown> | null`. Pass-through mapper. When someone eventually wires a filter-preferences form, design the `HeatmapConfig` schema at that time and migrate. A memory note (`memory/project_heatmap_config_investigation.md`) captures the deferred design work so it doesn't get silently re-typed in the future.

### 15.5 Execution chunking

Implementation is split into four chunks, each with its own manual-test checkpoint on a real backend instance. Chunks A and C land on `main` independently; chunks B1–B3 land sequentially on top of A.

#### Chunk A — API contract cleanup *(standalone PR to main)*

All correctness work that is an improvement regardless of Pattern B. Lands first so `main` gets the bug fixes sooner and the migration has a clean baseline.

Contents:
1. Fix 9 backend Pydantic bugs (§15.1) plus the two bonus `SLODefinitionRead` fixes (`comparison`, `tags`).
2. Fix the Trigger Evaluation modal (§15.3) — URL, body shape, required `asset_name`.
3. Delete `evaluation_metadata` from UI types, rename read sites to `variables` (§15.2).
4. Rebase the Phase 1 tooling (`export-schema`, `codegen`, `check-schema-fresh`, `.github/workflows/contract-freshness.yml`) onto `main` — lands `ui/src/generated/api.ts` on `main` for the first time. Required prerequisite for Chunks B1–B3.

**Reuses the existing `.worktrees/contract-testing-phase-1/` worktree** — it already has the tooling foundation and the Phase 1 backend bug fix. No new worktree.

**Manual test:** dev server smoke test — assets list, SLO list, evaluations list, trigger a real evaluation end-to-end, verify no regressions.

#### Chunk B1 — Pattern B migration: simple features *(PR on top of A)*

Apply the DTO / Domain / Mapper pattern to every feature through assets. Validates the pattern six times before hitting the complex features.

Order (revised from §10 D6 based on discovery findings):
1. `datasources` — trivial CRUD, end-to-end validation of the pattern.
2. `registry` — zero mapper cost, pure `types.ts` → `ui-types.ts` rename (discovery found all five types are UI state with no backend analogue). Moved earlier than the original §10 D6 order.
3. `sli_registry`
4. `slos`
5. `slo-groups`
6. `assets` — upgrade from Phase 1 pure-alias to full mapper.

**Manual test:** for each feature, render its page in the dev server and verify it looks identical to before. Single cross-feature smoke test at the end.

#### Chunk B2 — Navigator *(PR on top of B1)*

Navigator gets its own chunk because of the heatmap rename and the mapper's presentation logic (cell coordinate attachment, result sentinel normalization, y-index math lifted out of `utils.ts`).

- `HeatmapCell` (UI-only ECharts type) renamed to `HeatmapEChartsCell` in `features/navigator/ui-types.ts`.
- `HeatmapCell` (backend DTO) is referenced as `HeatmapCellGroupedDto` in the mapper (§6.1 DTO suffix convention).
- `assetHeatmapDtoToDomain(resp, expandState)` owns: y-index math, cell coordinate attachment, collapsing `invalidated` sentinel into canonical `result` union, building the per-SLO summary lookup.
- `buildAssetHeatmapData` in `navigator/utils.ts` shrinks by ~80 lines as its work moves into the mapper.
- **No perf work.** Those wins are Chunk C.

**Manual test:** render the navigator heatmap against a realistic dataset, verify row ordering, expand/collapse, composite row, SLO summaries, and cell coloring all match current behavior.

#### Chunk B3 — Evaluations *(PR on top of B2)*

The biggest and last feature migration. Everything the pattern is designed for:

- `Evaluation` domain type with `period: DateRange` (replaces `period_start`/`period_end`), `outcome: Outcome` (typed union), `BaselinePin` struct (replaces scattered `baseline_pin_author`/`reason`/`pinned_at`/`unpinned_at` fields that discovery found **entirely absent** from the hand-written UI types — the exact coverage gap §7 was designed to surface).
- `Indicator` domain type with parsed `criteria: Criteria` struct (replaces `pass_criteria: string`).
- Reverse mappers (`xInputToDto`) for the three write paths flagged in §11.3: `triggerEvaluation`, `reEvaluate`, `overrideStatus`. `triggerEvaluation`'s shape fix already landed in Chunk A — the B3 work is the cosmetic mapper wrapping the already-correct shape.
- Inline date parsing and string-slicing in `EvaluationHeatmap.tsx`, `EvaluationTable.tsx`, `EvaluationSummaryCard.tsx`, `ReEvaluateForm.tsx` is removed — the mapper does it once at the fetch boundary.

**Manual test:** the evaluations list, detail page, re-evaluation form, baseline pin flow, override status flow, trigger evaluation flow. Full regression pass on the evaluations feature.

#### Chunk C — Heatmap performance *(separate worktree, after B3 lands)*

Deferred. Three concrete wins, ranked by impact/effort:

1. **Redis cache grouped heatmap response** per `(asset_id, from, to, eval_names)` key with ~60s TTL, invalidated on new eval completion. Matches the pre-existing memory note `project_column_level_redis_caching.md`. (H impact / M effort)
2. **Hoist `pass_targets` / `warning_targets` to per-metric** in `SloGroup.metrics[]` instead of per-cell. Shrinks payload, halves Pydantic instantiations. (M impact / L effort)
3. **Precompute `resolve_targets()` per objective** once instead of twice per cell (`presenter.py:158-169`). Pairs with (2). (M impact / L effort)

Runs in a separate worktree with load testing, not inline with feature migration. Not blocked by Chunk B; could run in parallel but is deferred by user preference to "stabilize before optimizing."

### 15.6 Migration order changes from §10 D6

One change to the originally proposed §10 D6 order: **`registry` moves from position 5 to position 2** (between `datasources` and `sli_registry`). Discovery found that all five `registry` types are pure UI state with zero backend analogue — it's a `types.ts` → `ui-types.ts` rename with no mapper and no domain file. That makes it the cheapest migration in the tree and a confidence booster early in Chunk B1.

### 15.7 Prerequisites

Before implementation planning starts:

- [x] Discovery document exists and is reviewed
- [x] §15 reconciliation notes (this section) are written
- [ ] User confirms chunking strategy (confirmed 2026-04-12 — four-chunk split A / B1 / B2 / B3 with C deferred)
- [ ] User triages any UNCLEAR items surfaced during planning (none remain at time of writing)

### 15.8 Open items for implementation planning

The implementation plan must still decide:

1. **Backend bug fixes (9+2): one commit or several?** Recommend grouping by Pydantic file (3–4 commits max) to keep blast radius small and make bisect easy.
2. **Chunk A rollout:** does the backend bug fix commit go on `main` *before* the Phase 1 tooling rebase, or after? Recommendation: bugs first, then tooling rebase that regenerates `api.ts` against the now-correct Pydantic — so the first committed `api.ts` on `main` is already clean.
3. **Per-feature mapper cost budget.** Discovery D7 estimated boilerplate per feature; the plan should cap review effort per chunk and split further if any single feature exceeds the cap.
4. **Chunk C trigger.** Perf work starts after B3 lands, but on what signal? A scheduled follow-up, or wait until a user complaint? Recommend scheduled — the memory note has been open long enough.

These are planning-session concerns, not spec concerns.
