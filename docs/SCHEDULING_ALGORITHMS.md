# Scheduling Algorithms in PILA

PILA lets you compare queue scheduling strategies using the same set of customers and service requirements. This guide summarizes the ideas behind the supported algorithms.

| Algorithm | How it selects the next customer | Main trade-off |
|---|---|---|
| FCFS | First customer to arrive | Simple and fair by arrival order, but long jobs can delay everyone behind them |
| Priority | Highest configured priority | Important customers can be served sooner; low-priority customers may wait longer |
| SJF | Customer with the shortest service time | Can reduce average waiting time when service times are known; long jobs may be delayed |
| Round Robin | Customers take turns in fixed time slices | Shares service time across customers; results depend on the chosen time quantum |

## Comparing runs fairly

- Use the same arrival times and service durations when comparing algorithms.
- Keep the number of service counters consistent.
- For Round Robin, record the time quantum used.
- Compare waiting time, turnaround time, throughput, and unfinished customers together.
- Repeat simulations with different workloads; one scenario does not prove an algorithm is always best.

The best scheduling strategy depends on the workload and the service goal.
