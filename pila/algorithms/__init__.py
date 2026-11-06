"""Scheduling algorithm registry."""
from __future__ import annotations

from typing import Dict, List, Type

from ..errors import ConfigError
from .base import SchedulingAlgorithm
from .fcfs import FCFS
from .priority import PriorityScheduling
from .round_robin import RoundRobin
from .sjf import SJF

ALGORITHMS: Dict[str, Type[SchedulingAlgorithm]] = {
    cls.key: cls for cls in (FCFS, PriorityScheduling, SJF, RoundRobin)
}


def available_algorithms() -> List[Type[SchedulingAlgorithm]]:
    return list(ALGORITHMS.values())


def create_algorithm(key: str, time_quantum: float = 4.0) -> SchedulingAlgorithm:
    try:
        cls = ALGORITHMS[key]
    except KeyError:
        raise ConfigError(
            f"Unknown algorithm '{key}'. Choose one of: {', '.join(ALGORITHMS)}."
        ) from None
    if time_quantum <= 0:
        raise ConfigError("Time quantum must be positive.")
    return cls(time_quantum=time_quantum)


__all__ = [
    "ALGORITHMS", "SchedulingAlgorithm", "FCFS", "PriorityScheduling", "SJF",
    "RoundRobin", "available_algorithms", "create_algorithm",
]
