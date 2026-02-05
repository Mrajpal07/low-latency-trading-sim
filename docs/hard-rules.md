# Hard Rules

## Hot Path — NEVER

- No blocking calls
- No dynamic memory allocation
- No shared locks with non-critical components
- No network hops
- No syscalls for observability
- No wall clock access

## Hot Path — ALWAYS

- Monotonic timestamps only
- Thread-local counters for metrics
- Lock-free data structures
- Explicit failure signaling
- Deterministic latency attribution

## Backpressure

- Producer never blocks
- Slow consumers are isolated, not accommodated
- Drops are acceptable; blocking is not

## Observability

- Must never slow trading
- Best-effort under stress
- Tail latency must be honest

## Execution

- Asynchronous only
- Explicit acknowledgement
- Failures in completion metadata
- Execution slowdown never backpressures ingest

## Automation

- Reduce risk, never increase it
- Humans approve high-risk actions
- No hot-path restarts during trading

## Scaling

- Vertical on hot path
- Load shedding before latency violation
- Known bottlenecks, explicit limits

## Deliberately Excluded

- No Kubernetes on hot path
- No service mesh
- No distributed tracing in execution
- No auto-scaling trading components
- No attempt at infinite scalability
