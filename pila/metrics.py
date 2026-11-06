"""Result containers and statistical calculations."""
from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .errors import SimulationError
from .models import Counter, Customer, SimulationConfig


@dataclass(frozen=True)
class Slice:
    """One continuous stretch of service of a customer at a counter."""

    counter_id: int
    customer_id: int
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class CustomerRecord:
    """Immutable per-customer outcome."""

    customer_id: int
    arrival_time: float
    service_time: float
    priority: int
    start_time: float
    finish_time: float
    counter_id: int
    waiting_time: float
    turnaround_time: float
    response_time: float

    @classmethod
    def from_customer(cls, c: Customer) -> "CustomerRecord":
        return cls(
            customer_id=c.id,
            arrival_time=c.arrival_time,
            service_time=c.service_time,
            priority=c.priority,
            start_time=c.first_start_time,
            finish_time=c.finish_time,
            counter_id=c.counter_id,
            waiting_time=c.waiting_time,
            turnaround_time=c.turnaround_time,
            response_time=c.response_time,
        )


@dataclass(frozen=True)
class SimulationSummary:
    """Aggregate statistics of one run.

    Definitions (all times in simulation units):

    * waiting     = finish - arrival - service   (total time spent queued)
    * turnaround  = finish - arrival
    * response    = first service start - arrival
    * span        = last finish - first arrival
    * utilization = total busy time / (counters * span)
    * avg queue   = time-weighted mean number of waiting customers
    * throughput  = customers served / span
    """

    total_customers: int
    total_served: int
    avg_waiting_time: float
    avg_turnaround_time: float
    avg_response_time: float
    max_waiting_time: float
    std_waiting_time: float
    max_queue_length: int
    avg_queue_length: float
    utilization: float
    throughput: float
    makespan: float
    counter_utilization: Tuple[float, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["counter_utilization"] = list(self.counter_utilization)
        return data


@dataclass
class SimulationResult:
    """Everything produced by one finished simulation run."""

    algorithm_key: str
    algorithm_name: str
    config: SimulationConfig
    records: List[CustomerRecord]
    slices: List[Slice]
    queue_timeline: List[Tuple[float, int]]
    summary: SimulationSummary
    group_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    db_id: Optional[int] = None


def compute_summary(
    customers: Sequence[Customer],
    counters: Sequence[Counter],
    max_queue_length: int,
    queue_area: float,
) -> SimulationSummary:
    """Compute :class:`SimulationSummary` from a *finished* simulation."""
    if not customers:
        raise SimulationError("Cannot compute statistics without customers.")
    if any(c.finish_time is None for c in customers):
        raise SimulationError("All customers must be finished to compute statistics.")

    n = len(customers)
    waits = [c.waiting_time for c in customers]
    turnarounds = [c.turnaround_time for c in customers]
    responses = [c.response_time for c in customers]

    start = min(c.arrival_time for c in customers)
    end = max(c.finish_time for c in customers)
    span = end - start
    if span <= 0:
        raise SimulationError("Simulation span must be positive.")

    busy = [ctr.busy_time for ctr in counters]
    per_counter = tuple(b / span for b in busy)
    return SimulationSummary(
        total_customers=n,
        total_served=n,
        avg_waiting_time=sum(waits) / n,
        avg_turnaround_time=sum(turnarounds) / n,
        avg_response_time=sum(responses) / n,
        max_waiting_time=max(waits),
        std_waiting_time=statistics.pstdev(waits) if n > 1 else 0.0,
        max_queue_length=max_queue_length,
        avg_queue_length=queue_area / span,
        utilization=sum(busy) / (len(counters) * span),
        throughput=n / span,
        makespan=end,
        counter_utilization=per_counter,
    )
