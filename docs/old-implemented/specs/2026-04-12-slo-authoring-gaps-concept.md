# SLO Authoring Paths — Concept & Known Gaps

**Date:** 2026-04-12
**Status:** Concept document — captures the gap between documented design and current implementation. Not a plan. Not a spec. Intended as the landing page for anyone who later picks up "why can't I create an SLO in the UI" or "the method override feature doesn't do anything."
**Related:**
- Spec `docs/old-implemented/specs/2026-03-29-prometheus-sli-adapter-design.md` §5 — the original Level-2 method expansion design
- Plan `docs/old-implemented/plans/2026-03-30-aggregated-mode-e2e.md` — aggregated-mode adapter rollout
- Contract-testing work that surfaced these gaps: `docs/superpowers/plans/2026-04-12-ui-layering-chunk-b1.md`
- Worktree where the schema cleanup landed: `.worktrees/contract-testing-phase-1/` commit `6ca3e1e`

---

## 1. What TROPEK is supposed to let you do

There are meant to be **three** ways to bring a new SLO into the system:

1. **Direct YAML author** — hand-write an SLO YAML following `api_version: tropek/v1`, POST it to the SLO registry. Works today. Used by `scripts/dev-start.sh` and any external automation.
2. **Template + `$__gen_` expansion (SLO Groups)** — write one template SLO with `$__gen_<var>` placeholders, attach it to an SLO Group whose `gen_variables` map contains lists of values, and have the backend generate N concrete SLOs (one per row). Works today for Level-1 expansion; the generator lives at `api/tropek/modules/slo_groups/generator.py`.
3. **SLO Creation Wizard (UI)** — a step-through UI that walks a user through picking a datasource, selecting an SLI, defining objectives, setting comparison config, and producing an SLO definition. Intended but **never end-to-end tested against a real backend**. The scaffold components exist under `ui/src/features/registry/forms/` (`SloWizard.tsx`, `WizardStepIndicators.tsx`, `WizardStepComparison.tsx`, `MethodCriteriaTable.tsx`). User confirmed on 2026-04-12 that they've been creating SLOs via the API directly and the wizard has drifted from reality.

Separately, there's a **Level-2 expansion** concept for aggregated-mode SLIs: a single template objective references an aggregated-mode SLI (e.g. `process-cpu-agg`), the generator reads the SLI's `methods: [mean, p99, max]` list, and produces three concrete objectives (`process-cpu-agg.mean`, `.p99`, `.max`) with per-method criteria overrides pulled from a `method_criteria` dict on the template. This is what the wizard's `MethodCriteriaTable` is designed around.

## 2. What works today

### 2.1 Direct YAML — fully working

Example that round-trips cleanly through the backend:

```yaml
api_version: tropek/v1
kind: SLO
metadata:
  name: http-availability-slo
  display_name: HTTP Availability SLO
spec:
  sli_name: http-service-sli
  sli_version: 1
  kind: standard
  comparison:
    compare_with: several_results
    number_of_comparison_results: 3
    include_result_with_score: pass_or_warn
    aggregate_function: avg
  total_score:
    pass_threshold: 90.0
    warning_threshold: 75.0
  objectives:
    - sli: response_time_p99
      display_name: "Response Time P99 (ms)"
      pass_threshold: [">0", "<500", "<=+10%"]
      warning_threshold: [">0", "<800", "<=+15%"]
      weight: 2
    - sli: error_rate
      pass_threshold: [">0", "<0.01", "<=+10%"]
      weight: 3
      key_sli: true
    - sli: availability
      pass_threshold: [">=0.999"]
      weight: 2
```

This is the canonical shape. `objectives[].pass_threshold` / `warning_threshold` are list-of-criteria (outer OR, inner AND per `api/docs/evaluation-engine.md:83-85`). `weight` and `key_sli` on the objective are honored by the scoring engine (`api/tropek/modules/quality_gate/evaluation_engine/scoring.py:54,73,82`).

### 2.2 Level-1 template expansion — fully working

A template with `$__gen_<var>` placeholders attached to an SLO Group. The group's `gen_variables` drives expansion row by row. Objectives are copied verbatim into each generated SLO; no per-row modification beyond the placeholder substitution in `name` and `variables`.

Example template (Level-1 only, no Level-2):

```yaml
api_version: tropek/v1
kind: SLO
metadata:
  name: "plugin/$__gen_process_name"
spec:
  kind: template
  sli_name: plugin-metrics-sli
  sli_version: 1
  display_name: "Plugin Health — $__gen_process_name"
  variables:
    process_name: "$__gen_process_name"
    AGGREGATION_WINDOW: "5m"
  objectives:
    - sli: cpu_usage
      pass_threshold: ["<80"]
      warning_threshold: ["<90"]
      weight: 1
      key_sli: true
    - sli: memory_usage
      pass_threshold: ["<1073741824"]
      weight: 1
  tags:
    category: plugin-health
```

Attach to a group with `gen_variables: {process_name: [word, excel, ppt]}` and the generator emits three concrete SLOs: `plugin/word`, `plugin/excel`, `plugin/ppt`.

Code path: `api/tropek/modules/slo_groups/generator.py:generate_slo_specs()`.

### 2.3 Aggregated-mode SLIs with manually-expanded objectives — working

You can write a template that references an aggregated-mode SLI and **hand-enumerate** the per-method objectives. No magic, no `method_criteria`, just explicit objective rows:

```yaml
api_version: tropek/v1
kind: SLO
metadata:
  name: "cpu-agg/$__gen_process_name"
spec:
  kind: template
  sli_name: process-cpu-agg
  variables:
    process_name: "$__gen_process_name"
    host: "localhost"
  objectives:
    - sli: process-cpu-agg.mean
      display_name: "CPU Mean %"
      pass_threshold: ["<10"]
      weight: 1
    - sli: process-cpu-agg.p99
      display_name: "CPU P99 %"
      pass_threshold: ["<25"]
      weight: 2
      key_sli: true
    - sli: process-cpu-agg.max
      display_name: "CPU Max %"
      pass_threshold: ["<40"]
      weight: 1
  total_score:
    pass_threshold: 90.0
    warning_threshold: 75.0
```

This combines Level-1 expansion (one SLO per process_name) with aggregated-mode SLI metric collection (adapter produces `.mean`, `.p99`, `.max` derived metrics). Neither the generator nor the scoring engine needs to know anything about "methods" — the author has already materialized the method list into three concrete objective rows.

**This is the `manual` path that works today.** Any SLO shown in the UI that references an aggregated-mode SLI today should look like this.

## 3. What's missing

### 3.1 SLO Creation Wizard — not end-to-end tested

**Scaffold exists:** `ui/src/features/registry/forms/SloWizard.tsx` and its step components. The wizard's intended flow:

1. Pick datasource (binds to a `DataSourceRead`)
2. Pick SLI (binds to a `SLIDefinitionRead`, either raw-mode or aggregated-mode)
3. Define per-indicator objectives
4. Set comparison config
5. Review
6. Submit `SLODefinitionCreate` to the API

**Known failures (as of 2026-04-12):**

- `WizardStepComparison.tsx:66` exposes a `baseline_mode: 'previous' | 'manual'` dropdown. The `baseline_mode` field is nowhere on the backend `ComparisonConfig` schema — the backend silently dropped it via `extra='allow'` until the 2026-04-12 schema cleanup tightened the type. `baseline_mode` is a **UI phantom**: sent, accepted, dropped, never consumed. The dropdown has no effect.
- `SloWizard.tsx:50,86,211` and `SloWizard.test.tsx:61` all reference `baseline_mode`. Dead code path.
- `MethodCriteriaTable.tsx` shows a per-method override grid (pass_threshold + weight + key_sli per method name). The backend stores `method_criteria` as JSONB on `SLODefinition` but **no code anywhere reads it during template instantiation** — it's dead storage (see §3.2). The wizard can write it, the database can store it, and nothing ever applies it.
- No integration test or Playwright/Cypress-level e2e exercises the wizard against a real backend. The component tests in `SloWizard.test.tsx` cover rendering and state transitions only.
- The mock data generator (`ui/src/mocks/handlers/slos.ts:26`) still produces `baseline_mode: 'none'` on SLO responses, which is invented data — the backend never returns that field.

**Design decisions that need to be made before the wizard is useful:**

- **What does the wizard do with aggregated-mode SLIs?** Options:
  - (a) Show only one objective row (the SLI itself) and defer method expansion to Level-2 generator magic (which doesn't exist — see §3.2)
  - (b) Show N objective rows, one per method in the SLI's `methods` list, and let the user edit each explicitly — matching the working "manual" path from §2.3
  - (c) Require the user to pick a single method and generate a single objective
  - **Recommended path forward:** (b). Matches the `manual` path that works today. No dependency on Level-2 expansion. Requires the wizard to query the SLI registry for the `methods` list and pre-populate N rows.
- **Should the wizard support `$__gen_` placeholders?** A template is a different beast from a standard SLO — different save target (template vs. concrete), different validation rules. Current wizard doesn't distinguish. Either:
  - Split the wizard into "Create Standard SLO" and "Create Template" flows
  - Or keep one wizard and add a top-level "kind: standard | template" picker
- **Comparison config UI** needs to be reduced to the four real fields (`compare_with`, `include_result_with_score`, `number_of_comparison_results`, `aggregate_function`) plus `scope_tags` (now declared explicitly). Drop `baseline_mode`.

### 3.2 Level-2 method expansion in the generator — not implemented

**Original spec:** `docs/old-implemented/specs/2026-03-29-prometheus-sli-adapter-design.md:381-450`. Intended design: one template objective references an aggregated-mode SLI. The generator reads the SLI's `methods: [mean, p99, max]` and expands the single template objective into N concrete objectives — one per method. Per-method overrides come from a `method_criteria` dict on the template, keyed by method name.

**Example the spec envisioned** (contrast with §2.3 where the author does this by hand):

```yaml
spec:
  kind: template
  sli_name: process-cpu-agg
  objectives:
    - sli: process-cpu-agg   # unqualified — NO `.method` suffix
      pass_threshold: ["<25"]
      weight: 1
  method_criteria:
    mean:
      pass_threshold: ["<10"]
      weight: 1
    p99:
      pass_threshold: ["<25"]
      weight: 2
      key_sli: true
    max:
      pass_threshold: ["<40"]
      weight: 1
```

During generation, the single `process-cpu-agg` objective row fans out into three concrete rows, each picking up overrides from `method_criteria[<method>]` or falling back to the blueprint.

**Current implementation state:**

- Schema: `MethodCriteriaOverride` exists on `api/tropek/modules/slo_registry/schemas.py`. After commit `6ca3e1e` (2026-04-12) its fields mirror `SLOObjectiveIn`'s four override-capable fields (`pass_threshold`, `warning_threshold`, `weight`, `key_sli`) plus two adapter hints (`method`, `aggregation`) whose role is unclear (see below).
- Storage: `api/tropek/db/models.py:270` has a `method_criteria` JSONB column. Router serializes and persists; repository hydrates and returns. Storage path is complete.
- **Consumption: zero.** Grep confirms: no reference to `method_criteria` in `evaluation_engine/`, `slo_groups/generator.py`, `workflows/`, or anywhere else beyond storage. The generator's `_OBJ_KEYS` (line 50) does not include `method_criteria`. Level-2 expansion never runs.

**Open design questions that must be answered before implementing Level-2:**

1. **What is the dict key of `method_criteria`?**
   - Spec doc says method name (`mean`, `p99`, `max`). Clean if the single template objective's `sli` field is the base SLI name (unqualified), and the generator produces `{base_sli}.{method}` for each method. The `method` and `aggregation` value-fields are then redundant with the key — why are they there?
   - Alternative reading: dict key is an indicator/metric name, and `method`/`aggregation` inside the value describe adapter aggregation hints for *that* indicator. In this reading, `method_criteria` is not about method-level expansion at all — it's a per-indicator override map. But then the Level-2 expansion model doesn't apply.
   - Third reading: dict key is method name AND `method`/`aggregation` fields are about something completely different (e.g., how to aggregate baseline values for relative criteria evaluation, not how to aggregate raw samples). No evidence this interpretation was ever coded.
   - **Decision needed.** No code commits to an answer.

2. **What happens when the template's single objective uses a `sli` field that already has a `.method` suffix?** Error, or pass through as already-concrete?

3. **What happens when `method_criteria` references a method name that isn't in the SLI's `methods` list?** Error, warning, or silent ignore?

4. **What happens when an SLI has `methods` but the template has no `method_criteria` at all?** Blueprint expansion with identical settings per method, or require explicit method_criteria, or treat as a pre-§2.3 style manual listing?

5. **`weight` in the expanded world.** If the template says `weight: 1` and the expansion produces three objectives with `weight: 1` each, the total weight is 3× what a standalone single-objective SLO would be. Is that intended? Or should the blueprint weight be divided across methods? The spec doc is silent.

6. **Does `MethodCriteriaTable.tsx` in the wizard match option (a)/(b)/(c) above?** Currently it's designed around the spec's method-name-as-key model. If the generator goes a different direction, the table is wrong by construction.

### 3.3 `method_criteria.method` and `method_criteria.aggregation` — semantic drift

After commit `6ca3e1e`, `MethodCriteriaOverride` has six fields:

```python
class MethodCriteriaOverride(BaseModel):
    method: str | None = None
    aggregation: str | None = None
    pass_threshold: list[str] | None = None
    warning_threshold: list[str] | None = None
    weight: int | None = None
    key_sli: bool | None = None
```

`pass_threshold`, `warning_threshold`, `weight`, `key_sli` mirror `SLOObjectiveIn` and make sense as per-expansion overrides. `method` and `aggregation` are ambiguous:

- If dict-key interpretation #1 is right (key = method name), then the `method` value field is redundant.
- If dict-key interpretation #2 is right (key = indicator name), then `method`/`aggregation` might be adapter hints — but the Prometheus adapter currently takes aggregation method from the SLI definition's `methods` list, not from an SLO-side override.
- If these fields are vestigial from an earlier iteration and should be deleted, nothing in the codebase today depends on them.

**Decision needed before implementing Level-2:** keep both, drop one, drop both.

## 4. Why this document exists

The schema cleanup in commit `6ca3e1e` tightened `MethodCriteriaOverride` and `ComparisonConfig` without committing to a Level-2 expansion design. That means the generated OpenAPI schema is now honest about what the backend stores, but it's still storing data that no code reads. The UI wizard that's supposed to edit this data is partially broken and never end-to-end tested.

Two ways to resolve this over time:

**(A) Build Level-2 expansion and finish the wizard.** Full implementation of the spec: generator reads `method_criteria`, expands template objectives, produces concrete SLOs. Wizard is audited end-to-end against a real backend, `baseline_mode` phantom is removed, `MethodCriteriaTable` is either validated against the chosen dict-key interpretation or redesigned. Significant work — probably its own Chunk spec and plan.

**(B) Declare Level-2 out of scope and delete the dead storage.** Remove `method_criteria` column + schema + wizard UI entirely. Require template authors to hand-enumerate per-method objectives (the §2.3 path). Simpler codebase, smaller surface. Costs the ergonomic feature that aggregated-mode SLIs theoretically offer.

**No decision is being made in this document.** The point is that "do nothing" is not a neutral state — the dead storage and broken wizard actively mislead. Whoever picks this up next should pick (A) or (B) explicitly rather than leave the system in its current half-implemented state.

## 5. Follow-up prompts for when this comes back to the top of the stack

If you're a future Claude or a future human revisiting this:

1. Read §3.2 dict-key design questions. Pick an interpretation or propose a fourth. Write the decision into the spec doc (`docs/old-implemented/specs/2026-03-29-prometheus-sli-adapter-design.md` may no longer be the right home — create a new spec).
2. Audit the wizard against the chosen interpretation. Decide whether `MethodCriteriaTable.tsx` survives, gets rewritten, or gets deleted.
3. Test the wizard end-to-end against `just dev`. Create an SLO through the UI. Verify it appears in the backend with the shape you expected.
4. Decide on `baseline_mode` — it's gone from the UI as of the 2026-04-12 UI layering work. Don't bring it back without a real backend field to back it.
5. Write unit tests for the generator's Level-2 path BEFORE writing the implementation. TDD matters here; the feature is subtle.
6. Write e2e tests for SLO Groups + aggregated-mode SLIs + method_criteria. This is the intersection where bugs will hide.

## 6. Related files to read when picking this up

Backend:
- `api/tropek/modules/slo_registry/schemas.py` — post-`6ca3e1e` schemas
- `api/tropek/modules/slo_groups/generator.py` — current Level-1 generator
- `api/tropek/modules/slo_groups/router.py` — where the generator is invoked
- `api/tropek/modules/quality_gate/evaluation_engine/scoring.py` — how weight + key_sli are consumed at scoring time
- `api/tropek/modules/quality_gate/evaluation_engine/slo_models.py` — dataclasses for the runtime SLO model
- `api/tests/data/slo/*.yaml` — canonical YAML fixtures

UI:
- `ui/src/features/registry/forms/SloWizard.tsx` — the wizard scaffold
- `ui/src/features/registry/forms/WizardStepIndicators.tsx`
- `ui/src/features/registry/forms/WizardStepComparison.tsx`
- `ui/src/features/registry/forms/MethodCriteriaTable.tsx`

Docs:
- `docs/old-implemented/specs/2026-03-29-prometheus-sli-adapter-design.md` — original Level-2 spec (§5)
- `docs/old-implemented/plans/2026-03-30-aggregated-mode-e2e.md` — aggregated-mode rollout
- `api/docs/evaluation-engine.md` — evaluator semantics

## 7. Changelog

- **2026-04-12** — Document created during Chunk B1 (UI layering) after the layering refactor surfaced that `method_criteria` is dead storage and `baseline_mode` is a UI phantom. Backend schema cleanup landed as commit `6ca3e1e` on `feat/contract-testing-phase-1`. UI cleanup (delete `baseline_mode`, migrate slos to DTO/Domain/Mapper) is the next commit on the same branch.
