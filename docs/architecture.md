# Architecture

## Execution-Critical Path

```
Market Data Ingest → Timestamp (monotonic) → Ring Buffer → Fan-out → Execution Decision → Async Queue → Ack
```

## Timestamping & Latency Attribution

- Hot path uses monotonic clocks only
- Wall clock exists only in the control plane
- Latency measured in segments:
  - **Decision latency** (what we control)
  - **Execution latency** (what external systems influence)

## Fan-Out & Backpressure

- Lock-free ring buffer with independent cursors per consumer
- Producer never blocks
- Slow consumers are detected, isolated, optionally dropped
- Overload is signaled, not hidden
- **Tradeoff:** Latency > completeness

## Execution Semantics

- Execution is asynchronous
- Acknowledgement is explicit and delayed
- Failures surfaced via completion metadata
- Execution slowdown never backpressures market data ingest

## Observability

- Hot path updates only thread-local counters
- No locks, no syscalls, no allocations on hot path
- Sidecar aggregates and exports metrics asynchronously
- Metrics are best-effort, approximate under stress
- Dropped metrics are acceptable; blocking trading is not

## Failure Injection

Deliberately test:
- Slow consumers
- Execution backlog
- Market data bursts
- Observability loss
- Process restarts

Goal: Degrade predictably and recover cleanly

## Deployment Topology

**Phase 1 — Single Host**
- All hot-path components co-located
- Clean latency attribution

**Phase 2 — Split Control Plane**
- Hot path isolated
- Observability and automation off-host
- Human systems never in execution path

## Cold Start & Warm-Up

State machine: `INIT → WARM-UP → READY → DEGRADED`

- Readiness is stability-based and latency-aware
- Metrics during warm-up marked untrusted

## Automation

- Automation can isolate, alert, prepare
- Humans approve high-risk actions
- Hot-path restarts during trading are forbidden
- Runbooks are short, explicit, auditable

## Capacity Planning

- Scale up, not out, on hot path
- Explicit load shedding
- Known saturation points
- System fails by shedding load before violating latency guarantees
