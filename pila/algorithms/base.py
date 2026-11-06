"""Abstract base class for scheduling algorithms."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Iterable, List, Sequence

from ..models import Customer


class SchedulingAlgorithm(ABC):
    """Strategy deciding *who is served next* and *for how long*.

    The engine owns the clock, the counters and the ready queue. An algorithm
    only provides a total order over waiting customers (``sort_key``) and an
    optional preemption quantum (``time_slice``). Keeping algorithms this small
    makes them trivially testable and guarantees they are compared on exactly
    the same engine.
    """

    key: ClassVar[str]
    name: ClassVar[str]
    description: ClassVar[str]
    preemptive: ClassVar[bool] = False

    def __init__(self, time_quantum: float = 4.0) -> None:
        self.time_quantum = time_quantum

    @abstractmethod
    def sort_key(self, customer: Customer) -> tuple:
        """Smaller keys are served first. Must be a strict total order."""

    def select(self, queue: Sequence[Customer], now: float) -> Customer:
        if not queue:
            raise ValueError("cannot select from an empty queue")
        return min(queue, key=self.sort_key)

    def order(self, queue: Iterable[Customer]) -> List[Customer]:
        """Waiting customers in the order they would be served."""
        return sorted(queue, key=self.sort_key)

    def time_slice(self, customer: Customer) -> float:
        """Maximum continuous service before the customer is sent back."""
        return customer.remaining_time
