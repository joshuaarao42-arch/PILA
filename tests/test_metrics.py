"""Statistical calculations checked against values computed by hand."""
import statistics

import pytest

from pila.algorithms import create_algorithm
from pila.engine import SimulationEngine
from pila.models import Customer


@pytest.fixture
def summary():
    # single counter, FCFS: waits 0,4,6 ; turnarounds 5,7,7 ; responses = waits
    cs = [Customer(1, 0, 5), Customer(2, 1, 3), Customer(3, 2, 1)]
    e = SimulationEngine(cs, 1, create_algorithm("fcfs"))
    e.run_to_completion()
    return e.result().summary


def test_average_waiting(summary):
    assert summary.avg_waiting_time == pytest.approx(10 / 3)


def test_average_turnaround(summary):
    assert summary.avg_turnaround_time == pytest.approx(19 / 3)


def test_max_waiting_and_std(summary):
    assert summary.max_waiting_time == 6
    assert summary.std_waiting_time == pytest.approx(statistics.pstdev([0, 4, 6]))


def test_max_queue_length(summary):
    assert summary.max_queue_length == 2  # customers 2 and 3 wait together


def test_average_queue_length(summary):
    # queue holds 1 during [1,2), 2 during [2,5), 1 during [5,8), 0 during [8,9)
    assert summary.avg_queue_length == pytest.approx((1 + 6 + 3) / 9)


def test_utilization_and_throughput(summary):
    assert summary.utilization == pytest.approx(1.0)
    assert summary.throughput == pytest.approx(3 / 9)
    assert summary.makespan == 9
    assert summary.total_served == 3


def test_utilization_with_idle_counter():
    e = SimulationEngine([Customer(1, 0, 4)], 2, create_algorithm("fcfs"))
    e.run_to_completion()
    s = e.result().summary
    assert s.utilization == pytest.approx(0.5)
    assert s.counter_utilization == pytest.approx((1.0, 0.0))


def test_single_customer_has_zero_std():
    e = SimulationEngine([Customer(1, 2, 3)], 1, create_algorithm("fcfs"))
    e.run_to_completion()
    s = e.result().summary
    assert s.std_waiting_time == 0 and s.avg_waiting_time == 0 and s.avg_response_time == 0
