import pandas as pd
import pytest

from pila.analytics import (best_algorithms, export_history_csv, export_reports,
                            history_algorithm_averages, results_to_customers_df,
                            results_to_summary_df, waiting_by_priority)
from pila.database import Database
from pila.engine import compare_algorithms
from pila.errors import ConfigError, DatabaseError, PilaError
from pila.generator import generate_customers
from pila.models import SimulationConfig
from pila.sample_data import seed_sample_history


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def results():
    cfg = SimulationConfig(num_customers=30, num_counters=2, seed=8)
    return compare_algorithms(generate_customers(cfg), cfg)


def test_save_and_history(db, results):
    ids = db.save_results(results)
    assert len(ids) == 4 and db.count_simulations() == 4
    hist = db.get_history()
    assert set(hist["algorithm"]) == {"fcfs", "priority", "sjf", "rr"}
    assert hist["group_id"].nunique() == 1
    assert len(db.get_history("sjf")) == 1


def test_customer_records_persisted(db, results):
    sim_id = db.save_result(results[0])
    df = db.get_customer_records(sim_id)
    assert len(df) == 30
    assert df["waiting_time"].mean() == pytest.approx(results[0].summary.avg_waiting_time)


def test_load_result_replays_identically(db, results):
    for r in results:
        sim_id = db.save_result(r)
        rebuilt = db.load_result(sim_id)
        assert rebuilt.summary == r.summary
        assert rebuilt.slices == r.slices


def test_delete_cascades(db, results):
    ids = db.save_results(results)
    db.delete_simulations(ids[:1])
    assert db.count_simulations() == 3
    with db._connect() as conn:
        orphans = conn.execute(
            "SELECT COUNT(*) FROM customer_records WHERE simulation_id = ?", (ids[0],)).fetchone()[0]
    assert orphans == 0
    db.clear_history()
    assert db.count_simulations() == 0


def test_missing_simulation_raises(db):
    with pytest.raises(DatabaseError):
        db.load_result(999)


def test_sql_injection_is_inert(db):
    cfg = SimulationConfig(seed=1)
    db.save_config("x'; DROP TABLE simulations;--", cfg)
    assert db.list_configs() == ["x'; DROP TABLE simulations;--"]
    assert db.count_simulations() == 0  # table still exists


def test_config_presets_roundtrip(db):
    cfg = SimulationConfig(num_customers=12, num_counters=4, seed=77, time_quantum=2.5)
    db.save_config("Lunch", cfg)
    db.save_config("Lunch", SimulationConfig(num_customers=13, seed=77))  # upsert
    assert db.load_config("Lunch").num_customers == 13
    assert db.list_configs() == ["Lunch"]
    db.delete_config("Lunch")
    assert db.list_configs() == []
    with pytest.raises(DatabaseError):
        db.load_config("Lunch")
    with pytest.raises(ConfigError):
        db.save_config("   ", cfg)


def test_summary_dataframe(results):
    df = results_to_summary_df(results)
    assert list(df["Algorithm"]) == ["FCFS", "Priority", "SJF", "Round Robin"]
    assert df["Utilization %"].between(0, 100).all()
    best = best_algorithms(df)
    assert best["Avg Waiting"][0] == df.loc[df["Avg Waiting"].idxmin(), "Algorithm"]


def test_customer_dataframe_and_priority_pivot(results):
    df = results_to_customers_df(results)
    assert len(df) == 4 * 30 and set(df["algorithm"]) == {"FCFS", "Priority", "SJF", "Round Robin"}
    pivot = waiting_by_priority(results)
    assert set(pivot.columns) == set(df["algorithm"])


def test_history_aggregation(db):
    seed_sample_history(db)
    agg = history_algorithm_averages(db.get_history())
    assert len(agg) == 4 and (agg["runs"] == 4).all()
    assert len(db.list_configs()) == 4


def test_export_reports(tmp_path, results):
    summary, customers = export_reports(results, tmp_path / "report")
    assert summary.name == "report.csv" and customers.name == "report_customers.csv"
    assert len(pd.read_csv(summary)) == 4
    assert len(pd.read_csv(customers)) == 120


def test_export_errors(tmp_path, results):
    with pytest.raises(PilaError):
        export_reports([], tmp_path / "x.csv")
    with pytest.raises(PilaError):
        export_reports(results, tmp_path / "missing_dir" / "x.csv")
    with pytest.raises(PilaError):
        export_history_csv(pd.DataFrame(), tmp_path / "h.csv")


def test_export_history(tmp_path, db, results):
    db.save_results(results)
    path = export_history_csv(db.get_history(), tmp_path / "hist")
    assert len(pd.read_csv(path)) == 4
