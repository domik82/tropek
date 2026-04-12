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

### 8.2 Why not `select`

React Query's `select` option is tempting because it co-locates transform logic with the hook. It's the wrong place for a mapper in this project:

- `select` runs on every render unless memoized. For a mapper that parses dates, walks indicator arrays, and parses criteria strings, that's non-trivial work per render.
- Memoization in `select` is subtle — reference equality on the DTO is not preserved across refetches, so naive `useMemo` doesn't help.
- The mapper becomes a render-critical path. For large evaluation datasets (TROPEK already sees rendering slowness on large asset heatmaps), this is the wrong layer to pay that cost.

By mapping at the fetch boundary, the cost is paid once per refetch — which matches how often the underlying data actually changes. React Query cache hits return the already-mapped domain type with reference-equal stability.

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

A custom ESLint rule (or a `no-restricted-imports` configuration) enforces that `@/generated/api` is only imported from `features/*/api.ts` and `features/*/mappers.ts`. Any component file importing it is a boundary violation and fails lint.

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

## 11. Open questions for future sessions

### 11.1 React Query interaction

The user has flagged uncertainty about how Pattern B interconnects with React Query idioms. The proposed default (§5, §8) is:

- Mappers run inside `api.ts` fetch functions
- React Query `queryFn` calls the fetch function and caches the domain type
- React Query `select` is unused for the DTO→domain transform (but remains available for further derivation inside a component)
- Hooks like `useEvaluation(id)` return `UseQueryResult<Evaluation>`

This default is reasonable but not fully examined. A separate brainstorming session should:

1. Audit current React Query usage in TROPEK (where `useQuery`, `useMutation`, `useInfiniteQuery` are used, and what transforms exist today)
2. Confirm the "map at fetch boundary" default doesn't break existing patterns
3. Decide how mutations interact — whether `useMutation` needs a symmetric `domainToDto` mapper for write paths or whether writes can send DTOs directly
4. Decide how optimistic updates work with domain types (mutations typically set cache via `setQueryData`, which must write a domain type)
5. Revisit the `select` decision if there's a concrete use case for it

That session is out of scope for this spec. The conclusions land in a follow-up spec or an amendment to this one.

### 11.2 Synchronous vs asynchronous mappers

This spec defaults to **synchronous mappers**. Rationale:

- Simpler to compose and test
- React Query's `queryFn` can `await fetch(...)` then synchronously map; no added latency beyond the network
- Asynchronous mappers would allow the mapper to fetch auxiliary data (e.g., hydrate an asset reference from a separate endpoint) — but that's better modeled as multiple queries joined in a hook, not as a mapper responsibility

If a concrete need for an async mapper arises during migration, it's added then with a clear rationale. Until then, mappers are pure synchronous functions.

### 11.3 Write-path mappers

Most features are predominantly read-only from the UI's perspective. For the few write paths (creating/updating assets, triggering evaluations, pinning baselines), the spec accepts two possibilities:

- **Option A:** Send DTO types directly from the UI. The domain-to-DTO conversion is trivial (often a renaming of UI-level fields back to `snake_case`) and the anti-corruption layer has less value on write than on read.
- **Option B:** Symmetric `domainToDto` mappers for every write path.

Default: **Option A** unless a write path has non-trivial transformation. Discovery §D5 flags write paths where the UI's domain vocabulary differs enough from the DTO to justify Option B.

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
