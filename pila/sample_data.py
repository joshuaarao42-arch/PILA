"""Realistic demo scenarios used to seed the history database."""
from __future__ import annotations

from typing import Dict, List

from .database import Database
from .engine import compare_algorithms
from .generator import generate_customers
from .models import SimulationConfig

#: name -> config. Fixed seeds make the demo data reproducible.
SCENARIOS: Dict[str, SimulationConfig] = {
    "Bank Branch": SimulationConfig(num_customers=60, num_counters=3, mean_interarrival=2.5,
                                    min_service=3, max_service=12, priority_levels=3,
                                    time_quantum=4, seed=101, speed=4),
    "Hospital Triage": SimulationConfig(num_customers=40, num_counters=2, mean_interarrival=3.0,
                                        min_service=4, max_service=15, priority_levels=5,
                                        time_quantum=5, seed=202, speed=4),
    "Fast-Food Rush": SimulationConfig(num_customers=120, num_counters=5, mean_interarrival=1.0,
                                       min_service=2, max_service=8, priority_levels=2,
                                       time_quantum=3, seed=303, speed=8),
    "Government Office": SimulationConfig(num_customers=80, num_counters=2, mean_interarrival=4.0,
                                          min_service=5, max_service=20, priority_levels=4,
                                          time_quantum=6, seed=404, speed=6),
}


def seed_sample_history(db: Database) -> int:
    """Save every scenario (all four algorithms) plus presets. Returns runs saved."""
    saved = 0
    for name, config in SCENARIOS.items():
        db.save_config(name, config)
        results = compare_algorithms(generate_customers(config), config)
        saved += len(db.save_results(results))
    return saved


def scenario_names() -> List[str]:
    return list(SCENARIOS)
