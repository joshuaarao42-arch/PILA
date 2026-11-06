"""Customer generation (random, seeded) and CSV import/export."""
from __future__ import annotations

import random
from pathlib import Path
from typing import List, Sequence, Union

import pandas as pd

from .errors import ConfigError
from .models import Customer, SimulationConfig

CSV_COLUMNS = ["id", "arrival_time", "service_time", "priority"]
MAX_IMPORT_ROWS = 500


def generate_customers(config: SimulationConfig) -> List[Customer]:
    """Generate customers for ``config``.

    Arrivals form a Poisson process (exponential gaps, mean
    ``mean_interarrival``) rounded to whole time units; service times are
    uniform integers in ``[min_service, max_service]``. Priorities are drawn so
    that urgent levels (1, 2, ...) are rarer than routine ones. The same seed
    always yields the same customers.
    """
    config.validate()
    rng = random.Random(config.seed)
    levels = list(range(1, config.priority_levels + 1))
    weights = levels[:]  # priority p has weight p -> urgent customers are rarer

    customers: List[Customer] = []
    clock = 0.0
    for i in range(1, config.num_customers + 1):
        clock += rng.expovariate(1.0 / config.mean_interarrival)
        customers.append(
            Customer(
                id=i,
                arrival_time=float(round(clock)),
                service_time=float(rng.randint(config.min_service, config.max_service)),
                priority=rng.choices(levels, weights=weights, k=1)[0],
            )
        )
    return customers


def customers_to_dataframe(customers: Sequence[Customer]) -> pd.DataFrame:
    return pd.DataFrame(
        [(c.id, c.arrival_time, c.service_time, c.priority) for c in customers],
        columns=CSV_COLUMNS,
    )


def customers_from_dataframe(df: pd.DataFrame) -> List[Customer]:
    """Validate a DataFrame and convert it to customers."""
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [c for c in ("arrival_time", "service_time") if c not in df.columns]
    if missing:
        raise ConfigError(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Expected columns: {', '.join(CSV_COLUMNS)} (id and priority are optional)."
        )
    if df.empty:
        raise ConfigError("The file contains no customers.")
    if len(df) > MAX_IMPORT_ROWS:
        raise ConfigError(f"At most {MAX_IMPORT_ROWS} customers can be imported.")

    for col in ("arrival_time", "service_time"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df[["arrival_time", "service_time"]].isna().any().any():
        raise ConfigError("arrival_time and service_time must be numeric in every row.")

    if "id" not in df.columns:
        df["id"] = range(1, len(df) + 1)
    df["id"] = pd.to_numeric(df["id"], errors="coerce")
    if df["id"].isna().any() or (df["id"] % 1 != 0).any():
        raise ConfigError("id values must be whole numbers.")
    if df["id"].duplicated().any():
        raise ConfigError("id values must be unique.")

    if "priority" not in df.columns:
        df["priority"] = 3
    df["priority"] = pd.to_numeric(df["priority"], errors="coerce")
    if df["priority"].isna().any() or (df["priority"] % 1 != 0).any():
        raise ConfigError("priority values must be whole numbers.")

    customers = [
        Customer(int(r.id), float(r.arrival_time), float(r.service_time), int(r.priority))
        for r in df.itertuples(index=False)
    ]
    return sorted(customers, key=lambda c: (c.arrival_time, c.id))


def load_customers_csv(path: Union[str, Path]) -> List[Customer]:
    path = Path(path)
    try:
        df = pd.read_csv(path)
    except FileNotFoundError:
        raise ConfigError(f"File not found: {path}") from None
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        raise ConfigError(f"Could not read '{path.name}' as CSV: {exc}") from None
    return customers_from_dataframe(df)


def save_customers_csv(customers: Sequence[Customer], path: Union[str, Path]) -> Path:
    path = Path(path)
    customers_to_dataframe(customers).to_csv(path, index=False)
    return path
