"""Headless smoke tests for the chart builders and the Pygame view."""
import os

import matplotlib
import pytest

matplotlib.use("Agg")

from pila.engine import compare_algorithms  # noqa: E402
from pila.generator import generate_customers  # noqa: E402
from pila.models import SimulationConfig  # noqa: E402
from pila.ui import charts  # noqa: E402


@pytest.fixture(scope="module")
def results():
    cfg = SimulationConfig(num_customers=30, num_counters=2, seed=3, priority_levels=4)
    return compare_algorithms(generate_customers(cfg), cfg)


@pytest.mark.parametrize("draw", [charts.draw_comparison, charts.draw_wait_analysis, charts.draw_queue_length])
def test_multi_result_charts(draw, results, tmp_path):
    fig = charts.new_figure()
    draw(fig, results)
    fig.savefig(tmp_path / "c.png")
    assert (tmp_path / "c.png").stat().st_size > 1000


@pytest.mark.parametrize("draw", [charts.draw_comparison, charts.draw_wait_analysis, charts.draw_queue_length])
def test_charts_handle_no_data(draw):
    draw(charts.new_figure(), [])


def test_single_result_and_gantt(results, tmp_path):
    fig = charts.new_figure()
    charts.draw_comparison(fig, results[:1])
    charts.draw_gantt(fig, results[3])
    charts.draw_gantt(fig, None)
    fig.savefig(tmp_path / "g.png")


def test_visualizer_headless_snapshot(tmp_path):
    pytest.importorskip("pygame")
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    from pila.visualization import QueueVisualizer

    cfg = SimulationConfig(num_customers=25, num_counters=3, seed=4)
    customers = generate_customers(cfg)
    for key in ("fcfs", "priority", "sjf", "rr"):
        out = tmp_path / f"{key}.png"
        QueueVisualizer(customers, cfg, key).snapshot(str(out), at_time=20)
        assert out.stat().st_size > 5000


def test_visualizer_reports_result_once():
    pytest.importorskip("pygame")
    import queue

    from pila.visualization import QueueVisualizer

    cfg = SimulationConfig(num_customers=10, num_counters=2, seed=1)
    out = queue.Queue()
    viz = QueueVisualizer(generate_customers(cfg), cfg, "sjf", speed=100, out_queue=out)
    for _ in range(2000):
        viz._advance_sim(0.1)
    assert viz.engine.finished
    kind, result = out.get_nowait()
    assert kind == "finished" and result.summary.total_served == 10
    assert out.empty()
