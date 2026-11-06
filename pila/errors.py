"""Exception hierarchy used across PILA."""


class PilaError(Exception):
    """Base class for all PILA errors."""


class ConfigError(PilaError, ValueError):
    """Raised when a simulation configuration or input file is invalid."""


class SimulationError(PilaError):
    """Raised when the simulation engine is used incorrectly."""


class DatabaseError(PilaError):
    """Raised when a SQLite operation fails."""
