# Low-Latency Trading Infrastructure Simulator

A deterministic reference architecture for low-latency trading infrastructure, focused on execution safety, lifecycle control, and failure behavior, not trading strategy.

This project models how a high-frequency trading system behaves under load, under failure, and during recovery. It deliberately avoids strategy logic, UI, or exchange connectivity in order to isolate and prove the infrastructure mechanics that determine whether a trading system is safe to operate.

---

## What This Project Proves

This repository exists to demonstrate ability in low-latency infrastructure and DevOps engineering, specifically:

- Designing non-blocking execution paths
- Handling backpressure and explicit data loss
- Enforcing deterministic lifecycle transitions
- Building observability that does not pollute latency
- Operating systems through warm-up, degradation, and recovery

This is not a backtester.
This is not a trading strategy.
This is an infrastructure-first system focused on correctness under stress.

---

## Quick Verification

You do not need to read the code to verify the claims.

The system includes a deterministic, operator-driven CLI demo. Each scenario runs end-to-end in milliseconds and produces identical output every time.

```bash
# Stable execution: balanced load
python -m demo balanced

# Explicit backpressure: deterministic data loss
# First overrun always occurs at step 12
python -m demo producer-heavy

# Sparse data: clean empty polling
python -m demo consumer-heavy

# Failure handling: READY -> DEGRADED -> READY
python -m demo failure-recovery
```

If the output matches the README descriptions, the system behaves as designed.

---

## What This System Is (and Is Not)

**It is:**

- A deterministic simulator of low-latency trading infrastructure
- Focused on execution paths, lifecycle, and failure semantics
- Designed for operator reasoning and verification

**It is not:**

- A market-making system
- A real-time exchange connector
- A performance benchmark
- A cloud-native microservice demo

---

## Core Design Principles

### 1. Protect the Hot Path

The execution path does one thing: process events with minimal, predictable latency.

- No locks
- No blocking calls
- No allocations
- No logging
- No wall-clock time

Everything else happens outside the hot path.

**Why this matters:**
In production trading systems, a single lock or GC pause can invalidate timing assumptions. The hot path must remain isolated from operational concerns.

### 2. Explicit State Over Inference

The system has a formal lifecycle state machine:

```
INIT -> WARMUP -> READY <-> DEGRADED
```

Components read state. Only runtime controllers mutate state.

**Why this matters:**
Implicit readiness causes systems to execute when they should not. Explicit state prevents silent failure modes.

### 3. Determinism Over Peak Throughput

This system prefers predictable behavior over raw throughput.

- No sleeps
- No randomness
- No time-based warm-up
- Step-driven execution

**Why this matters:**
Known latency is safer than fast but unpredictable latency. Determinism enables reasoning, testing, and recovery.

### 4. Degrade Before Failing

When the system cannot operate safely, it degrades explicitly instead of crashing or blocking.

- Execution continues
- Decisions are marked provisional
- State is visible to operators
- Recovery is possible

**Why this matters:**
A crashed trading system has zero optionality. A degraded system can still observe, report, and recover.

### 5. Observability Must Not Lie

Observability is best-effort and lossy by design.

- Metrics drop data instead of blocking
- No instrumentation on the hot path
- No conditional checks per event

**Why this matters:**
Metrics that distort latency are worse than missing metrics. Honest observability preserves system behavior.

---

## System Architecture

```
CONTROL PLANE
  ├─ Metrics Aggregation
  ├─ Health & Readiness
  └─ Failure Injection
        │
        ▼
LIFECYCLE STATE
  INIT -> WARMUP -> READY <-> DEGRADED
        │
        ▼
HOT PATH
  Ingest -> Ring Buffer -> Execution -> Ack
        │
        ▼
OBSERVABILITY SINK (optional, non-blocking)
```

Control components influence execution only through lifecycle state. They never touch event data structures.

---

## Execution Path

**1. Market data arrives**
The ingest component receives a tick and wraps it as an event.

**2. Monotonic timestamp captured**
Wall-clock time is banned. All latency is measured using monotonic time only.

**3. Ring buffer publish**
The producer writes and returns immediately. It never blocks.

**4. Consumer poll**
The executor polls non-blocking. Empty polls return immediately.

**5. Lifecycle gate**
Execution decisions depend solely on current lifecycle state.

**6. Ack emission**
Each event produces an acknowledgment containing:
- Sequence number
- Decision timestamp
- Completion timestamp
- Executed or provisional flag

**7. Observability handoff**
The ack is passed to a sink. If observability is disabled, this is a no-op call.

---

## Backpressure and Overrun Semantics

The ring buffer is bounded and overwrite-on-full.

- Producers never block
- Slow consumers miss data
- Data loss is explicit, not silent

### Why the Producer Never Blocks

Blocking producers creates stale market views. Fresh data with gaps is safer than complete data that is late.

### Why Overruns Are Explicit Errors

Silent drops hide system failure. Explicit overruns force acknowledgment of data loss.

---

## Capacity and Stress Characterization

The system was verified using three deterministic experiments with a ring capacity of 64.

| Scenario | Ingest | Consume | Result |
| :--- | :--- | :--- | :--- |
| Balanced | 5 | 5 | Stable, no overruns |
| Producer-Heavy | 8 | 3 | Overrun at step 12 |
| Consumer-Heavy | 3 | 8 | Stable, empty polls |

**Failure math (producer-heavy):**

- Net accumulation: +5 events per step
- Capacity: 64
- Saturation: 64 / 5 = 12.8

Overrun occurs exactly at step 12, reproducible every run.

> This system prioritizes predictability and explicit data loss over blocking or unbounded buffering.

---

## Failure Injection and Recovery

Failures are modeled by lifecycle manipulation, not component breakage.

- Activate failure: transition to DEGRADED
- Deactivate failure: restore previous state
- Execution continues, marked provisional

This mirrors real trading infrastructure behavior where systems degrade rather than crash.

---

## Non-Goals

These exclusions are deliberate:

- No trading strategy
- No exchange connectivity
- No Kubernetes or autoscaling
- No distributed tracing
- No real-time market feeds

Focus is on infrastructure correctness, not surface realism.

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
├── control/                 # CONTROL PLANE
│   ├── failure/             # Failure injection scenarios
│   ├── health/              # Health probes
│   └── metrics/             # Metrics aggregator
├── runtime/                 # PROCESS LIFECYCLE
│   ├── readiness/           # Readiness probe
│   ├── shutdown/            # Graceful shutdown
│   └── warmup/              # Warm-up controller
├── demo/                    # CLI verification scenarios
└── tests/                   # Deterministic test suites
```

---

## Who This Is For

- Low-latency infrastructure engineers
- Trading systems DevOps and SRE roles
- Interviewers evaluating systems design under load and failure

---

## License

MIT License. See LICENSE file.
