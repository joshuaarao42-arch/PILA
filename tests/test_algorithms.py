"""Scheduling logic, verified against hand-computed schedules."""
import pytest

from pila.algorithms import ALGORITHMS, create_algorithm
from pila.engine import SimulationEngine
from pila.errors import ConfigError
from pila.models import Customer


def run(customers, algo_key, counters=1, quantum=4.0):
    engine = SimulationEngine(customers, counters, create_algorithm(algo_key, quantum))
    engine.run_to_completion()
    return engine


def by_id(engine):
    return {c.id: c for c in engine.customers}


# ----------------------------------------------------------------- registry
def test_registry_has_four_algorithms():
    assert set(ALGORITHMS) == {"fcfs", "priority", "sjf", "rr"}


def test_unknown_algorithm_rejected():
    with pytest.raises(ConfigError):
        create_algorithm("lottery")


# --------------------------------------------------------------------- FCFS
def test_fcfs_single_counter_hand_computed():
    cs = [Customer(1, 0, 5), Customer(2, 1, 3), Customer(3, 2, 1)]
    e = by_id(run(cs, "fcfs"))
    assert (e[1].first_start_time, e[1].finish_time) == (0, 5)
    assert (e[2].first_start_time, e[2].finish_time) == (5, 8)
    assert (e[3].first_start_time, e[3].finish_time) == (8, 9)
    assert [e[i].waiting_time for i in (1, 2, 3)] == [0, 4, 6]
    assert [e[i].turnaround_time for i in (1, 2, 3)] == [5, 7, 7]


def test_fcfs_multi_counter():
    cs = [Customer(1, 0, 4), Customer(2, 0, 3), Customer(3, 0, 2), Customer(4, 0, 1)]
    engine = run(cs, "fcfs", counters=2)
    e = by_id(engine)
    assert [e[i].waiting_time for i in (1, 2, 3, 4)] == [0, 0, 3, 4]
    assert e[3].counter_id == 2 and e[4].counter_id == 1
    result = engine.result()
    assert result.summary.avg_waiting_time == pytest.approx(1.75)
    assert result.summary.utilization == pytest.approx(1.0)  # 10 busy / (2 * 5)


# ---------------------------------------------------------------------- SJF
def test_sjf_picks_shortest_waiting_job():
    cs = [Customer(1, 0, 5), Customer(2, 1, 3), Customer(3, 2, 1)]
    e = by_id(run(cs, "sjf"))
    assert e[3].first_start_time == 5 and e[3].finish_time == 6
    assert e[2].first_start_time == 6 and e[2].finish_time == 9
    assert sum(c.waiting_time for c in e.values()) == pytest.approx(8)


def test_sjf_is_non_preemptive():
    # A short job arriving mid-service must NOT interrupt the running one.
    cs = [Customer(1, 0, 10), Customer(2, 1, 1)]
    e = by_id(run(cs, "sjf"))
    assert e[1].finish_time == 10 and e[2].first_start_time == 10


def test_sjf_tie_broken_by_arrival_then_id():
    cs = [Customer(1, 0, 4), Customer(3, 1, 2), Customer(2, 1, 2), Customer(4, 0.5, 2)]
    e = by_id(run(cs, "sjf"))
    # after job 1: candidates 4(arr .5), 2(arr 1), 3(arr 1) all service 2
    assert e[4].first_start_time < e[2].first_start_time < e[3].first_start_time


# ----------------------------------------------------------------- Priority
def test_priority_serves_most_urgent_first():
    cs = [Customer(1, 0, 5, 3), Customer(2, 1, 3, 3), Customer(3, 2, 1, 1), Customer(4, 3, 2, 2)]
    e = by_id(run(cs, "priority"))
    # after customer 1 (0-5): priority 1 (#3), then 2 (#4), then 3 (#2)
    assert e[3].first_start_time == 5
    assert e[4].first_start_time == 6
    assert e[2].first_start_time == 8


def test_priority_ties_fall_back_to_arrival():
    cs = [Customer(1, 0, 5, 2), Customer(2, 2, 1, 2), Customer(3, 1, 1, 2)]
    e = by_id(run(cs, "priority"))
    assert e[3].first_start_time == 5 and e[2].first_start_time == 6


def test_priority_can_starve_low_priority():
    cs = [Customer(1, 0, 2, 1), Customer(2, 0, 2, 5)]
    cs += [Customer(10 + i, 1 + 2 * i, 2, 1) for i in range(5)]
    e = by_id(run(cs, "priority"))
    # the priority-5 customer is served only after every priority-1 customer
    assert e[2].first_start_time >= max(e[10 + i].finish_time for i in range(5))


# -------------------------------------------------------------- Round Robin
def test_round_robin_hand_computed():
    cs = [Customer(1, 0, 5), Customer(2, 1, 3), Customer(3, 2, 1)]
    engine = run(cs, "rr", quantum=2)
    e = by_id(engine)
    assert {i: e[i].finish_time for i in e} == {1: 9, 2: 8, 3: 5}
    assert {i: e[i].waiting_time for i in e} == {1: 4, 2: 4, 3: 2}
    seq = [(s.customer_id, s.start, s.end) for s in engine.slices]
    assert seq == [(1, 0, 2), (2, 2, 4), (3, 4, 5), (1, 5, 7), (2, 7, 8), (1, 8, 9)]


def test_round_robin_large_quantum_equals_fcfs():
    cs = [Customer(1, 0, 5), Customer(2, 1, 3), Customer(3, 2, 1)]
    rr = by_id(run(cs, "rr", quantum=100))
    fc = by_id(run(cs, "fcfs"))
    assert {i: rr[i].finish_time for i in rr} == {i: fc[i].finish_time for i in fc}


def test_round_robin_slices_never_exceed_quantum():
    cs = [Customer(i, i, 7) for i in range(1, 6)]
    engine = run(cs, "rr", counters=2, quantum=3)
    assert all(s.duration <= 3 + 1e-9 for s in engine.slices)


def test_round_robin_response_time_better_than_fcfs():
    cs = [Customer(i, 0, 10) for i in range(1, 5)]
    rr = run(cs, "rr", quantum=2).result().summary.avg_response_time
    fc = run(cs, "fcfs").result().summary.avg_response_time
    assert rr < fc


# ------------------------------------------------------------ engine basics
def test_idle_gap_before_first_arrival():
    e = by_id(run([Customer(1, 10, 3)], "fcfs"))
    assert e[1].first_start_time == 10 and e[1].waiting_time == 0


def test_simultaneous_completion_and_arrival():
    # Customer 2 arrives exactly when 1 finishes: served immediately, zero wait.
    e = by_id(run([Customer(1, 0, 4), Customer(2, 4, 2)], "fcfs"))
    assert e[2].first_start_time == 4 and e[2].waiting_time == 0
