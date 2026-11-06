"""First Come, First Served."""
from ..models import Customer
from .base import SchedulingAlgorithm


class FCFS(SchedulingAlgorithm):
    key = "fcfs"
    name = "FCFS"
    description = "First Come, First Served: serve in order of arrival."

    def sort_key(self, customer: Customer) -> tuple:
        return (customer.arrival_time, customer.id)
