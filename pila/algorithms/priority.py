"""Non-preemptive priority scheduling."""
from ..models import Customer
from .base import SchedulingAlgorithm


class PriorityScheduling(SchedulingAlgorithm):
    key = "priority"
    name = "Priority"
    description = "Serve the most urgent customer first (1 = highest); ties by arrival."

    def sort_key(self, customer: Customer) -> tuple:
        return (customer.priority, customer.arrival_time, customer.id)
