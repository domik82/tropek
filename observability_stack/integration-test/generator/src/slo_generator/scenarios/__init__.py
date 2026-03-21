"""Scenario factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slo_generator.scenarios.base import BaseScenario


def get_scenario(name: str, **kwargs) -> BaseScenario:
    """Factory for creating scenarios by name."""
    from slo_generator.scenarios.csv_input import CSVScenario
    from slo_generator.scenarios.degradation import DegradationScenario
    from slo_generator.scenarios.healthy import HealthyScenario
    from slo_generator.scenarios.memory_leak import MemoryLeakScenario
    from slo_generator.scenarios.outage import OutageScenario
    from slo_generator.scenarios.polska import PolskaScenario
    from slo_generator.scenarios.step_change import StepChangeScenario
    from slo_generator.scenarios.traffic_spike import TrafficSpikeScenario

    scenarios = {
        "healthy": HealthyScenario,
        "outage": OutageScenario,
        "degradation": DegradationScenario,
        "csv": CSVScenario,
        "memory_leak": MemoryLeakScenario,
        "traffic_spike": TrafficSpikeScenario,
        "step_change": StepChangeScenario,
        "polska": PolskaScenario,
    }
    if name not in scenarios:
        raise ValueError(f"unknown scenario: {name!r}, expected one of {list(scenarios)}")
    return scenarios[name](**kwargs)
