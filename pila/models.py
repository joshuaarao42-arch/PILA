"""Core data models: customers, counters and the simulation configuration."""
from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import Any, ClassVar, Dict, Optional

from .errors import ConfigError

#: Tolerance used when comparing floating point simulation times.
EPS = 1e-9


class CustomerState(str, Enum):
    """Lifecycle of a customer inside the simulation."""

    UPCOMING = "upcoming"  # has not arrived yet
    WAITING = "waiting"    # in the queue
    SERVING = "serving"    # currently at a counter
    DONE = "done"          # finished


@dataclass(eq=False)
class Customer:
    """A customer who needs ``service_time`` units of service.

    ``priority`` follows the usual convention: **1 is the most urgent**.
    Runtime fields are mutated by the engine, so the engine always works on
    fresh copies (see :meth:`fresh_copy`).
    """

    id: int
    arrival_time: float
    service_time: float
    priority: int = 3

    remaining_time: float = field(init=False, default=0.0)
    state: CustomerState = field(init=False, default=CustomerState.UPCOMING)
    first_start_time: Optional[float] = field(init=False, default=None)
    finish_time: Optional[float] = field(init=False, default=None)
    counter_id: Optional[int] = field(init=False, default=None)
    enqueue_seq: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        if self.arrival_time < 0 or not math.isfinite(self.arrival_time):
            raise ConfigError(f"Customer {self.id}: arrival time must be >= 0.")
        if self.service_time <= 0 or not math.isfinite(self.service_time):
            raise ConfigError(f"Customer {self.id}: service time must be > 0.")
        if int(self.priority) < 1:
            raise ConfigError(f"Customer {self.id}: priority must be >= 1.")
        self.priority = int(self.priority)
        self.remaining_time = float(self.service_time)

    def fresh_copy(self) -> "Customer":
        return Customer(self.id, float(self.arrival_time), float(self.service_time), self.priority)

    @property
    def has_started(self) -> bool:
        return self.first_start_time is not None

    @property
    def turnaround_time(self) -> float:
        if self.finish_time is None:
            raise ValueError("customer has not finished")
        return round(self.finish_time - self.arrival_time, 9)

    @property
    def waiting_time(self) -> float:
        """Total time spent in the queue (turnaround minus service)."""
        return max(0.0, round(self.turnaround_time - self.service_time, 9))

    @property
    def response_time(self) -> float:
        if self.first_start_time is None:
            raise ValueError("customer has not started")
        return round(self.first_start_time - self.arrival_time, 9)


@dataclass(eq=False)
class Counter:
    """A service counter. Serves one customer (or one slice) at a time."""

    id: int
    customer: Optional[Customer] = None
    slice_start: float = 0.0
    slice_end: float = 0.0
    busy_time: float = 0.0      # accumulated time of *completed* slices
    customers_served: int = 0

    @property
    def is_busy(self) -> bool:
        return self.customer is not None


@dataclass
class SimulationConfig:
    """User-facing parameters of a simulation."""

    num_customers: int = 50
    num_counters: int = 3
    mean_interarrival: float = 2.0
    min_service: int = 2
    max_service: int = 10
    priority_levels: int = 3
    time_quantum: float = 4.0
    seed: Optional[int] = None
    speed: float = 4.0

    LABELS: ClassVar[Dict[str, str]] = {
        "num_customers": "Customers",
        "num_counters": "Counters",
        "mean_interarrival": "Mean inter-arrival time",
        "min_service": "Minimum service time",
        "max_service": "Maximum service time",
        "priority_levels": "Priority levels",
        "time_quantum": "Time quantum",
        "seed": "Seed",
        "speed": "Simulation speed",
    }
    LIMITS: ClassVar[Dict[str, tuple]] = {
        "num_customers": (1, 500),
        "num_counters": (1, 10),
        "mean_interarrival": (0.1, 60.0),
        "min_service": (1, 100),
        "max_service": (1, 100),
        "priority_levels": (1, 5),
        "time_quantum": (0.5, 100.0),
        "speed": (0.1, 200.0),
    }
    INT_FIELDS: ClassVar[tuple] = (
        "num_customers", "num_counters", "min_service", "max_service", "priority_levels",
    )

    def validate(self) -> "SimulationConfig":
        for name, (lo, hi) in self.LIMITS.items():
            value = getattr(self, name)
            label = self.LABELS[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ConfigError(f"{label} must be a number.")
            if not math.isfinite(value):
                raise ConfigError(f"{label} must be a finite number.")
            if name in self.INT_FIELDS and int(value) != value:
                raise ConfigError(f"{label} must be a whole number.")
            if not lo <= value <= hi:
                raise ConfigError(f"{label} must be between {lo:g} and {hi:g}.")
        if self.min_service > self.max_service:
            raise ConfigError("Minimum service time cannot exceed the maximum.")
        if self.seed is not None:
            if isinstance(self.seed, bool) or not isinstance(self.seed, int):
                raise ConfigError("Seed must be a whole number (or left blank).")
            if not 0 <= self.seed <= 2**31 - 1:
                raise ConfigError("Seed must be between 0 and 2147483647.")
        return self

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SimulationConfig":
        """Build a validated config from loosely-typed input (e.g. form fields)."""
        values: Dict[str, Any] = {}
        for name in cls.LABELS:
            if name not in data:
                continue
            raw = data[name]
            label = cls.LABELS[name]
            if name == "seed":
                if raw is None or (isinstance(raw, str) and not raw.strip()):
                    values[name] = None
                    continue
                try:
                    values[name] = int(str(raw).strip())
                except ValueError:
                    raise ConfigError("Seed must be a whole number (or left blank).") from None
                continue
            try:
                number = float(str(raw).strip()) if isinstance(raw, str) else float(raw)
            except (TypeError, ValueError):
                raise ConfigError(f"{label} must be a number.") from None
            if name in cls.INT_FIELDS:
                if not math.isfinite(number) or int(number) != number:
                    raise ConfigError(f"{label} must be a whole number.")
                number = int(number)
            values[name] = number
        return cls(**values).validate()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def with_seed(self, seed: int) -> "SimulationConfig":
        return replace(self, seed=seed)

    def ensure_seed(self) -> "SimulationConfig":
        """Return a copy with a concrete seed so the run is reproducible."""
        if self.seed is not None:
            return replace(self)
        return replace(self, seed=random.SystemRandom().randrange(1, 2**31))
