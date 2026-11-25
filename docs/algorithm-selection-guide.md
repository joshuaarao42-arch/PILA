# Choosing a Scheduling Algorithm

PILA includes four scheduling strategies. The best choice depends on whether you want predictable arrival order, short jobs first, urgency-based service, or time-sharing.

## First-Come, First-Served (FCFS)

FCFS serves customers in the order they arrive. It is straightforward and predictable, and it works well when fairness by arrival order is the priority. A long service can make later customers wait (the convoy effect).

**Choose FCFS when:** arrival order should determine service order.

## Shortest Job First (SJF)

SJF selects the waiting customer with the shortest service time. It can reduce average waiting time when service durations are known, but long jobs may wait behind many short jobs.

**Choose SJF when:** service durations are known and reducing average waiting is important.

## Priority

Priority scheduling serves the most urgent waiting customer first. When priorities are equal, arrival order can be used as the tie-breaker. Customers with low priority may wait longer if high-priority work keeps arriving.

**Choose Priority when:** urgency matters more than arrival order.

## Round Robin (RR)

Round Robin gives each customer a time slice (quantum), then moves unfinished work to the back of the queue. A smaller quantum improves responsiveness but increases switching overhead; a larger quantum behaves more like FCFS.

**Choose RR when:** each customer should receive regular turns rather than waiting for one long job to finish.

## Comparison

| Algorithm | Main selection rule | Main trade-off |
| --- | --- | --- |
| FCFS | Earliest arrival | Simple, but long jobs delay others |
| SJF | Shortest waiting service time | Low average wait, but possible starvation |
| Priority | Highest urgency | Urgent work first, but low priorities may starve |
| RR | Rotating time slices | Responsive sharing, with quantum overhead |

## Interpreting simulation results

Compare average waiting time, response time, turnaround time, and counter utilization together. No single metric identifies the best algorithm for every workload. Run the same customer set through multiple algorithms to make a fair comparison.
