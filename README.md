# Low-Latency Trading Infrastructure Simulator

**A deterministic reference architecture for HFT hot-path engineering.**

This project demonstrates how to build reliability into the sub-microsecond critical path. It isolates the infrastructure concerns of a trading system—lifecycle, data distribution, execution safety, and failure recovery—from the trading strategy itself.

It is designed to be read, verify, and understood by engineers who build systems where `p99` latency matters more than throughput.

---

## ⚡ Quick Verification

You don't have to read the code to verify the claims. The system includes a deterministic CLI demo that runs in milliseconds.

```bash
# 1. Prove stable execution (5 ingest/step vs 5 polls/step)
python -m demo balanced

# 2. Prove explicit backpressure (8 ingest/step vs 3 polls/step)
# Watch for "first_overrun_step: 12" — precise mathematical saturation.
python -m demo producer-heavy

# 3. Prove runtime authority
# Watch lifecycle transition READY -> DEGRADED -> READY
python -m demo failure-recovery
```

---

## 🛠 What This Project Demonstrates

This is not a toy backtester. It is a rigorous implementation of **production-grade HFT patterns**:

*   **Zero-Allocation Hot Path**: The critical loop creates zero garbage. No `malloc`, no `new`, no GC pauses.
*   **Wait-Free Ring Buffer**: Single-producer / Multi-consumer layout where the producer *never* blocks. Slow consumers explicitly miss data (overrun) rather than verifying backpressure.
*   **Monotonic Time Only**: Wall-clock time is banned on the hot path to prevent backward jumps during NTP updates.
*   **Explicit Lifecycle**: A formal state machine (`INIT` -> `WARMUP` -> `READY` -> `DEGRADED`) acts as the absolute authority on whether the system is allowed to trade.
*   **Honest Observability**: Metrics are lossy by design. If the metrics subsystem falls behind, it drops data rather than blocking the trading loop.

---

## 🏗 System Architecture

The system enforces a strict separation between the **Control Plane** (slow, safe, allocating) and the **Hot Path** (fast, dangerous, static).

```mermaid
graph TD
    subgraph Control_Plane [Control Plane (Allocating)]
        Metrics[Metrics Aggregator]
        Health[Health Probes]
        Chaos[Chaos Monkey]
    end

    subgraph State [Shared State]
        Lifecycle[(Lifecycle State)]
    end

    subgraph Hot_Path [Hot Path (Zero-Alloc)]
        Ingest[Market Data Ingest]
        Ring((Ring Buffer))
        Exec[Executor]
        Ack[Ack Emitter]
    end

    Control_Plane -- Writes --> Lifecycle
    Lifecycle -- Gates --> Hot_Path
    Ingest -- Publishes --> Ring
    Ring -- Polls --> Exec
    Exec -- Emits --> Ack
    Exec -.-> Metrics
```

### 1. The Hot Path (Execution)
*   **Ingest**: Timestamps raw bytes on arrival.
*   **Ring Buffer**: Fixed-size circular buffer. Power-of-two capacity for bitwise indexing.
*   **Executor**: Polls for storage. Checks `Lifecycle` state (atomic equivalent). Runs logic. Emits result.
*   **Constraint**: If it touches the hot path, it must be `O(1)` and allocation-free.

### 2. The Control Plane (Safety)
*   **Warmup Controller**: Drives the system through a deterministic number of warmup ticks to train JIT/Branch Predictors before setting `READY`.
*   **Failure Injection**: Can force `DEGRADED` state from the outside. The hot path reacts immediately by marking orders as "Provisional" (non-executable).

---

## 📊 Capacity & Stress Characterization

The system's limits are mathematical, not accidental. We verified behavior under three stress conditions using a fixed ring buffer (size 64).

| Scenario | Load Profile | Outcome |
| :--- | :--- | :--- |
| **Balanced** | Ingest == Poll | **Stable**. 0 overruns. |
| **Consumer Lag** | Ingest > Poll | **Predictable Failure**. First overrun exactly at Step 12. |
| **Under-Load** | Ingest < Poll | **Stable**. Clean handling of empty polls. |

### The "Math of Failure"
In the **Consumer Lag** scenario (8 writes vs 3 reads per step), the buffer accumulates **5 events/step**.
With a capacity of **64**, the system MUST overrun at `64 / 5 = 12.8` steps.
The demo proves the first overrun happens at **Step 12**.

> **Design Principle:** We prefer explicit data loss (exception) over implicit latency (blocking). Old news is worse than no news.

---

## 🚫 Non-Goals & Limitations

To maintain clarity, we explicitly exclude complexity that doesn't serve the architectural demonstration:

*   **No Network I/O**: We simulate data arrival. TCP tuning is a different skill set.
*   **No Multi-Host**: Use Kubernetes for that. This deals with single-node mechanical sympathy.
*   **No Trading Strategy**: The "algo" is a dummy function. The focus is on *how* the algo is called, not *what* it does.
*   **Python**: Yes, Python. The patterns (ring buffers, zero-alloc, pre-calc) transfer 1:1 to C++/Rust. We use Python for readability and rapid prototyping of the *architecture*.

---

## License

MIT License. See [LICENSE](LICENSE) file.
