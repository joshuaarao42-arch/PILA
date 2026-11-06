"""Non-preemptive Shortest Job First."""
from ..models import Customer
from .base import SchedulingAlgorithm


class SJF(SchedulingAlgorithm):
    key = "sjf"
    name = "SJF"
    description = "Shortest Job First: serve the shortest service time next; ties by arrival."

    def sort_key(self, customer: Customer) -> tuple:
        return (customer.remaining_time, customer.arrival_time, customer.id)
