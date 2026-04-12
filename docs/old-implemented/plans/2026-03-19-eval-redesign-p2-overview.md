# Evaluation Redesign P2 — Comparison Rules Overview

## Context

P0 and P1 are merged to main. P0 rewrote `get_baselines()` to scope by `asset_id + slo_name` with a `period_start` guard, added `tag_filters` and `sli_version_range` parameters. P1 added the re-evaluation engine, `comparable_from_version`, and evaluation tag merging. The `tag_filters` parameter on `get_baselines()` exists but nothing populates it yet — that's P2's job.

**Spec:** `docs/superpowers/specs/2026-03-18-evaluation-redesign-design.md` (Change 4)

---

## P2a — Data Model + CRUD + Validation

**Plan:** `docs/superpowers/plans/2026-03-19-eval-redesign-p2a.md`

**Scope:** Everything needed to store, validate, and manage comparison rules — but NOT use them during evaluation.

| What | Details |
|------|---------|
| `comparison_rules` JSONB column | On `AssetSLOLink`, default `[]`, with Alembic migration |
| Pydantic validation | `ComparisonRule` model, `validate_comparison_rules()` enforcing catch-all-must-be-last, at-most-one-catch-all |
| Repository methods | `get_by_link_name(asset_id, link_name)` for CRUD endpoints, `get_by_asset_and_slo(asset_id, slo_name)` for evaluation flow, `update_comparison_rules(link_id, rules)` |
| API endpoints | `GET /assets/{name}/slo-links/{link_name}/comparison-rules`, `PUT /assets/{name}/slo-links/{link_name}/comparison-rules` with 422 on invalid rules |
| Tests | 9 unit tests (validation), 7 integration tests (repository CRUD) |

**Does NOT touch:** worker.py, re_evaluator.py, trigger.py, evaluation flow, `get_baselines()` callers.

---

## P2b — Rule Resolution Engine + Evaluation Flow Wiring

**Plan:** Not yet written.

**Scope:** Everything needed to actually USE comparison rules during evaluation.

| What | Details |
|------|---------|
| Rule resolution function | `resolve_comparison_rule(rules, evaluation_metadata)` — walks rules in order, matches current eval tags against `match` conditions (exact match + `!` negation), returns the first matching rule's `compare_to` as `tag_filters` |
| Worker wiring | In `_resolve_baselines()` (`worker.py:92-133`): load `AssetSLOLink` via `get_by_asset_and_slo(ev.asset_id, ev.slo_name)`, resolve rule, pass `tag_filters` to `get_baselines()` |
| Re-evaluator wiring | Same pattern in `re_evaluator.py` for both baseline calls |
| Rule override via API | Optional `comparison_rule` field on `POST /evaluations` trigger request, overrides stored rules for that evaluation only |
| Audit trail | Store `_applied_comparison_rule` in `evaluation_metadata` (source, rule_index, match, compare_to) |
| `pinned` handling in compare_to | When `compare_to` contains `{"pinned": true}`, integrate with existing `baseline_pinned_at` logic |
| Tests | Unit tests for rule matching (exact, negation, catch-all, no-match-falls-through), integration tests for end-to-end evaluation with rules |

**Key files:** `worker.py:92-133` (`_resolve_baselines`), `trigger.py` (TriggerContext), `re_evaluator.py`, `quality_gate/router.py` (trigger endpoint), `quality_gate/schemas.py` (TriggerRequest)

---

## P3 (deferred, for reference)

- Prefix glob matching in rules (`"branch": "release-*"`)
- UI rule editor component
- Re-evaluation with explicit `slo_version` parameter (end-to-end)
