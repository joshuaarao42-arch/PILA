"""Discrete-event simulation engine.

The engine is *exact*: time jumps from event to event (arrival or end of a
service slice), so results never depend on a frame rate or tick size. The same
engine drives the animated Pygame view (via :meth:`advance_to`) and the
instant batch runs (via :meth:`run_to_completion`), which guarantees that what
you watch is what gets measured.

Tie-breaking convention at a single instant ``t``:
  1. slices ending at ``t`` are completed,
  2. customers arriving at ``t`` join the queue,
  3. customers returning from a preempted slice (Round Robin) join the queue,
  4. idle counters (lowest id first) pick the next customer.
"""
from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Dict, List, Optional, Sequence

from .algorithms import SchedulingAlgorithm, available_algorithms, create_algorithm
from .errors import SimulationError
from .metrics import CustomerRecord, SimulationResult, Slice, compute_summary
from .models import EPS, Counter, Customer, CustomerState, SimulationConfig


class SimulationEngine:
    def __init__(
        self,
        customers: Sequence[Customer],
        num_counters: int,
        algorithm: SchedulingAlgorithm,
    ) -> None:
        if num_counters < 1:
            raise SimulationError("At least one counter is required.")
        if not customers:
            raise SimulationError("At least one customer is required.")
        ids = [c.id for c in customers]
        if len(set(ids)) != len(ids):
            raise SimulationError("Customer ids must be unique.")

        self.algorithm = algorithm
        self.customers: List[Customer] = sorted(
            (c.fresh_copy() for c in customers), key=lambda c: (c.arrival_time, c.id)
        )
        self.counters: List[Counter] = [Counter(i + 1) for i in range(num_counters)]
        self.queue: List[Customer] = []
        self.completed: List[Customer] = []
        self.slices: List[Slice] = []

        self.now = 0.0
        self.first_arrival = self.customers[0].arrival_time
        self.max_queue_length = 0
        self.queue_timeline: List[tuple] = [(0.0, 0)]

        self._next_arrival = 0
        self._seq = 0
        self._last_event_time = 0.0
        self._queue_area = 0.0

    # ------------------------------------------------------------------ state
    @property
    def finished(self) -> bool:
        return len(self.completed) == len(self.customers)

    def next_event_time(self) -> Optional[float]:
        times = []
        if self._next_arrival < len(self.customers):
            times.append(self.customers[self._next_arrival].arrival_time)
        times.extend(c.slice_end for c in self.counters if c.customer is not None)
        return min(times) if times else None

    def waiting_in_order(self) -> List[Customer]:
        """Queue contents in the order the algorithm will serve them."""
        return self.algorithm.order(self.queue)

    # --------------------------------------------------------------- stepping
    def advance_to(self, target: float) -> None:
        """Process every event with time <= ``target`` and move the clock."""
        if target < self.now - EPS:
            raise SimulationError("Simulation time cannot move backwards.")
        while True:
            t = self.next_event_time()
            if t is None or t > target + EPS:
                break
            self._process_events(max(t, self._last_event_time))
        self.now = self._last_event_time if self.finished else max(self.now, target)

    def run_to_completion(self) -> None:
        while not self.finished:
            t = self.next_event_time()
            if t is None:  # pragma: no cover - defensive, cannot happen
                raise SimulationError("Simulation stalled before all customers finished.")
            self._process_events(max(t, self._last_event_time))
        self.now = self._last_event_time

    # ----------------------------------------------------------------- events
    def _enqueue(self, customer: Customer) -> None:
        self._seq += 1
        customer.enqueue_seq = self._seq
        customer.state = CustomerState.WAITING
        self.queue.append(customer)

    def _process_events(self, t: float) -> None:
        # Queue length is constant between events: integrate before changing it.
        self._queue_area += len(self.queue) * (t - self._last_event_time)
        self._last_event_time = t

        # 1. complete slices ending at t
        returning: List[Customer] = []
        for ctr in self.counters:
            c = ctr.customer
            if c is None or ctr.slice_end > t + EPS:
                continue
            duration = ctr.slice_end - ctr.slice_start
            ctr.busy_time += duration
            c.remaining_time -= duration
            self.slices.append(Slice(ctr.id, c.id, ctr.slice_start, ctr.slice_end))
            ctr.customer = None
            if c.remaining_time <= EPS:
                c.remaining_time = 0.0
                c.state = CustomerState.DONE
                c.finish_time = ctr.slice_end
                c.counter_id = ctr.id
                ctr.customers_served += 1
                self.completed.append(c)
            else:
                returning.append(c)

        # 2. arrivals, 3. preempted customers returning
        while (
            self._next_arrival < len(self.customers)
            and self.customers[self._next_arrival].arrival_time <= t + EPS
        ):
            self._enqueue(self.customers[self._next_arrival])
            self._next_arrival += 1
        for c in returning:
            self._enqueue(c)

        # 4. dispatch to idle counters
        for ctr in self.counters:
            if ctr.customer is None and self.queue:
                c = self.algorithm.select(self.queue, t)
                self.queue.remove(c)
                length = min(self.algorithm.time_slice(c), c.remaining_time)
                if length <= 0:
                    raise SimulationError("Algorithm returned a non-positive time slice.")
                if c.first_start_time is None:
                    c.first_start_time = t
                c.state = CustomerState.SERVING
                ctr.customer = c
                ctr.slice_start = t
                ctr.slice_end = t + length

        qlen = len(self.queue)
        self.max_queue_length = max(self.max_queue_length, qlen)
        if self.queue_timeline and abs(self.queue_timeline[-1][0] - t) <= EPS:
            self.queue_timeline[-1] = (t, qlen)
        else:
            self.queue_timeline.append((t, qlen))

    # ------------------------------------------------------- live (for the UI)
    def remaining_of(self, customer: Customer) -> float:
        """Remaining service time at ``self.now`` (accounts for the running slice)."""
        for ctr in self.counters:
            if ctr.customer is customer:
                return max(0.0, customer.remaining_time - (self.now - ctr.slice_start))
        return customer.remaining_time

    def busy_time_at_now(self) -> float:
        total = 0.0
        for ctr in self.counters:
            total += ctr.busy_time
            if ctr.customer is not None:
                total += max(0.0, min(self.now, ctr.slice_end) - ctr.slice_start)
        return total

    def live_stats(self) -> Dict[str, float]:
        done = self.completed
        elapsed = max(self.now - self.first_arrival, 0.0)
        return {
            "now": self.now,
            "queue_length": len(self.queue),
            "max_queue_length": self.max_queue_length,
            "served": len(done),
            "total": len(self.customers),
            "avg_waiting": (sum(c.waiting_time for c in done) / len(done)) if done else 0.0,
            "utilization": (
                self.busy_time_at_now() / (len(self.counters) * elapsed) if elapsed > EPS else 0.0
            ),
        }

    # ----------------------------------------------------------------- result
    def result(self, config: Optional[SimulationConfig] = None, group_id: str = "") -> SimulationResult:
        if not self.finished:
            raise SimulationError("Simulation has not finished yet.")
        n = len(self.customers)
        if config is None:
            config = SimulationConfig(num_customers=n, num_counters=len(self.counters))
        config = replace(config, num_customers=n, num_counters=len(self.counters))
        summary = compute_summary(self.customers, self.counters, self.max_queue_length, self._queue_area)
        records = [CustomerRecord.from_customer(c) for c in sorted(self.customers, key=lambda c: c.id)]
        return SimulationResult(
            algorithm_key=self.algorithm.key,
            algorithm_name=self.algorithm.name,
            config=config,
            records=records,
            slices=list(self.slices),
            queue_timeline=list(self.queue_timeline),
            summary=summary,
            group_id=group_id,
        )


# ---------------------------------------------------------------- convenience
def new_group_id() -> str:
    """Identifier shared by all runs that used the same customer set."""
    return uuid.uuid4().hex[:12]


def run_simulation(
    customers: Sequence[Customer],
    config: SimulationConfig,
    algorithm_key: str,
    group_id: str = "",
) -> SimulationResult:
    engine = SimulationEngine(customers, config.num_counters, create_algorithm(algorithm_key, config.time_quantum))
    engine.run_to_completion()
    return engine.result(config, group_id)


def compare_algorithms(
    customers: Sequence[Customer],
    config: SimulationConfig,
    keys: Optional[Sequence[str]] = None,
    group_id: str = "",
) -> List[SimulationResult]:
    """Run several algorithms on the *identical* customer set."""
    keys = list(keys) if keys else [cls.key for cls in available_algorithms()]
    group_id = group_id or new_group_id()
    return [run_simulation(customers, config, key, group_id) for key in keys]
