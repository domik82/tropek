# Quality Platform Phase 1 — Chunk 2: Evaluation Engine

> **For agentic workers:** Use superpowers:executing-plans to implement this chunk.
> **Depends on:** Chunk 1 (project scaffold)

**Goal:** Pure Python evaluation engine — SLO parser, criteria evaluator, weight-based scoring. Zero I/O. Fully tested.

**Architecture:** Four focused modules under `quality-gate-api/app/modules/quality_gate/engine/`. Each is a pure function. The top-level `evaluate()` call composes them.

---

## Chunk 2: Evaluation Engine

### Task 2.1: SLO Parser

**Files:**
- Create: `quality-gate-api/app/modules/__init__.py`
- Create: `quality-gate-api/app/modules/quality_gate/__init__.py`
- Create: `quality-gate-api/app/modules/quality_gate/engine/__init__.py`
- Create: `quality-gate-api/app/modules/quality_gate/engine/slo_parser.py`
- Create: `quality-gate-api/tests/engine/__init__.py`
- Create: `quality-gate-api/tests/engine/test_slo_parser.py`

- [ ] Write failing tests for SLO parser

```python
# tests/engine/test_slo_parser.py
import pytest
from app.modules.quality_gate.engine.slo_parser import parse_slo, SLOParseError

MINIMAL_SLO = """
spec_version: '1.0'
indicators:
  response_time_p99: 'avg_over_time(http_duration_seconds[5m])'
objectives:
  - sli: response_time_p99
    pass:
      - criteria: ["<600"]
    weight: 1
total_score:
  pass: "90%"
  warning: "75%"
"""

RELATIVE_SLO = """
spec_version: '1.0'
comparison:
  compare_with: several_results
  number_of_comparison_results: 3
  include_result_with_score: pass_or_warn
  aggregate_function: avg
  scope_tags:
    - os
    - arch
indicators:
  cpu_usage: 'avg_over_time(cpu[5m])'
objectives:
  - sli: cpu_usage
    pass:
      - criteria: ["<=+10%"]
    warning:
      - criteria: ["<=+20%"]
    weight: 2
    key_sli: true
total_score:
  pass: "90%"
  warning: "75%"
"""


def test_parse_minimal_slo() -> None:
    slo = parse_slo(MINIMAL_SLO)
    assert slo.spec_version == "1.0"
    assert len(slo.objectives) == 1
    assert slo.objectives[0].sli == "response_time_p99"
    assert slo.objectives[0].weight == 1
    assert slo.objectives[0].key_sli is False
    assert slo.total_score.pass_threshold == 90.0
    assert slo.total_score.warning_threshold == 75.0


def test_parse_indicators_block() -> None:
    slo = parse_slo(MINIMAL_SLO)
    assert "response_time_p99" in slo.indicators
    assert slo.indicators["response_time_p99"] == "avg_over_time(http_duration_seconds[5m])"


def test_parse_comparison_defaults() -> None:
    """Minimal SLO without comparison block gets defaults."""
    slo = parse_slo(MINIMAL_SLO)
    assert slo.comparison.compare_with == "single_result"
    assert slo.comparison.number_of_comparison_results == 3
    assert slo.comparison.include_result_with_score == "all"
    assert slo.comparison.aggregate_function == "avg"
    assert slo.comparison.scope_tags == ["os"]


def test_parse_relative_slo_comparison() -> None:
    slo = parse_slo(RELATIVE_SLO)
    assert slo.comparison.compare_with == "several_results"
    assert slo.comparison.scope_tags == ["os", "arch"]


def test_parse_key_sli() -> None:
    slo = parse_slo(RELATIVE_SLO)
    assert slo.objectives[0].key_sli is True


def test_parse_weight_default() -> None:
    """Objectives without explicit weight default to 1."""
    yaml = """
spec_version: '1.0'
indicators:
  m: 'query()'
objectives:
  - sli: m
    pass:
      - criteria: ["<100"]
total_score:
  pass: "90%"
  warning: "75%"
"""
    slo = parse_slo(yaml)
    assert slo.objectives[0].weight == 1


def test_missing_spec_version_raises() -> None:
    bad = "objectives:\n  - sli: m\n"
    with pytest.raises(SLOParseError, match="spec_version"):
        parse_slo(bad)


def test_objective_references_missing_indicator_raises() -> None:
    bad = """
spec_version: '1.0'
indicators:
  other: 'query()'
objectives:
  - sli: nonexistent
    pass:
      - criteria: ["<100"]
total_score:
  pass: "90%"
  warning: "75%"
"""
    with pytest.raises(SLOParseError, match="nonexistent"):
        parse_slo(bad)


def test_change_point_detection_field_ignored() -> None:
    """change_point_detection is reserved but accepted without error."""
    yaml = """
spec_version: '1.0'
indicators:
  m: 'query()'
objectives:
  - sli: m
    pass:
      - criteria: ["<100"]
    change_point_detection:
      enabled: true
      algorithm: otava
total_score:
  pass: "90%"
  warning: "75%"
"""
    slo = parse_slo(yaml)  # must not raise
    assert slo.objectives[0].sli == "m"
```

- [ ] Run — expect failures

```bash
cd quality-gate-api
uv run pytest tests/engine/test_slo_parser.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'app.modules'`

- [ ] Implement `slo_parser.py`

```python
# app/modules/quality_gate/engine/slo_parser.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml


class SLOParseError(ValueError):
    pass


@dataclass
class SLOCriteria:
    criteria: list[str]


@dataclass
class SLOObjective:
    sli: str
    display_name: str = ""
    pass_threshold: list[SLOCriteria] = field(default_factory=list)
    warning_threshold: list[SLOCriteria] = field(default_factory=list)
    weight: int = 1
    key_sli: bool = False


@dataclass
class SLOComparison:
    compare_with: str = "single_result"
    number_of_comparison_results: int = 3
    include_result_with_score: str = "all"
    aggregate_function: str = "avg"
    scope_tags: list[str] = field(default_factory=lambda: ["os"])


@dataclass
class SLOTotalScore:
    pass_pct: float = 90.0
    warning_pct: float = 75.0


@dataclass
class SLO:
    spec_version: str
    indicators: dict[str, str]
    objectives: list[SLOObjective]
    comparison: SLOComparison
    total_score: SLOTotalScore


def _parse_pct(value: str) -> float:
    return float(value.strip().rstrip("%"))


def parse_slo(yaml_text: str) -> SLO:
    try:
        data: dict[str, Any] = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError as e:
        raise SLOParseError(f"Invalid YAML: {e}") from e

    if "spec_version" not in data:
        raise SLOParseError("Missing required field: spec_version")

    indicators: dict[str, str] = {
        str(k): str(v) for k, v in (data.get("indicators") or {}).items()
    }

    raw_cmp = data.get("comparison") or {}
    comparison = SLOComparison(
        compare_with=raw_cmp.get("compare_with", "single_result"),
        number_of_comparison_results=int(raw_cmp.get("number_of_comparison_results", 3)),
        include_result_with_score=raw_cmp.get("include_result_with_score", "all"),
        aggregate_function=raw_cmp.get("aggregate_function", "avg"),
        scope_tags=list(raw_cmp.get("scope_tags", ["os"])),
    )

    raw_score = data.get("total_score") or {}
    total_score = SLOTotalScore(
        pass_pct=_parse_pct(str(raw_score.get("pass", "90%"))),
        warning_pct=_parse_pct(str(raw_score.get("warning", "75%"))),
    )

    objectives: list[SLOObjective] = []
    for raw_obj in data.get("objectives") or []:
        sli_name = str(raw_obj.get("sli", ""))
        if sli_name not in indicators:
            raise SLOParseError(
                f"Objective references unknown indicator: {sli_name!r}. "
                f"Available: {list(indicators)}"
            )

        pass_threshold = [
            SLOCriteria(criteria=list(block.get("criteria", [])))
            for block in (raw_obj.get("pass") or [])
        ]
        warning_threshold = [
            SLOCriteria(criteria=list(block.get("criteria", [])))
            for block in (raw_obj.get("warning") or [])
        ]

        objectives.append(SLOObjective(
            sli=sli_name,
            display_name=str(raw_obj.get("displayName", sli_name)),
            pass_threshold=pass_threshold,
            warning_threshold=warning_threshold,
            weight=int(raw_obj.get("weight", 1)),
            key_sli=bool(raw_obj.get("key_sli", False)),
        ))

    return SLO(
        spec_version=str(data["spec_version"]),
        indicators=indicators,
        objectives=objectives,
        comparison=comparison,
        total_score=total_score,
    )
```

- [ ] Create `__init__.py` files

```bash
touch app/modules/__init__.py
touch app/modules/quality_gate/__init__.py
touch app/modules/quality_gate/engine/__init__.py
touch tests/engine/__init__.py
```

- [ ] Run tests — expect pass

```bash
uv run pytest tests/engine/test_slo_parser.py -v
```

Expected: all 9 tests PASSED.

- [ ] Run mypy + ruff

```bash
uv run mypy app/modules/quality_gate/engine/slo_parser.py
uv run ruff check app/modules/quality_gate/engine/slo_parser.py
```

- [ ] Commit

```bash
git add .
git commit -m "feat: SLO parser with validation and defaults"
```

---

### Task 2.2: Criteria Evaluator

**Files:**
- Create: `quality-gate-api/app/modules/quality_gate/engine/criteria.py`
- Create: `quality-gate-api/tests/engine/test_criteria.py`

- [ ] Write failing tests

```python
# tests/engine/test_criteria.py
import pytest
from app.modules.quality_gate.engine.criteria import (
    parse_criteria_string,
    evaluate_criteria,
    CriteriaType,
    ParsedCriteria,
)


# --- parse_criteria_string ---

def test_parse_fixed_lt() -> None:
    c = parse_criteria_string("<600")
    assert c.operator == "<"
    assert c.type == CriteriaType.FIXED
    assert c.threshold == 600.0


def test_parse_fixed_lte() -> None:
    c = parse_criteria_string("<=500")
    assert c.operator == "<="
    assert c.threshold == 500.0


def test_parse_fixed_eq() -> None:
    c = parse_criteria_string("=0")
    assert c.operator == "="
    assert c.threshold == 0.0


def test_parse_fixed_gte() -> None:
    c = parse_criteria_string(">=10")
    assert c.operator == ">="
    assert c.threshold == 10.0


def test_parse_relative_plus_pct() -> None:
    c = parse_criteria_string("<=+10%")
    assert c.type == CriteriaType.RELATIVE
    assert c.operator == "<="
    assert c.relative_pct == 10.0
    assert c.relative_direction == "+"


def test_parse_relative_minus_pct() -> None:
    c = parse_criteria_string(">=-5%")
    assert c.type == CriteriaType.RELATIVE
    assert c.relative_pct == 5.0
    assert c.relative_direction == "-"


def test_parse_relative_no_sign_defaults_plus() -> None:
    c = parse_criteria_string("<=10%")
    assert c.type == CriteriaType.RELATIVE
    assert c.relative_direction == "+"


def test_invalid_criteria_raises() -> None:
    with pytest.raises(ValueError, match="Cannot parse"):
        parse_criteria_string("?????")


# --- evaluate_criteria (fixed) ---

def test_fixed_lt_pass() -> None:
    c = parse_criteria_string("<600")
    assert evaluate_criteria(c, value=550.0, baseline=None) is True


def test_fixed_lt_fail() -> None:
    c = parse_criteria_string("<600")
    assert evaluate_criteria(c, value=600.0, baseline=None) is False


def test_fixed_lte_pass_equal() -> None:
    c = parse_criteria_string("<=600")
    assert evaluate_criteria(c, value=600.0, baseline=None) is True


def test_fixed_eq_pass() -> None:
    c = parse_criteria_string("=0")
    assert evaluate_criteria(c, value=0.0, baseline=None) is True


def test_fixed_eq_fail() -> None:
    c = parse_criteria_string("=0")
    assert evaluate_criteria(c, value=1.0, baseline=None) is False


# --- evaluate_criteria (relative) ---

def test_relative_plus_within_threshold() -> None:
    # value 110, baseline 100, +10% → 110 <= 110 → pass
    c = parse_criteria_string("<=+10%")
    assert evaluate_criteria(c, value=110.0, baseline=100.0) is True


def test_relative_plus_exceeds_threshold() -> None:
    # value 111, baseline 100, +10% → 111 > 110 → fail
    c = parse_criteria_string("<=+10%")
    assert evaluate_criteria(c, value=111.0, baseline=100.0) is False


def test_relative_minus_pct() -> None:
    # value 92, baseline 100, >=-10% → threshold=90, 92 >= 90 → pass
    c = parse_criteria_string(">=-10%")
    assert evaluate_criteria(c, value=92.0, baseline=100.0) is True


def test_relative_no_baseline_passes() -> None:
    """When no baseline available, relative criteria always pass (no history yet)."""
    c = parse_criteria_string("<=+10%")
    assert evaluate_criteria(c, value=999.0, baseline=None) is True


def test_compute_target_value_fixed() -> None:
    c = parse_criteria_string("<600")
    assert c.compute_target_value(baseline=None) == 600.0


def test_compute_target_value_relative() -> None:
    c = parse_criteria_string("<=+10%")
    assert c.compute_target_value(baseline=100.0) == 110.0
```

- [ ] Run — expect failures

```bash
uv run pytest tests/engine/test_criteria.py -v 2>&1 | head -5
```

- [ ] Implement `criteria.py`

```python
# app/modules/quality_gate/engine/criteria.py
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class CriteriaType(Enum):
    FIXED = "fixed"
    RELATIVE = "relative"


@dataclass
class ParsedCriteria:
    raw: str
    operator: str
    type: CriteriaType
    threshold: float = 0.0          # for FIXED
    relative_pct: float = 0.0       # for RELATIVE
    relative_direction: str = "+"   # "+" or "-"

    def compute_target_value(self, baseline: float | None) -> float:
        if self.type == CriteriaType.FIXED:
            return self.threshold
        if baseline is None:
            return 0.0
        delta = baseline * (self.relative_pct / 100.0)
        if self.relative_direction == "+":
            return baseline + delta
        return baseline - delta


_PATTERN = re.compile(
    r"^(?P<op><=|>=|<|>|=)"
    r"(?P<sign>[+-])?"
    r"(?P<value>\d+(?:\.\d+)?)"
    r"(?P<pct>%)?"
    r"$"
)


def parse_criteria_string(raw: str) -> ParsedCriteria:
    raw = raw.strip()
    m = _PATTERN.match(raw)
    if not m:
        raise ValueError(f"Cannot parse criteria string: {raw!r}")

    op = m.group("op")
    sign = m.group("sign")
    value = float(m.group("value"))
    is_pct = m.group("pct") is not None

    if is_pct:
        return ParsedCriteria(
            raw=raw,
            operator=op,
            type=CriteriaType.RELATIVE,
            relative_pct=value,
            relative_direction=sign or "+",
        )
    return ParsedCriteria(
        raw=raw,
        operator=op,
        type=CriteriaType.FIXED,
        threshold=value,
    )


def _compare(operator: str, value: float, target: float) -> bool:
    match operator:
        case "<":  return value < target
        case "<=": return value <= target
        case ">":  return value > target
        case ">=": return value >= target
        case "=":  return value == target
        case _:    return False


def evaluate_criteria(
    criteria: ParsedCriteria,
    value: float,
    baseline: float | None,
) -> bool:
    if criteria.type == CriteriaType.RELATIVE and baseline is None:
        return True  # no history — skip, do not penalise
    target = criteria.compute_target_value(baseline)
    return _compare(criteria.operator, value, target)
```

- [ ] Run tests — expect all pass

```bash
uv run pytest tests/engine/test_criteria.py -v
```

- [ ] Commit

```bash
git add .
git commit -m "feat: criteria parser and evaluator with relative and fixed threshold support"
```

---

### Task 2.3: Scoring Engine

**Files:**
- Create: `quality-gate-api/app/modules/quality_gate/engine/scoring.py`
- Create: `quality-gate-api/tests/engine/test_scoring.py`

- [ ] Write failing tests

```python
# tests/engine/test_scoring.py
from app.modules.quality_gate.engine.slo_parser import parse_slo
from app.modules.quality_gate.engine.scoring import (
    score_objective,
    calculate_total_score,
    IndicatorStatus,
    ObjectiveResult,
)


SIMPLE_SLO = """
spec_version: '1.0'
indicators:
  m1: 'q()'
  m2: 'q()'
  m3: 'q()'
objectives:
  - sli: m1
    pass:
      - criteria: ["<100"]
    warning:
      - criteria: ["<200"]
    weight: 2
    key_sli: false
  - sli: m2
    pass:
      - criteria: ["<50"]
    weight: 1
    key_sli: true
  - sli: m3
    displayName: Info only
    weight: 1
total_score:
  pass: "90%"
  warning: "75%"
"""


def _slo():
    return parse_slo(SIMPLE_SLO)


def test_objective_passes() -> None:
    slo = _slo()
    result = score_objective(slo.objectives[0], value=80.0, baseline=None)
    assert result.status == IndicatorStatus.PASS
    assert result.score == 2.0


def test_objective_warns() -> None:
    slo = _slo()
    result = score_objective(slo.objectives[0], value=150.0, baseline=None)
    assert result.status == IndicatorStatus.WARNING
    assert result.score == 1.0  # 0.5 * weight(2)


def test_objective_fails() -> None:
    slo = _slo()
    result = score_objective(slo.objectives[0], value=250.0, baseline=None)
    assert result.status == IndicatorStatus.FAIL
    assert result.score == 0.0


def test_objective_missing_metric_fails() -> None:
    slo = _slo()
    result = score_objective(slo.objectives[0], value=None, baseline=None)
    assert result.status == IndicatorStatus.FAIL
    assert result.score == 0.0


def test_objective_no_pass_threshold_is_informational() -> None:
    """m3 has no pass criteria — contributes 0 to maximum_achievable_score."""
    slo = _slo()
    result = score_objective(slo.objectives[2], value=999.0, baseline=None)
    assert result.status == IndicatorStatus.INFO
    assert result.score == 0.0
    assert result.contributes_to_score is False


def test_or_criteria_one_set_passes() -> None:
    """Two pass blocks (OR logic) — second block alone passes."""
    slo = parse_slo("""
spec_version: '1.0'
indicators:
  m: 'q()'
objectives:
  - sli: m
    pass:
      - criteria: ["<50", "<30"]
      - criteria: ["<200"]
    weight: 1
total_score:
  pass: "90%"
  warning: "75%"
""")
    result = score_objective(slo.objectives[0], value=100.0, baseline=None)
    assert result.status == IndicatorStatus.PASS  # second block (<200) passes


def test_key_sli_failure_flagged() -> None:
    slo = _slo()
    result = score_objective(slo.objectives[1], value=999.0, baseline=None)
    assert result.status == IndicatorStatus.FAIL
    assert result.key_sli_failed is True


# --- calculate_total_score ---

def test_total_score_all_pass() -> None:
    slo = _slo()
    results = [
        ObjectiveResult(slo.objectives[0], IndicatorStatus.PASS, 2.0, False, False),
        ObjectiveResult(slo.objectives[1], IndicatorStatus.PASS, 1.0, True, False),
        ObjectiveResult(slo.objectives[2], IndicatorStatus.INFO, 0.0, False, False),
    ]
    total = calculate_total_score(results, slo.total_score)
    assert total.result == "pass"
    assert total.score == 100.0


def test_total_score_key_sli_fails_regardless() -> None:
    slo = _slo()
    results = [
        ObjectiveResult(slo.objectives[0], IndicatorStatus.PASS, 2.0, False, False),
        ObjectiveResult(slo.objectives[1], IndicatorStatus.FAIL, 0.0, True, True),
        ObjectiveResult(slo.objectives[2], IndicatorStatus.INFO, 0.0, False, False),
    ]
    total = calculate_total_score(results, slo.total_score)
    assert total.result == "fail"


def test_total_score_no_pass_threshold_returns_pass() -> None:
    """If maximum_achievable_score == 0, return pass at 100%."""
    slo = parse_slo("""
spec_version: '1.0'
indicators:
  m: 'q()'
objectives:
  - sli: m
    weight: 1
total_score:
  pass: "90%"
  warning: "75%"
""")
    results = [
        ObjectiveResult(slo.objectives[0], IndicatorStatus.INFO, 0.0, False, False),
    ]
    total = calculate_total_score(results, slo.total_score)
    assert total.result == "pass"
    assert total.score == 100.0


def test_total_score_warning_band() -> None:
    slo = _slo()
    # achieved = 1/3 = 33% — below 75% warning threshold
    results = [
        ObjectiveResult(slo.objectives[0], IndicatorStatus.FAIL, 0.0, False, False),
        ObjectiveResult(slo.objectives[1], IndicatorStatus.PASS, 1.0, True, False),
        ObjectiveResult(slo.objectives[2], IndicatorStatus.INFO, 0.0, False, False),
    ]
    total = calculate_total_score(results, slo.total_score)
    # max=3, achieved=1 → 33% → fail
    assert total.result == "fail"
```

- [ ] Implement `scoring.py`

```python
# app/modules/quality_gate/engine/scoring.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from app.modules.quality_gate.engine.criteria import evaluate_criteria, parse_criteria_string
from app.modules.quality_gate.engine.slo_parser import SLOObjective, SLOTotalScore

if TYPE_CHECKING:
    pass


class IndicatorStatus(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    INFO = "info"
    ERROR = "error"


@dataclass
class ObjectiveResult:
    objective: SLOObjective
    status: IndicatorStatus
    score: float
    contributes_to_score: bool
    key_sli_failed: bool


@dataclass
class TotalScore:
    result: str  # pass | warning | fail
    score: float  # 0–100


def _evaluate_criteria_block(
        criteria_list: list[str],
        value: float,
        baseline: float | None,
) -> bool:
    """AND logic: all criteria in the block must pass."""
    for raw in criteria_list:
        c = parse_criteria_string(raw)
        if not evaluate_criteria(c, value, baseline):
            return False
    return True


def _evaluate_pass_or_warning(
        criteria_blocks: list,  # list of SLOCriteria
        value: float,
        baseline: float | None,
) -> bool:
    """OR logic across blocks: any block passing means overall pass."""
    if not criteria_blocks:
        return False
    return any(
        _evaluate_criteria_block(block.criteria, value, baseline)
        for block in criteria_blocks
    )


def score_objective(
        objective: SLOObjective,
        value: float | None,
        baseline: float | None,
) -> ObjectiveResult:
    has_pass = bool(objective.pass_threshold)
    contributes = has_pass

    if not has_pass:
        return ObjectiveResult(objective, IndicatorStatus.INFO, 0.0, False, False)

    if value is None:
        return ObjectiveResult(
            objective, IndicatorStatus.FAIL, 0.0, contributes,
            objective.key_sli,
        )

    if _evaluate_pass_or_warning(objective.pass_threshold, value, baseline):
        return ObjectiveResult(
            objective, IndicatorStatus.PASS, float(objective.weight), contributes, False,
        )

    if _evaluate_pass_or_warning(objective.warning_threshold, value, baseline):
        return ObjectiveResult(
            objective, IndicatorStatus.WARNING, 0.5 * objective.weight, contributes, False,
        )

    return ObjectiveResult(
        objective, IndicatorStatus.FAIL, 0.0, contributes,
        objective.key_sli,
    )


def calculate_total_score(
        results: list[ObjectiveResult],
        total_score: SLOTotalScore,
) -> TotalScore:
    maximum = sum(r.objective.weight for r in results if r.contributes_to_score)
    if maximum == 0:
        return TotalScore(result="pass", score=100.0)

    achieved = sum(r.score for r in results)
    pct = 100.0 * achieved / maximum

    key_sli_failed = any(r.key_sli_failed for r in results)
    if key_sli_failed:
        return TotalScore(result="fail", score=pct)
    if pct >= total_score.pass_threshold:
        return TotalScore(result="pass", score=pct)
    if pct >= total_score.warning_threshold:
        return TotalScore(result="warning", score=pct)
    return TotalScore(result="fail", score=pct)
```

- [ ] Run tests — expect all pass

```bash
uv run pytest tests/engine/test_scoring.py -v
```

- [ ] Commit

```bash
git add .
git commit -m "feat: weight-based scoring engine with key_sli veto"
```

---

### Task 2.4: Top-Level Evaluator

**Files:**
- Create: `quality-gate-api/app/modules/quality_gate/engine/evaluator.py`
- Create: `quality-gate-api/tests/engine/test_evaluator.py`

- [ ] Write failing tests

```python
# tests/engine/test_evaluator.py
from app.modules.quality_gate.engine.evaluator import evaluate, EvaluationResult


SLO_YAML = """
spec_version: '1.0'
comparison:
  compare_with: several_results
  number_of_comparison_results: 3
  include_result_with_score: pass_or_warn
  aggregate_function: avg
  scope_tags: [os]
indicators:
  response_time_p99: 'query()'
  error_rate: 'query()'
  compilation_s: 'query()'
objectives:
  - sli: response_time_p99
    pass:
      - criteria: ["<600", "<=+10%"]
    warning:
      - criteria: ["<800"]
    weight: 2
    key_sli: false
  - sli: error_rate
    pass:
      - criteria: ["=0"]
    weight: 3
    key_sli: true
  - sli: compilation_s
    pass:
      - criteria: ["<=+5%"]
    weight: 1
total_score:
  pass: "90%"
  warning: "75%"
"""


def test_evaluate_all_pass_no_baseline() -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 0.0, "compilation_s": 45.0}
    result = evaluate(SLO_YAML, metrics, baselines={})
    assert result.result == "pass"
    assert result.score > 0


def test_evaluate_key_sli_fails_entire_evaluation() -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 1.0, "compilation_s": 45.0}
    result = evaluate(SLO_YAML, metrics, baselines={})
    assert result.result == "fail"


def test_evaluate_missing_metric_fails_objective() -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 0.0}
    # compilation_s missing — fails objective but not key_sli
    result = evaluate(SLO_YAML, metrics, baselines={})
    # max=6, achieved=5 (2+3) → 83% → below 90% pass → fail
    assert result.result in ("fail", "warning")


def test_evaluate_relative_criteria_with_baseline() -> None:
    metrics = {"response_time_p99": 605.0, "error_rate": 0.0, "compilation_s": 45.0}
    baselines = {"response_time_p99": 550.0}  # +10% = 605 exactly → pass
    result = evaluate(SLO_YAML, metrics, baselines=baselines)
    assert result.indicator_results[0]["status"] == "pass"


def test_evaluate_relative_criteria_exceeded() -> None:
    metrics = {"response_time_p99": 700.0, "error_rate": 0.0, "compilation_s": 45.0}
    baselines = {"response_time_p99": 550.0}  # +10% = 605, 700 > 605 → fail pass, try warning <800
    result = evaluate(SLO_YAML, metrics, baselines=baselines)
    assert result.indicator_results[0]["status"] == "warning"


def test_evaluate_returns_indicator_results() -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 0.0, "compilation_s": 45.0}
    result = evaluate(SLO_YAML, metrics, baselines={})
    assert len(result.indicator_results) == 3
    names = {r["metric"] for r in result.indicator_results}
    assert names == {"response_time_p99", "error_rate", "compilation_s"}


def test_evaluate_includes_target_values() -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 0.0, "compilation_s": 45.0}
    result = evaluate(SLO_YAML, metrics, baselines={"response_time_p99": 500.0})
    rt = next(r for r in result.indicator_results if r["metric"] == "response_time_p99")
    # fixed target <600 and relative <=+10% (550) — both in pass_targets
    assert any(t["criteria"] == "<600" for t in rt["pass_targets"])
```

- [ ] Implement `evaluator.py`

```python
# app/modules/quality_gate/engine/evaluator.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.modules.quality_gate.engine.criteria import (
    ParsedCriteria,
    evaluate_criteria,
    parse_criteria_string,
)
from app.modules.quality_gate.engine.scoring import (
    ObjectiveResult,
    TotalScore,
    calculate_total_score,
    score_objective,
)
from app.modules.quality_gate.engine.slo_parser import SLOObjective, parse_slo


@dataclass
class EvaluationResult:
    result: str          # pass | warning | fail
    score: float
    indicator_results: list[dict[str, Any]] = field(default_factory=list)
    compared_evaluation_ids: list[str] = field(default_factory=list)


def _build_targets(
    objective: SLOObjective,
    value: float | None,
    baseline: float | None,
    is_pass: bool,
) -> list[dict[str, Any]]:
    blocks = objective.pass_threshold if is_pass else objective.warning_threshold
    targets = []
    for block in blocks:
        for raw in block.criteria:
            c: ParsedCriteria = parse_criteria_string(raw)
            target_value = c.compute_target_value(baseline)
            violated = not evaluate_criteria(c, value or 0.0, baseline) if value is not None else True
            targets.append({
                "criteria": raw,
                "target_value": target_value,
                "violated": violated,
            })
    return targets


def evaluate(
    slo_yaml: str,
    metrics: dict[str, float | None],
    baselines: dict[str, float | None],
    compared_evaluation_ids: list[str] | None = None,
) -> EvaluationResult:
    slo = parse_slo(slo_yaml)
    objective_results: list[ObjectiveResult] = []
    indicator_results: list[dict[str, Any]] = []

    for obj in slo.objectives:
        value = metrics.get(obj.sli)
        baseline = baselines.get(obj.sli)
        obj_result = score_objective(obj, value, baseline)
        objective_results.append(obj_result)

        pass_targets = _build_targets(obj, value, baseline, is_pass=True)
        warning_targets = _build_targets(obj, value, baseline, is_pass=False)

        ir: dict[str, Any] = {
            "metric": obj.sli,
            "display_name": obj.display_name,
            "value": value,
            "compared_value": baseline,
            "status": obj_result.status.value,
            "score": obj_result.score,
            "weight": obj.weight,
            "key_sli": obj.key_sli,
            "pass_targets": pass_targets,
            "warning_targets": warning_targets if obj.warning_threshold else None,
        }
        if value is not None and baseline is not None:
            ir["change_absolute"] = value - baseline
            ir["change_relative_pct"] = ((value / baseline) - 1) * 100 if baseline != 0 else None
        indicator_results.append(ir)

    total: TotalScore = calculate_total_score(objective_results, slo.total_score)

    return EvaluationResult(
        result=total.result,
        score=round(total.score, 2),
        indicator_results=indicator_results,
        compared_evaluation_ids=compared_evaluation_ids or [],
    )
```

- [ ] Run all engine tests

```bash
uv run pytest tests/engine/ -v
```

Expected: all tests PASSED.

- [ ] Run full type-check

```bash
uv run mypy app/modules/quality_gate/engine/
```

Expected: `Success: no issues found`

- [ ] Commit

```bash
git add .
git commit -m "feat: top-level evaluate() function with indicator results and target values"
```

---

### Task 2.5: Variable Substitution

**Files:**
- Create: `quality-gate-api/app/modules/quality_gate/engine/variables.py`
- Create: `quality-gate-api/tests/engine/test_variables.py`

- [ ] Write failing tests

```python
# tests/engine/test_variables.py
import pytest
from app.modules.quality_gate.engine.variables import substitute_variables, UnresolvedVariableError


def test_substitutes_single_variable() -> None:
    result = substitute_variables(
        "cpu{instance=\"$vm_ip\"}", {"vm_ip": "10.0.0.1"}
    )
    assert result == 'cpu{instance="10.0.0.1"}'


def test_substitutes_reserved_vars() -> None:
    result = substitute_variables(
        "metric{job=\"$test_name\"}", {"test_name": "compile-test"}
    )
    assert result == 'metric{job="compile-test"}'


def test_substitutes_multiple_vars() -> None:
    tmpl = "query{os=\"$os\", arch=\"$arch\"}"
    result = substitute_variables(tmpl, {"os": "windows-11", "arch": "x64"})
    assert result == 'query{os="windows-11", arch="x64"}'


def test_unresolved_variable_raises() -> None:
    with pytest.raises(UnresolvedVariableError) as exc_info:
        substitute_variables("cpu{instance=\"$vm_ip\"}", {})
    assert "vm_ip" in str(exc_info.value)


def test_substitute_slo_indicators_block() -> None:
    """substitute_slo_variables returns new SLO yaml with vars replaced."""
    from app.modules.quality_gate.engine.variables import substitute_slo_variables
    slo_yaml = """
spec_version: '1.0'
indicators:
  cpu: 'avg_over_time(cpu{instance="$vm_ip"}[5m])'
objectives:
  - sli: cpu
    pass:
      - criteria: ["<90"]
    weight: 1
total_score:
  pass: "90%"
  warning: "75%"
"""
    result = substitute_slo_variables(slo_yaml, {"vm_ip": "10.0.0.5"})
    assert "$vm_ip" not in result
    assert "10.0.0.5" in result
```

- [ ] Implement `variables.py`

```python
# app/modules/quality_gate/engine/variables.py
from __future__ import annotations

import re


class UnresolvedVariableError(ValueError):
    pass


_VAR_RE = re.compile(r"\$([a-zA-Z_][a-zA-Z0-9_]*)")


def substitute_variables(template: str, variables: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in variables:
            raise UnresolvedVariableError(
                f"Unresolved variable '${name}' in template. "
                f"Available: {sorted(variables)}"
            )
        return variables[name]
    return _VAR_RE.sub(replace, template)


def substitute_slo_variables(slo_yaml: str, variables: dict[str, str]) -> str:
    """Substitute $variables in the full SLO YAML text.

    Raises UnresolvedVariableError if any $var remains after substitution.
    """
    return substitute_variables(slo_yaml, variables)


def build_variables(
    metadata: dict[str, str],
    asset_name: str | None = None,
    test_name: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, str]:
    """Merge all variable sources into a single dict."""
    vars_: dict[str, str] = dict(metadata)
    if asset_name:
        vars_.setdefault("asset_name", asset_name)
    if test_name:
        vars_.setdefault("test_name", test_name)
    if start:
        vars_.setdefault("start", start)
    if end:
        vars_.setdefault("end", end)
    if "ip" in vars_:
        vars_.setdefault("asset_ip", vars_["ip"])
    return vars_
```

- [ ] Run all engine tests

```bash
uv run pytest tests/engine/ -v
```

Expected: all pass.

- [ ] Commit

```bash
git add .
git commit -m "feat: SLO variable substitution with unresolved variable detection"
```
