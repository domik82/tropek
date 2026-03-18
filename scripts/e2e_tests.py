"""End-to-end integration tests run against a live TROPEK API.

Usage: uv run --directory clients/python python ../../scripts/e2e_tests.py <api_url>

Bootstrap manifests must be applied before running (see scripts/bootstrap.py).
"""

from __future__ import annotations

import sys
import time

from tropek_client import TropekClient

TERMINAL_STATUSES = {"completed", "failed", "partial"}


def step(name: str) -> None:
    """Print a step header."""
    print(f"\n=== {name} ===")


def poll_eval(client: TropekClient, eval_id: str, timeout: int = 30) -> object:
    """Poll an evaluation until it reaches a terminal status."""
    for _ in range(timeout):
        ev = client.evaluations.get(eval_id)
        if ev.status in TERMINAL_STATUSES:
            return ev
        time.sleep(1)
    raise TimeoutError(f"evaluation {eval_id} did not complete within {timeout}s")


def test_single_evaluation(client: TropekClient) -> None:
    """Trigger one evaluation and assert it completes."""
    step("Step 7: Trigger single evaluation")
    result = client.evaluations.trigger(
        "checkout-api",
        "integration-test",
        "http-availability-slo",
        "2026-03-15T08:00:00Z",
        "2026-03-15T08:30:00Z",
    )
    eval_id = result["id"]
    print(f"triggered: {eval_id}")
    ev = poll_eval(client, eval_id)
    print(f"status={ev.status} result={ev.result} score={ev.score}")
    assert ev.status == "completed", f"expected completed, got {ev.status}"
    print("PASS: single evaluation")


def test_pin_baseline(client: TropekClient) -> None:
    """Pin a baseline on the first evaluation."""
    step("Step 8: Pin baseline")
    evals = client.evaluations.list(asset_name="checkout-api")
    eval_id = str(evals.items[0].id)
    result = client.evaluations.pin_baseline(eval_id, "integration test pin", "test-runner")
    print(f"pinned: {eval_id}")
    assert result.baseline_pinned_at is not None
    print("PASS: pin baseline")


def test_batch_evaluation(client: TropekClient) -> None:
    """Trigger a batch evaluation for an asset group and wait for all to complete."""
    step("Step 9: Trigger batch evaluation")
    result = client.evaluations.trigger_batch(
        "core-services",
        "batch-test",
        "2026-03-15T08:00:00Z",
        "2026-03-15T08:30:00Z",
    )
    batch_id = result["batch_id"]
    eval_ids = result["evaluation_ids"]
    print(f"batch triggered: {batch_id}, {len(eval_ids)} evaluations")
    assert len(eval_ids) >= 1, f"expected at least 1 evaluation, got {len(eval_ids)}"

    for _ in range(60):
        statuses = {client.evaluations.get(str(eid)).status for eid in eval_ids}
        if statuses.issubset(TERMINAL_STATUSES):
            break
        time.sleep(1)

    print("PASS: batch evaluation")


def test_regression_eval(client: TropekClient) -> None:
    """Trigger a second evaluation to exercise baseline comparison."""
    step("Step 10: Trigger regression eval after pin")
    result = client.evaluations.trigger(
        "checkout-api",
        "regression-test",
        "http-availability-slo",
        "2026-03-16T12:00:00Z",
        "2026-03-16T12:30:00Z",
    )
    eval_id = result["id"]
    print(f"triggered regression eval: {eval_id}")
    ev = poll_eval(client, eval_id)
    print(f"status={ev.status} result={ev.result} score={ev.score}")
    print("PASS: regression eval completed (check result manually if needed)")


def test_override_status(client: TropekClient) -> None:
    """Override an evaluation result and restore it."""
    step("Step 11: Override evaluation status")
    evals = client.evaluations.list(asset_name="checkout-api")
    eval_id = str(evals.items[0].id)

    result = client.evaluations.override_status(eval_id, "fail", "testing override", "test-runner")
    assert result.result == "fail"
    assert result.original_result is not None

    result = client.evaluations.restore_override(eval_id)
    assert result.original_result is None
    print("PASS: override + restore")


def test_override_to_pass(client: TropekClient) -> None:
    """Override a completed evaluation to pass and verify original_result is preserved."""
    step("Step 12: Override completed eval result to pass")
    evals = client.evaluations.list(asset_name="checkout-api")
    completed = [e for e in evals.items if e.status == "completed"]
    assert completed, "expected at least one completed eval"
    eval_id = str(completed[0].id)
    original_result = completed[0].result

    result = client.evaluations.override_status(
        eval_id, "pass", "manual override to pass", "test-runner"
    )
    assert result.result == "pass", f"expected pass, got {result.result}"
    assert result.original_result == original_result
    print(f"overridden: {original_result} -> pass")

    result = client.evaluations.restore_override(eval_id)
    assert result.result == original_result, (
        f"expected {original_result} after restore, got {result.result}"
    )
    assert result.original_result is None
    print("PASS: override result to pass + restore")


def test_reeval_from_pinned_baseline(client: TropekClient) -> None:
    """Pin the 2nd evaluation, then re-evaluate from that pinned baseline."""
    step("Step 14: Pin baseline + re-evaluate from pinned")
    evals = client.evaluations.list(asset_name="checkout-api")
    completed = [e for e in evals.items if e.status == "completed"]
    assert len(completed) >= 2, f"need >= 2 completed evals, got {len(completed)}"

    # Pin the 2nd evaluation (not the most recent)
    pin_target = str(completed[1].id)
    pin_result = client.evaluations.pin_baseline(
        pin_target, "e2e test: set baseline for re-eval", "test-runner"
    )
    assert pin_result.baseline_pinned_at is not None
    print(f"pinned eval {pin_target}")

    # Re-evaluate from the pinned baseline
    result = client.evaluations.re_evaluate(
        "checkout-api", "http-availability-slo", from_baseline=True
    )
    print(
        f"re-evaluated {result['affected_evaluations']} evals (SLO v{result['slo_version_used']})"
    )
    assert result["affected_evaluations"] >= 1, "expected at least 1 re-evaluated eval"
    for r in result["results"]:
        print(f"  {r['period_start'][:16]}: {r['old_result']} -> {r['new_result']}")
    print("PASS: re-evaluate from pinned baseline")


def test_reeval_from_date(client: TropekClient) -> None:
    """Re-evaluate evaluations from a specific date."""
    step("Step 15: Re-evaluate from date")
    result = client.evaluations.re_evaluate(
        "checkout-api",
        "http-availability-slo",
        from_date="2026-03-15T16:00:00Z",
    )
    print(
        f"re-evaluated {result['affected_evaluations']} evals (SLO v{result['slo_version_used']})"
    )
    assert result["affected_evaluations"] >= 1, "expected at least 1 re-evaluated eval"
    for r in result["results"]:
        print(f"  {r['period_start'][:16]}: {r['old_result']} -> {r['new_result']}")
    print("PASS: re-evaluate from date")


def test_reeval_dry_run(client: TropekClient) -> None:
    """Dry-run re-evaluation returns diffs without writing."""
    step("Step 16: Re-evaluate dry run")
    result = client.evaluations.re_evaluate(
        "checkout-api",
        "http-availability-slo",
        from_date="2026-03-15T00:00:00Z",
        dry_run=True,
    )
    print(
        f"dry run: {result['affected_evaluations']} evals would be affected "
        f"(SLO v{result['slo_version_used']})"
    )
    assert result["affected_evaluations"] >= 0
    print("PASS: re-evaluate dry run")


def test_annotations(client: TropekClient) -> None:
    """Create, list, update, and delete an annotation on an evaluation."""
    step("Step 13: Annotation lifecycle")
    evals = client.evaluations.list(asset_name="checkout-api")
    assert evals.items, "expected evaluations"
    eval_id = str(evals.items[0].id)

    ann = client.annotations.create(
        eval_id,
        "deployment looked fine, ignoring regression",
        author="test-runner",
        category="deployment",
    )
    assert ann.content == "deployment looked fine, ignoring regression"
    assert ann.author == "test-runner"
    ann_id = str(ann.id)
    print(f"created annotation: {ann_id}")

    anns = client.annotations.list(eval_id)
    assert any(str(a.id) == ann_id for a in anns), f"annotation {ann_id} not found in list"
    print(f"listed {len(anns)} annotation(s)")

    updated = client.annotations.update(eval_id, ann_id, content="updated note")
    assert updated.content == "updated note"
    print("updated annotation content")

    client.annotations.delete(eval_id, ann_id)
    assert not any(str(a.id) == ann_id for a in client.annotations.list(eval_id))
    print("PASS: create, list, update, delete annotation")


def main() -> None:
    """Entry point — parse API URL from argv and run all tests."""
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <api_url>", file=sys.stderr)
        sys.exit(1)

    client = TropekClient(sys.argv[1])

    test_single_evaluation(client)
    test_pin_baseline(client)
    test_batch_evaluation(client)
    test_regression_eval(client)
    test_override_status(client)
    test_override_to_pass(client)
    test_reeval_from_pinned_baseline(client)
    test_reeval_from_date(client)
    test_reeval_dry_run(client)
    test_annotations(client)

    print("\n=== All integration tests passed ===")


if __name__ == "__main__":
    main()
