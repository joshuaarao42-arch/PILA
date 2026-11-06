"""Properties that must hold for *every* algorithm on random workloads."""
import pytest

from pila.algorithms import ALGORITHMS
from pila.engine import SimulationEngine, compare_algorithms, run_simulation
from pila.errors import SimulationError
from pila.generator import generate_customers
from pila.algorithms import create_algorithm
from pila.models import Customer, SimulationConfig

SEEDS = [1, 7, 42, 99, 2024]
CONFIGS = [(1, 30), (2, 40), (4, 80)]


def make(seed, counters, n, **kw):
    cfg = SimulationConfig(num_customers=n, num_counters=counters, seed=seed, mean_interarrival=1.5, **kw)
    return cfg, generate_customers(cfg)


@pytest.mark.parametrize("key", list(ALGORITHMS))
@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("counters,n", CONFIGS)
def test_invariants(key, seed, counters, n):
    cfg, customers = make(seed, counters, n)
    engine = SimulationEngine(customers, counters, create_algorithm(key, cfg.time_quantum))
    engine.run_to_completion()
    res = engine.result(cfg)
    s = res.summary

    # every customer is served for exactly its service time
    per_customer = {}
    for sl in res.slices:
        per_customer[sl.customer_id] = per_customer.get(sl.customer_id, 0) + sl.duration
    for rec in res.records:
        assert per_customer[rec.customer_id] == pytest.approx(rec.service_time)
        assert rec.start_time >= rec.arrival_time
        assert rec.finish_time >= rec.arrival_time + rec.service_time - 1e-9
        assert rec.waiting_time == pytest.approx(rec.turnaround_time - rec.service_time)
        assert rec.response_time <= rec.waiting_time + 1e-9

    # work conservation: busy time equals total service demanded
    assert sum(c.busy_time for c in engine.counters) == pytest.approx(sum(r.service_time for r in res.records))

    # a counter never serves two slices at once
    for ctr in engine.counters:
        mine = sorted((x for x in res.slices if x.counter_id == ctr.id), key=lambda x: x.start)
        for a, b in zip(mine, mine[1:]):
            assert a.end <= b.start + 1e-9

    # time-weighted queue integral == sum of waiting times (Little's law identity)
    span = s.makespan - min(r.arrival_time for r in res.records)
    assert s.avg_queue_length * span == pytest.approx(sum(r.waiting_time for r in res.records))
    assert 0 < s.utilization <= 1 + 1e-9
    assert s.total_served == n


@pytest.mark.parametrize("seed", SEEDS)
def test_sjf_minimises_wait_among_nonpreemptive_single_counter(seed):
    cfg, customers = make(seed, 1, 40)
    res = {r.algorithm_key: r.summary.avg_waiting_time for r in compare_algorithms(customers, cfg)}
    assert res["sjf"] <= res["fcfs"] + 1e-9
    assert res["sjf"] <= res["priority"] + 1e-9


@pytest.mark.parametrize("seed", SEEDS)
def test_priority_gives_urgent_customers_shorter_waits(seed):
    cfg, customers = make(seed, 1, 120, priority_levels=3)
    pr = {r.algorithm_key: r for r in compare_algorithms(customers, cfg)}

    def mean_wait(res, level):
        waits = [r.waiting_time for r in res.records if r.priority == level]
        return sum(waits) / len(waits)

    assert mean_wait(pr["priority"], 1) <= mean_wait(pr["fcfs"], 1) + 1e-9


def test_all_algorithms_share_identical_customers_and_work():
    cfg, customers = make(5, 2, 50)
    results = compare_algorithms(customers, cfg)
    assert len({r.group_id for r in results}) == 1
    demands = {tuple((r.customer_id, r.arrival_time, r.service_time) for r in res.records) for res in results}
    assert len(demands) == 1


def test_engine_does_not_mutate_input_customers():
    cfg, customers = make(3, 2, 20)
    run_simulation(customers, cfg, "rr")
    assert all(c.finish_time is None and c.remaining_time == c.service_time for c in customers)


@pytest.mark.parametrize("key", list(ALGORITHMS))
def test_incremental_stepping_matches_batch(key):
    cfg, customers = make(11, 2, 40)
    batch = run_simulation(customers, cfg, key)
    stepped = SimulationEngine(customers, cfg.num_counters, create_algorithm(key, cfg.time_quantum))
    t = 0.0
    while not stepped.finished:
        t += 0.37
        stepped.advance_to(t)
    res = stepped.result(cfg)
    assert [(r.customer_id, r.finish_time) for r in res.records] == [(r.customer_id, r.finish_time) for r in batch.records]
    assert res.summary == batch.summary


def test_live_stats_progress():
    cfg, customers = make(3, 2, 30)
    engine = SimulationEngine(customers, 2, create_algorithm("fcfs"))
    engine.advance_to(engine.first_arrival + 10)
    stats = engine.live_stats()
    assert 0 <= stats["utilization"] <= 1.0 + 1e-9
    assert stats["served"] <= stats["total"]


def test_time_cannot_go_backwards():
    engine = SimulationEngine([Customer(1, 0, 2)], 1, create_algorithm("fcfs"))
    engine.advance_to(5)
    with pytest.raises(SimulationError):
        engine.advance_to(1)


def test_engine_input_validation():
    algo = create_algorithm("fcfs")
    with pytest.raises(SimulationError):
        SimulationEngine([], 1, algo)
    with pytest.raises(SimulationError):
        SimulationEngine([Customer(1, 0, 1)], 0, algo)
    with pytest.raises(SimulationError):
        SimulationEngine([Customer(1, 0, 1), Customer(1, 2, 1)], 1, algo)


def test_result_requires_finished_run():
    engine = SimulationEngine([Customer(1, 0, 5)], 1, create_algorithm("fcfs"))
    with pytest.raises(SimulationError):
        engine.result()
