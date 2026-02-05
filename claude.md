# Project Context

## What This System Is

A low-latency trading infrastructure simulator focused on **execution-path realism**, not trading strategy.

- Trading logic is intentionally simple
- Latency, determinism, failure behavior, and operability are the product
- Mirrors HFT DevOps responsibilities, not research code

## Core Design Principles

1. **Protect the hot path** — No blocking, no dynamic allocation, no shared locks with non-critical components
2. **Fail explicitly, not silently** — Overload is expected; drops and isolation are intentional; metrics tell the truth
3. **Prefer predictability over peak throughput** — Vertical scaling, known bottlenecks, explicit scale limits

## Execution-Critical Path (The Spine)

```
Market Data Ingest
 → Timestamp (monotonic)
 → In-memory event bus (ring buffer)
 → Fan-out with per-consumer cursors
 → Execution decision
 → Async execution queue
 → Completion acknowledgement
```

- No network hops on the hot path
- Latency attribution is deterministic
- Consumer slowness never contaminates producer latency

## Directory Purpose

| Directory | Purpose |
|-----------|---------|
| `core/` | Hot-path logic ONLY (latency critical) |
| `core/ingest/` | Market data ingestion |
| `core/time/` | Monotonic timestamping |
| `core/bus/` | Ring buffer event bus |
| `core/execution/` | Execution decision & async queue |
| `core/state/` | In-memory state |
| `control/` | Control plane (non-critical path) |
| `control/metrics/` | Thread-local counters, async aggregation |
| `control/health/` | Readiness, liveness |
| `control/automation/` | Runbooks, isolation |
| `control/failure/` | Failure injection |
| `runtime/` | Process lifecycle |
| `runtime/warmup/` | JIT warm-up, cache priming |
| `runtime/readiness/` | State machine: INIT → WARM-UP → READY → DEGRADED |
| `runtime/shutdown/` | Graceful shutdown |
| `config/` | Static configuration |
| `tests/` | Test suites |
| `docs/` | Architecture documentation |

## Current State

Infrastructure skeleton only. No logic implemented.
