# Low-Latency Trading Infrastructure Simulator

## Project Overview

This project is a low-latency trading infrastructure simulator focused on **execution-path mechanics**, **lifecycle control**, and **operational behavior** rather than trading strategy.

It models how real HFT systems:
- Ingest market data with deterministic timestamps
- Fan out events to multiple consumers without blocking producers
- Execute under strict latency constraints with explicit state gating
- Degrade predictably under failure conditions
- Remain observable without disturbing the hot path

**This is not:**
- A trading strategy backtester
- A market simulator with realistic order book dynamics
- A distributed system (single-host, vertical scaling only)
- Production-ready code (educational/interview artifact)

**Why it exists:**

To demonstrate understanding of the infrastructure concerns that HFT DevOps and systems engineers face daily: protecting latency, managing state transitions, handling degradation, and building observability that doesn't lie.

---

## Design Principles

### 1. Protect the Hot Path

The execution-critical path has exactly one job: process events with minimal, predictable latency. Everything else—metrics, logging, health checks—happens elsewhere. No locks, no allocations, no syscalls on the hot path.

### 2. Explicit State Over Inference

The system's operational state is always explicit. `INIT → WARMUP → READY → DEGRADED` is a state machine with validated transitions, not a set of boolean flags that might drift. Components check state; they don't guess.

### 3. Determinism Over Throughput

We prefer predictable latency over peak throughput. A system that processes 100k events/sec with p99 of 50μs is more valuable than one that does 500k events/sec with p99 of 5ms. Known bottlenecks are features, not bugs.

### 4. Degrade Before Failing

When things go wrong, the system sheds load and signals degradation rather than crashing or lying. Slow consumers get dropped. Execution continues in degraded mode. Metrics report honestly, even if that means "I don't know."

### 5. Observability Must Not Lie

Metrics that block the hot path are worse than no metrics. We accept lossy, best-effort aggregation. Thread-local counters, async snapshots, approximate values under stress. If observability can't keep up, it drops data—it never adds latency.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CONTROL PLANE                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Metrics   │  │   Health    │  │  Failure Injection  │  │
│  │ (Aggregator)│  │   (Probe)   │  │    (Scenarios)      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ reads state (never writes on hot path)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    LIFECYCLE STATE                          │
│           INIT ──► WARMUP ──► READY ◄──► DEGRADED           │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ gates all hot-path operations
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                       HOT PATH                              │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ Market Data  │───►│ Ring Buffer  │───►│  Execution   │  │
│  │   Ingest     │    │  (Fan-Out)   │    │   Consumer   │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                   │                   │          │
│         │                   │                   ▼          │
│         │                   │            ┌──────────────┐  │
│         │                   │            │     Ack      │  │
│         │                   │            │   + Sink     │  │
│         └───────────────────┴────────────┴──────────────┘  │
│                                                             │
│  Monotonic timestamps only. No locks. No allocations.       │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ observability sink (null-object pattern)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    RUNTIME CONTROL                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Warmup    │  │  Readiness  │  │      Shutdown       │  │
│  │ Controller  │  │    Probe    │  │     Controller      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow Direction

1. **Market Data Ingest** emits events with monotonic timestamps
2. **Ring Buffer** stores events; producer never blocks
3. **Consumers** (including Executor) read independently via cursors
4. **Executor** produces Ack records with decision/completion timestamps
5. **Observability Sink** receives (event, ack) pairs via null-object pattern

### What Does NOT Talk to What

| Component | Cannot Import |
|-----------|---------------|
| `core/*` (hot path) | `control/*`, `runtime/*` |
| `control/metrics` | `core/bus`, `core/execution` |
| `control/failure` | `core/bus`, `core/execution`, `core/ingest` |
| Observability sink | `control/*` (lives in core, protocol only) |

This layering is enforced by tests that parse imports via AST.

---

## Component Details

### Monotonic Timestamping (`core/time`)

```python
now() -> int          # Returns perf_counter_ns()
delta(start, end) -> int  # Pure subtraction
```

- Uses `time.perf_counter_ns()` — monotonic, nanosecond precision
- No wall clock on hot path (wall clock is control plane only)
- Enables deterministic latency attribution

### Ring Buffer (`core/bus`)

```python
RingBuffer[T](capacity)
  .publish(item) -> seq    # Never blocks, returns sequence number
  .get(seq) -> T           # Raises Overrun if data was overwritten
  .head() -> int           # Current write position

Consumer[T](ring)
  .poll() -> T | None      # Returns item or None if caught up
  .available() -> int      # Count of unread items
  .reset_to_head()         # Recovery after overrun
```

**Key Properties:**
- Fixed-size, pre-allocated buffer
- Lock-free single-producer design
- Independent cursor per consumer
- Explicit `Overrun` exception (not silent data loss)
- Producer independence: slow consumers never block publishing

### Lifecycle State Machine (`core/state`)

```
        ┌─────────────────────────┐
        │                         │
        ▼                         │
      INIT ──► WARMUP ──► READY ◄─┴─► DEGRADED
                  │                      │
                  └──────────────────────┘
```

| Transition | When |
|------------|------|
| INIT → WARMUP | System starting, caches cold |
| WARMUP → READY | Warm-up complete, latency stable |
| WARMUP → DEGRADED | Failure during warm-up |
| READY → DEGRADED | Failure detected |
| DEGRADED → READY | Recovery confirmed |
| DEGRADED → WARMUP | Full restart required |

**Invalid transitions raise `InvalidTransition`.**

### Execution (`core/execution`)

```python
Executor(ring, lifecycle, sink=None)
  .process() -> Ack | None   # Consumes one event, returns ack
  .cursor() -> int           # Current read position

Ack:
  .seq             # Sequence number of processed event
  .decision_ts     # When decision logic ran (monotonic)
  .completion_ts   # When ack was constructed (monotonic)
  .executed        # True only if state was READY
```

**Execution Semantics:**
- `INIT` state → raises `NotReady`
- `WARMUP` / `DEGRADED` → processes but `executed=False`
- `READY` → processes with `executed=True`
- No events available → returns `None` immediately (non-blocking)

### Observability Sink (`core/execution/observability`)

```python
class ObservabilitySink(Protocol):
    def observe(self, event: Any, ack: Ack) -> None: ...

class NoOpSink:
    def observe(self, event: Any, ack: Ack) -> None:
        pass  # Zero-cost when observability disabled
```

**Why null-object pattern:**
- No `if sink is not None:` branching on every event
- Executor always calls `sink.observe()` — it's either NoOp or real
- Sink protocol lives in `core/` but implementations can live in `control/`

### Metrics Aggregator (`control/metrics`)

```python
Metrics()
  .observe(latency_ns)     # O(1), no allocation
  .snapshot() -> Snapshot  # Returns immutable copy
  .reset() -> Snapshot     # Atomic snapshot + reset

Snapshot:
  .count, .total_latency_ns, .min_latency_ns, .max_latency_ns
```

**Hot-Path Safety:**
- No locks (single-threaded aggregation assumed)
- No allocations in `observe()`
- Lossy under stress (acceptable)
- `snapshot()` and `reset()` are control-plane operations

### Failure Injection (`control/failure`)

```python
MarketDataOutage(lifecycle)
ExecutionFailure(lifecycle)
  .activate()      # Transitions to DEGRADED, saves previous state
  .deactivate()    # Restores previous state
  .is_active()     # Returns current status
```

**Properties:**
- Uses only valid lifecycle transitions (no monkey-patching)
- Idempotent activation/deactivation
- Cannot activate from INIT or DEGRADED states
- Does not import hot-path modules

---

## Failure & Degradation Table

| Failure Scenario | Detection | System Response | Recovery |
|-----------------|-----------|-----------------|----------|
| **Slow Consumer** | `head - cursor > capacity` | `Overrun` raised on read | `consumer.reset_to_head()` |
| **Market Data Outage** | External signal | Lifecycle → DEGRADED | `scenario.deactivate()` |
| **Execution Backlog** | Consumer falls behind | Overrun, events dropped | Reset cursor, continue |
| **Cold Start** | `state == INIT` | `NotReady` exception | Complete warm-up cycle |
| **Warm-up Incomplete** | `state == WARMUP` | Execution allowed, `executed=False` | Wait for READY transition |
| **State Corruption** | Invalid transition attempted | `InvalidTransition` raised | Explicit operator action |

### Degradation Philosophy

```
Normal Operation     Degraded Operation     Failure
      │                     │                  │
      │   shed load         │   explicit       │
      │   ──────────►       │   signal         │
      │                     │   ──────────►    │
      │                     │                  │
   READY              DEGRADED           (no crash)
```

The system does not crash under load. It:
1. Drops data at the ring buffer (producer never blocks)
2. Signals degradation via lifecycle state
3. Continues processing with `executed=False`
4. Reports honest metrics (including "unknown" during stress)

---

## What This System Does NOT Do

| Limitation | Why |
|------------|-----|
| **No multi-threading** | Python GIL makes lock-free claims meaningless in true concurrent scenarios. Single-threaded model is honest. |
| **No actual network I/O** | This is a simulator. Real market data feeds would require kernel bypass, FPGA, etc. |
| **No persistence** | Hot path has no disk I/O. State is in-memory only. |
| **No distributed coordination** | Single-host design. Distributed systems introduce latency that defeats the purpose. |
| **No microsecond latency** | Python's baseline overhead is ~100ns per function call. We model the *architecture*, not the absolute numbers. |
| **No order book simulation** | This is infrastructure, not market simulation. Events are opaque to the bus. |

### Honest Assessment

This system demonstrates *understanding* of low-latency principles, not production performance. A real HFT system would:

- Use C++ or Rust for the hot path
- Pin threads to CPU cores
- Use huge pages and NUMA-aware allocation
- Bypass the kernel for network I/O
- Measure in nanoseconds, not microseconds

What transfers from this project:
- **Architectural patterns** (ring buffers, state machines, fan-out)
- **Operational concerns** (warm-up, degradation, observability)
- **Design discipline** (layering, explicit failures, determinism)

---

## Directory Structure

```
low-latency-trading-sim/
├── core/                    # HOT PATH ONLY
│   ├── bus/                 # Ring buffer, consumers
│   ├── execution/           # Executor, Ack, observability sink
│   ├── ingest/              # Market data source
│   ├── state/               # Lifecycle state machine
│   └── time/                # Monotonic timestamps
├── control/                 # CONTROL PLANE (non-critical)
│   ├── automation/          # Runbooks (placeholder)
│   ├── failure/             # Failure injection scenarios
│   ├── health/              # Health probes (placeholder)
│   └── metrics/             # Metrics aggregator
├── runtime/                 # PROCESS LIFECYCLE
│   ├── readiness/           # Readiness probe
│   ├── shutdown/            # Graceful shutdown
│   └── warmup/              # Warm-up controller
├── config/                  # Static configuration
├── tests/                   # Deterministic test suites
└── docs/                    # Architecture documentation
```

---

## Running Tests

```bash
# All tests
PYTHONPATH=. pytest tests/ -v

# Specific module
PYTHONPATH=. pytest tests/core/test_bus.py -v

# With coverage
PYTHONPATH=. pytest tests/ --cov=core --cov=control
```

**Test Properties:**
- No sleeps or timing assumptions
- Deterministic (same input → same output)
- Fast (<1 second total)
- 150+ tests covering all components

---

## Questions This System Can Answer

For interviews or design discussions:

1. **"How do you prevent slow consumers from affecting producers?"**
   → Ring buffer with independent cursors. Producer overwrites; consumer gets `Overrun`.

2. **"How do you handle failure without crashing?"**
   → Lifecycle state machine. Transition to DEGRADED, continue processing with `executed=False`.

3. **"How do you add observability without adding latency?"**
   → Null-object pattern. `NoOpSink` is always called; it's a no-op when disabled.

4. **"Why not use a queue?"**
   → Queues can block producers. Ring buffers have bounded, predictable behavior.

5. **"What's the difference between WARMUP and READY?"**
   → Cold caches, JIT compilation, branch predictor training. WARMUP metrics are unreliable.

6. **"How do you test failure scenarios without randomness?"**
   → Explicit `FailureScenario` objects with `activate()`/`deactivate()`. Deterministic.

---

## License

MIT License. See LICENSE file.
