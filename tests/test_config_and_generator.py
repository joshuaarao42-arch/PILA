import pytest

from pila.errors import ConfigError
from pila.generator import (customers_from_dataframe, generate_customers, load_customers_csv,
                            save_customers_csv)
from pila.models import Customer, SimulationConfig

import pandas as pd


def test_same_seed_same_customers():
    cfg = SimulationConfig(seed=5)
    a = [(c.arrival_time, c.service_time, c.priority) for c in generate_customers(cfg)]
    b = [(c.arrival_time, c.service_time, c.priority) for c in generate_customers(cfg)]
    assert a == b


def test_different_seed_differs():
    a = generate_customers(SimulationConfig(seed=1))
    b = generate_customers(SimulationConfig(seed=2))
    assert [c.service_time for c in a] != [c.service_time for c in b]


def test_generated_values_respect_config():
    cfg = SimulationConfig(num_customers=200, min_service=3, max_service=6, priority_levels=4, seed=9)
    cs = generate_customers(cfg)
    assert len(cs) == 200
    assert all(3 <= c.service_time <= 6 for c in cs)
    assert all(1 <= c.priority <= 4 for c in cs)
    arrivals = [c.arrival_time for c in cs]
    assert arrivals == sorted(arrivals) and arrivals[0] >= 0
    assert [c.id for c in cs] == list(range(1, 201))


def test_ensure_seed_creates_reproducible_config():
    cfg = SimulationConfig().ensure_seed()
    assert cfg.seed is not None
    assert cfg.ensure_seed().seed == cfg.seed


@pytest.mark.parametrize("field,value", [
    ("num_customers", 0), ("num_customers", 501), ("num_counters", 0), ("num_counters", 11),
    ("mean_interarrival", 0), ("min_service", 0), ("priority_levels", 6), ("time_quantum", 0),
    ("speed", 0), ("seed", -1),
])
def test_invalid_values_rejected(field, value):
    with pytest.raises(ConfigError):
        SimulationConfig(**{field: value}).validate()


def test_min_cannot_exceed_max_service():
    with pytest.raises(ConfigError):
        SimulationConfig(min_service=9, max_service=3).validate()


def test_from_dict_coerces_form_strings():
    cfg = SimulationConfig.from_dict({"num_customers": "25", "num_counters": " 2 ", "mean_interarrival": "1.5",
                                      "seed": ""})
    assert cfg.num_customers == 25 and cfg.num_counters == 2 and cfg.seed is None


@pytest.mark.parametrize("bad", [{"num_customers": "abc"}, {"num_customers": "2.5"}, {"seed": "x"},
                                 {"time_quantum": "nan"}, {"speed": "inf"}])
def test_from_dict_rejects_garbage(bad):
    with pytest.raises(ConfigError):
        SimulationConfig.from_dict(bad)


def test_customer_validation():
    with pytest.raises(ConfigError):
        Customer(1, -1, 2)
    with pytest.raises(ConfigError):
        Customer(1, 0, 0)
    with pytest.raises(ConfigError):
        Customer(1, 0, 1, priority=0)


def test_csv_roundtrip(tmp_path):
    cs = generate_customers(SimulationConfig(num_customers=10, seed=3))
    path = save_customers_csv(cs, tmp_path / "c.csv")
    back = load_customers_csv(path)
    assert [(c.id, c.arrival_time, c.service_time, c.priority) for c in back] == \
           [(c.id, c.arrival_time, c.service_time, c.priority) for c in cs]


def test_csv_optional_columns_default():
    cs = customers_from_dataframe(pd.DataFrame({"arrival_time": [3, 1], "service_time": [2, 2]}))
    assert [c.id for c in cs] == [2, 1] and all(c.priority == 3 for c in cs)


@pytest.mark.parametrize("df", [
    pd.DataFrame({"arrival_time": [1]}),
    pd.DataFrame({"arrival_time": [1], "service_time": ["x"]}),
    pd.DataFrame({"arrival_time": [1, 2], "service_time": [1, 1], "id": [1, 1]}),
    pd.DataFrame({"arrival_time": [], "service_time": []}),
])
def test_csv_invalid_inputs(df):
    with pytest.raises(ConfigError):
        customers_from_dataframe(df)


def test_missing_csv_file(tmp_path):
    with pytest.raises(ConfigError):
        load_customers_csv(tmp_path / "nope.csv")
