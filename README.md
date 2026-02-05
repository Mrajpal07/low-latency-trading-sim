# Low-Latency Trading Infrastructure Simulator

## Project Overview

This project simulates the **infrastructure layer** of a high-frequency trading system—the execution mechanics, lifecycle management, and operational behavior that determine whether trades happen reliably and on time. It deliberately ignores trading strategy, market dynamics, and financial logic to focus exclusively on the concerns that HFT DevOps engineers, platform teams, and systems programmers face daily.

### What This System Represents

A real HFT platform is more than algorithms. Before any trading logic runs, infrastructure must ensure that market data arrives with trustworthy timestamps, events fan out to multiple consumers without blocking the critical path, the system knows whether it's healthy enough to execute, failures degrade gracefully rather than crash, and observability exists without adding latency. This simulator models those concerns in isolation, making the architectural patterns visible and testable without the complexity of actual market connectivity or trading logic.

### Who Would Care About This

- **HFT DevOps / SRE engineers** who need to understand how trading infrastructure behaves under pressure
- **Platform engineers** building low-latency event processing systems in any domain
- **Systems programmers** learning patterns that transfer to C++ or Rust implementations
- **Interviewers and candidates** discussing infrastructure design for latency-sensitive applications

### Non-Negotiable Constraints

The hot path—the code that touches every event—must be predictable. This means no locks that could cause contention, no dynamic memory allocation that could trigger garbage collection, no system calls that could block, and no conditional branches based on observability state. These constraints are not optimizations to add later; they are architectural invariants that shape every design decision.

### What This Is Not

This is not a trading strategy backtester, a market simulator with order book dynamics, a distributed system, or production-ready code. It exists as an educational and interview artifact that demonstrates understanding of infrastructure principles, not as something you would deploy.

---

## Design Principles

### 1. Protect the Hot Path

The execution-critical path has exactly one job: process events with minimal, predictable latency. Everything else—metrics, logging, health checks—happens elsewhere.

**Why this matters:** In production HFT systems, a single lock acquisition on the hot path can add microseconds of jitter. A garbage collection pause can miss a trading opportunity. By establishing absolute separation between the hot path and supporting infrastructure, we ensure that operational concerns never compete with execution for resources or time.

### 2. Explicit State Over Inference

The system's operational state is always explicit. The lifecycle is a state machine with validated transitions, not a set of boolean flags that might drift out of sync. Components check state; they don't guess.

**Why this matters:** Distributed systems fail in subtle ways when components disagree about system state. A service that *thinks* it's healthy but isn't will accept traffic it can't handle. By making state explicit and transitions validated, we ensure that every component has the same understanding of whether the system should be executing, warming up, or degraded.

### 3. Determinism Over Throughput

We prefer predictable latency over peak throughput. A system that processes fewer events per second but with consistent timing is more valuable than one with higher throughput and unpredictable spikes.

**Why this matters:** Trading systems make decisions based on timing. If latency varies unpredictably, the system cannot reason about whether its view of the market is current. Known, stable latency—even if higher—enables correct decision-making. Unknown latency makes the system unreliable regardless of average performance.

### 4. Degrade Before Failing

When things go wrong, the system sheds load and signals degradation rather than crashing or lying. Slow consumers get dropped. Execution continues in degraded mode. Metrics report honestly.

**Why this matters:** Markets don't pause for system failures. A crashed trading system loses all optionality—it cannot even observe what's happening. A degraded system can still gather data, report its state, and recover when conditions improve. Graceful degradation preserves information and options that hard failures destroy.

### 5. Observability Must Not Lie

Metrics that block the hot path are worse than no metrics. We accept lossy, best-effort aggregation over precise measurements that add latency.

**Why this matters:** The purpose of observability is to understand system behavior. If collecting metrics changes that behavior—by adding latency, triggering allocations, or competing for CPU—then the metrics describe a different system than the one running without observation. Honest observability accepts that some data may be lost under stress rather than distorting the system it measures.

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

### What Each Layer Represents

**Control Plane** contains components that monitor and influence the system but never touch individual events. Metrics aggregation, health probes, and failure injection scenarios all live here. These components can be slow, allocate memory, make system calls, and block—because they operate outside the critical path.

**Lifecycle State** is the single source of truth for system operational status. Every component that needs to know whether execution is permitted reads from this state. The state machine enforces valid transitions: you cannot jump from initialization directly to degraded, and you cannot execute during initialization. This layer is minimal—it stores one enum value and validates transitions.

**Hot Path** is where market events flow. Data enters through ingestion, passes through the ring buffer for fan-out to multiple consumers, and reaches the execution consumer that produces acknowledgment records. Every operation here uses monotonic timestamps, avoids locks, and makes no allocations. The hot path is latency-critical and must remain undisturbed.

**Runtime Control** manages process lifecycle concerns that happen outside normal event processing: warming up caches and JIT compilation before accepting traffic, probing readiness for orchestration systems, and coordinating graceful shutdown. These components interact with lifecycle state but never with the hot path directly.

### How Data Flows

Market data enters the system through the ingest component, which stamps each event with a monotonic timestamp at arrival time. Events are published to the ring buffer, which stores them in a fixed-size circular structure. Multiple consumers can read from the buffer independently, each maintaining its own cursor position. The execution consumer reads events, makes execution decisions based on lifecycle state, and produces acknowledgment records that capture both when the decision was made and when processing completed. These acknowledgments flow to an observability sink using the null-object pattern.

### How Control Influences the Hot Path

Control plane components influence the hot path through exactly one mechanism: lifecycle state. The failure injection system transitions the lifecycle to DEGRADED, which causes the executor to process events but mark them as not executed. The warm-up controller transitions from WARMUP to READY when the system is prepared for production traffic. Health probes read lifecycle state to report readiness.

Critically, control plane components never write to hot-path data structures, never inject code into the event processing loop, and never hold locks that hot-path code might need. The influence is indirect and mediated entirely through the validated state machine.

### What Isolation Exists

The architecture enforces strict import boundaries. Hot-path code in the core layer cannot import from control or runtime layers. This is not a convention—it is verified by tests that parse the abstract syntax tree of every source file. If hot-path code accidentally imports a control-plane module, tests fail.

The observability sink illustrates this isolation. The sink protocol is defined in the core layer because the executor needs to call it. But actual sink implementations that aggregate metrics live in the control layer. The executor receives a sink through dependency injection and calls its method on every event—if no real observability is configured, it receives a no-op implementation that compiles to nearly zero instructions.

This layering ensures that changes to metrics collection, health checking, or failure injection cannot accidentally add latency to event processing.

---

## Failure & Degradation Behavior

The system handles failure through explicit state transitions rather than exceptions or crashes.

**Slow consumers** that fall behind the ring buffer receive an explicit overrun signal when they try to read data that has been overwritten. They can recover by resetting their cursor to the current buffer head, accepting that some events were missed.

**External failures** like market data outages trigger lifecycle transitions to DEGRADED state. In this state, the system continues processing events but marks execution decisions as provisional. When the failure clears, the system transitions back to READY.

**Cold starts** go through a mandatory warm-up phase. During warm-up, caches are cold, branch predictors are untrained, and latency measurements are unreliable. The system processes events during warm-up but does not trust its own timing. Only after warm-up completes does the system transition to READY for production execution.

**Invalid operations** like attempting to execute during initialization raise explicit exceptions. The system refuses to silently do the wrong thing—it fails loudly when preconditions are violated.

The philosophy is that degradation preserves options while failure destroys them. A degraded system can observe, report, and recover. A crashed system cannot.

---

## Limitations and Honest Assessment

This system demonstrates understanding of low-latency principles, not production performance. It runs in Python, which means function call overhead, garbage collection pauses, and the global interpreter lock all prevent true low-latency execution. A production HFT system would use C++ or Rust for the hot path, pin threads to CPU cores, use huge pages and NUMA-aware allocation, and bypass the kernel for network I/O.

What transfers from this project is not the absolute performance numbers but the architectural patterns: ring buffers for bounded fan-out, state machines for lifecycle management, null-object patterns for zero-cost abstraction, and strict layering to protect critical paths. These patterns apply regardless of implementation language.

The single-threaded model is also a deliberate simplification. Real systems use thread-per-core designs with careful memory isolation. This simulator avoids threading to keep the architectural patterns clear and to avoid false claims about lock-free behavior that Python cannot actually deliver.

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

## Questions This System Can Answer

For interviews or design discussions:

1. **"How do you prevent slow consumers from affecting producers?"**
   The ring buffer design ensures producers never block. Consumers read independently with their own cursors, and if they fall behind, they receive explicit notification rather than blocking the producer.

2. **"How do you handle failure without crashing?"**
   The lifecycle state machine supports graceful degradation. Components check state before executing and adjust behavior accordingly, continuing to process while signaling that execution decisions are provisional.

3. **"How do you add observability without adding latency?"**
   The null-object pattern means observability calls are always made—but when disabled, they resolve to empty implementations. No conditional branches check whether observability is enabled on every event.

4. **"Why not use a queue?"**
   Queues can block producers when full. Ring buffers have bounded, predictable behavior: the producer always succeeds, and consumers either keep up or receive explicit overrun notification.

5. **"What's the difference between WARMUP and READY?"**
   During warm-up, caches are cold, JIT compilation is incomplete, and branch predictors are untrained. Measurements during warm-up do not reflect steady-state performance. READY means the system's latency characteristics have stabilized.

6. **"How do you test failure scenarios without randomness?"**
   Failure scenarios are explicit objects with deterministic activation and deactivation. Tests control exactly when failures occur, making failure behavior reproducible and verifiable.

---

## License

MIT License. See LICENSE file.
