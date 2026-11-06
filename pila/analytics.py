"""Pandas-based data processing and CSV export."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Sequence, Tuple, Union

import pandas as pd

from .errors import PilaError
from .metrics import SimulationResult

SUMMARY_COLUMNS: Dict[str, str] = {
    "algorithm_name": "Algorithm",
    "avg_waiting_time": "Avg Waiting",
    "avg_turnaround_time": "Avg Turnaround",
    "avg_response_time": "Avg Response",
    "max_waiting_time": "Max Waiting",
    "std_waiting_time": "Std Waiting",
    "max_queue_length": "Max Queue",
    "avg_queue_length": "Avg Queue",
    "utilization": "Utilization %",
    "throughput": "Throughput",
    "makespan": "Makespan",
    "total_served": "Served",
}
#: Metrics where a smaller value is better (used to highlight the winner).
LOWER_IS_BETTER = ("Avg Waiting", "Avg Turnaround", "Avg Response", "Max Waiting",
                   "Std Waiting", "Max Queue", "Avg Queue", "Makespan")


def results_to_summary_df(results: Sequence[SimulationResult]) -> pd.DataFrame:
    """One row per result with human-readable column names."""
    rows = []
    for r in results:
        d = r.summary.to_dict()
        d["algorithm_name"] = r.algorithm_name
        rows.append(d)
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=list(SUMMARY_COLUMNS.values()))
    df = df[list(SUMMARY_COLUMNS)].rename(columns=SUMMARY_COLUMNS)
    df["Utilization %"] = df["Utilization %"] * 100
    return df.round(3).reset_index(drop=True)


def results_to_customers_df(results: Sequence[SimulationResult]) -> pd.DataFrame:
    """Long-format per-customer table across all given results."""
    frames = []
    for r in results:
        df = pd.DataFrame([vars(rec) for rec in r.records])
        df.insert(0, "algorithm", r.algorithm_name)
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def waiting_by_priority(results: Sequence[SimulationResult]) -> pd.DataFrame:
    """Average waiting time per priority level (rows) and algorithm (columns)."""
    df = results_to_customers_df(results)
    if df.empty:
        return pd.DataFrame()
    return df.pivot_table(index="priority", columns="algorithm", values="waiting_time", aggfunc="mean").round(3)


def best_algorithms(summary: pd.DataFrame) -> Dict[str, Tuple[str, float]]:
    """For each lower-is-better metric, the winning algorithm and its value."""
    best: Dict[str, Tuple[str, float]] = {}
    if summary.empty:
        return best
    for col in ("Avg Waiting", "Avg Turnaround", "Max Waiting", "Max Queue"):
        row = summary.loc[summary[col].idxmin()]
        best[col] = (str(row["Algorithm"]), float(row[col]))
    return best


def history_algorithm_averages(history: pd.DataFrame) -> pd.DataFrame:
    """Aggregate saved runs by algorithm (mean of the key metrics + run count)."""
    if history.empty:
        return pd.DataFrame()
    agg = (
        history.groupby("algorithm_name")
        .agg(
            runs=("id", "count"),
            avg_waiting_time=("avg_waiting_time", "mean"),
            avg_turnaround_time=("avg_turnaround_time", "mean"),
            max_queue_length=("max_queue_length", "mean"),
            utilization=("utilization", "mean"),
        )
        .round(3)
        .reset_index()
    )
    return agg


def _check_writable(path: Path) -> None:
    if not path.parent.exists():
        raise PilaError(f"Folder does not exist: {path.parent}")


def export_reports(results: Sequence[SimulationResult], summary_path: Union[str, Path]) -> Tuple[Path, Path]:
    """Write ``<name>.csv`` (summary) and ``<name>_customers.csv`` (per customer)."""
    if not results:
        raise PilaError("There are no results to export. Run a simulation first.")
    summary_path = Path(summary_path)
    if summary_path.suffix.lower() != ".csv":
        summary_path = summary_path.with_suffix(".csv")
    _check_writable(summary_path)
    customers_path = summary_path.with_name(summary_path.stem + "_customers.csv")
    try:
        results_to_summary_df(results).to_csv(summary_path, index=False)
        results_to_customers_df(results).to_csv(customers_path, index=False)
    except OSError as exc:
        raise PilaError(f"Could not write report: {exc}") from exc
    return summary_path, customers_path


def export_history_csv(history: pd.DataFrame, path: Union[str, Path]) -> Path:
    path = Path(path)
    if path.suffix.lower() != ".csv":
        path = path.with_suffix(".csv")
    _check_writable(path)
    if history.empty:
        raise PilaError("History is empty - nothing to export.")
    try:
        history.to_csv(path, index=False)
    except OSError as exc:
        raise PilaError(f"Could not write file: {exc}") from exc
    return path
