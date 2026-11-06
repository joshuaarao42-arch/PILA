"""SQLite persistence for simulation history and saved configurations."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional, Sequence, Union

import pandas as pd

from .engine import run_simulation
from .errors import ConfigError, DatabaseError
from .metrics import SimulationResult
from .models import Customer, SimulationConfig

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "pila.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS simulations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    algorithm TEXT NOT NULL,
    algorithm_name TEXT NOT NULL,
    num_customers INTEGER NOT NULL,
    num_counters INTEGER NOT NULL,
    mean_interarrival REAL NOT NULL,
    min_service INTEGER NOT NULL,
    max_service INTEGER NOT NULL,
    priority_levels INTEGER NOT NULL,
    time_quantum REAL NOT NULL,
    seed INTEGER,
    speed REAL NOT NULL,
    total_served INTEGER NOT NULL,
    avg_waiting_time REAL NOT NULL,
    avg_turnaround_time REAL NOT NULL,
    avg_response_time REAL NOT NULL,
    max_waiting_time REAL NOT NULL,
    std_waiting_time REAL NOT NULL,
    max_queue_length INTEGER NOT NULL,
    avg_queue_length REAL NOT NULL,
    utilization REAL NOT NULL,
    throughput REAL NOT NULL,
    makespan REAL NOT NULL,
    counter_utilization TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS customer_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id INTEGER NOT NULL REFERENCES simulations(id) ON DELETE CASCADE,
    customer_id INTEGER NOT NULL,
    arrival_time REAL NOT NULL,
    service_time REAL NOT NULL,
    priority INTEGER NOT NULL,
    start_time REAL NOT NULL,
    finish_time REAL NOT NULL,
    counter_id INTEGER NOT NULL,
    waiting_time REAL NOT NULL,
    turnaround_time REAL NOT NULL,
    response_time REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS configurations (
    name TEXT PRIMARY KEY,
    config_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_records_sim ON customer_records(simulation_id);
CREATE INDEX IF NOT EXISTS idx_sim_group ON simulations(group_id);
"""

_SUMMARY_COLUMNS = (
    "total_served", "avg_waiting_time", "avg_turnaround_time", "avg_response_time",
    "max_waiting_time", "std_waiting_time", "max_queue_length", "avg_queue_length",
    "utilization", "throughput", "makespan",
)
_CONFIG_COLUMNS = (
    "num_customers", "num_counters", "mean_interarrival", "min_service", "max_service",
    "priority_levels", "time_quantum", "seed", "speed",
)


class Database:
    """Thin, safe wrapper around a SQLite file (all queries are parameterised)."""

    def __init__(self, path: Union[str, Path, None] = None) -> None:
        self.path = Path(path) if path else DEFAULT_DB_PATH
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise DatabaseError(f"Cannot create database folder: {exc}") from exc
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        try:
            conn = sqlite3.connect(self.path)
        except sqlite3.Error as exc:
            raise DatabaseError(f"Cannot open database '{self.path}': {exc}") from exc
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise DatabaseError(f"Database error: {exc}") from exc
        finally:
            conn.close()

    # ------------------------------------------------------------- simulations
    def save_results(self, results: Sequence[SimulationResult]) -> List[int]:
        """Save several results atomically; returns their new row ids."""
        ids: List[int] = []
        with self._connect() as conn:
            for r in results:
                ids.append(self._insert_result(conn, r))
        for r, rid in zip(results, ids):
            r.db_id = rid
        return ids

    def save_result(self, result: SimulationResult) -> int:
        return self.save_results([result])[0]

    @staticmethod
    def _insert_result(conn: sqlite3.Connection, r: SimulationResult) -> int:
        cfg, s = r.config.to_dict(), r.summary
        cols = (
            ["group_id", "created_at", "algorithm", "algorithm_name"]
            + list(_CONFIG_COLUMNS) + list(_SUMMARY_COLUMNS) + ["counter_utilization"]
        )
        values = (
            [r.group_id or "", r.created_at, r.algorithm_key, r.algorithm_name]
            + [cfg[c] for c in _CONFIG_COLUMNS]
            + [getattr(s, c) for c in _SUMMARY_COLUMNS]
            + [json.dumps(list(s.counter_utilization))]
        )
        cur = conn.execute(
            f"INSERT INTO simulations ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            values,
        )
        sim_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO customer_records (simulation_id, customer_id, arrival_time, service_time,"
            " priority, start_time, finish_time, counter_id, waiting_time, turnaround_time,"
            " response_time) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [
                (sim_id, c.customer_id, c.arrival_time, c.service_time, c.priority, c.start_time,
                 c.finish_time, c.counter_id, c.waiting_time, c.turnaround_time, c.response_time)
                for c in r.records
            ],
        )
        return sim_id

    def get_history(self, algorithm: Optional[str] = None) -> pd.DataFrame:
        query, params = "SELECT * FROM simulations", []
        if algorithm:
            query += " WHERE algorithm = ?"
            params.append(algorithm)
        query += " ORDER BY id DESC"
        with self._connect() as conn:
            return pd.read_sql_query(query, conn, params=params)

    def get_customer_records(self, simulation_id: int) -> pd.DataFrame:
        with self._connect() as conn:
            return pd.read_sql_query(
                "SELECT customer_id, arrival_time, service_time, priority, start_time, finish_time,"
                " counter_id, waiting_time, turnaround_time, response_time"
                " FROM customer_records WHERE simulation_id = ? ORDER BY customer_id",
                conn, params=[simulation_id],
            )

    def count_simulations(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM simulations").fetchone()[0]

    def load_result(self, simulation_id: int) -> SimulationResult:
        """Rebuild a full result (incl. Gantt data) by replaying the stored customers.

        The engine is deterministic, so the replay reproduces the original run.
        """
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM simulations WHERE id = ?", (simulation_id,)).fetchone()
            if row is None:
                raise DatabaseError(f"Simulation #{simulation_id} does not exist.")
            recs = conn.execute(
                "SELECT customer_id, arrival_time, service_time, priority FROM customer_records"
                " WHERE simulation_id = ? ORDER BY customer_id", (simulation_id,)
            ).fetchall()
        try:
            config = SimulationConfig(**{c: row[c] for c in _CONFIG_COLUMNS})
            customers = [Customer(r["customer_id"], r["arrival_time"], r["service_time"], r["priority"]) for r in recs]
            result = run_simulation(customers, config, row["algorithm"], row["group_id"])
        except ConfigError as exc:
            raise DatabaseError(f"Stored simulation #{simulation_id} is corrupt: {exc}") from exc
        result.created_at = row["created_at"]
        result.db_id = simulation_id
        return result

    def delete_simulations(self, ids: Sequence[int]) -> int:
        if not ids:
            return 0
        with self._connect() as conn:
            cur = conn.executemany("DELETE FROM simulations WHERE id = ?", [(int(i),) for i in ids])
            return cur.rowcount

    def clear_history(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM simulations")

    # ---------------------------------------------------------- configurations
    def save_config(self, name: str, config: SimulationConfig) -> None:
        name = name.strip()
        if not name:
            raise ConfigError("Preset name cannot be empty.")
        if len(name) > 60:
            raise ConfigError("Preset name is too long (max 60 characters).")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO configurations (name, config_json, updated_at) VALUES (?,?,?)"
                " ON CONFLICT(name) DO UPDATE SET config_json=excluded.config_json,"
                " updated_at=excluded.updated_at",
                (name, json.dumps(config.to_dict()), datetime.now().isoformat(timespec="seconds")),
            )

    def load_config(self, name: str) -> SimulationConfig:
        with self._connect() as conn:
            row = conn.execute("SELECT config_json FROM configurations WHERE name = ?", (name,)).fetchone()
        if row is None:
            raise DatabaseError(f"Preset '{name}' does not exist.")
        try:
            return SimulationConfig.from_dict(json.loads(row["config_json"]))
        except (ValueError, TypeError) as exc:
            raise DatabaseError(f"Preset '{name}' is corrupt: {exc}") from exc

    def list_configs(self) -> List[str]:
        with self._connect() as conn:
            return [r["name"] for r in conn.execute("SELECT name FROM configurations ORDER BY name")]

    def delete_config(self, name: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM configurations WHERE name = ?", (name,))
