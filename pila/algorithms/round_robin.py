"""Round Robin with a fixed time quantum."""
from ..models import Customer
from .base import SchedulingAlgorithm


class RoundRobin(SchedulingAlgorithm):
    key = "rr"
    name = "Round Robin"
    description = "Each customer gets at most one quantum, then rejoins the back of the queue."
    preemptive = True

    def sort_key(self, customer: Customer) -> tuple:
        # ``enqueue_seq`` is stamped by the engine every time a customer
        # (re)joins the queue, giving a FIFO order that includes re-queues.
        return (customer.enqueue_seq,)

    def time_slice(self, customer: Customer) -> float:
        return min(self.time_quantum, customer.remaining_time)
