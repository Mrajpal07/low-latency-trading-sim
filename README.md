# Low-Latency Trading Infrastructure Simulator

## Project Overview

This project simulates the **infrastructure layer** of a high-frequency trading system. It focuses on execution mechanics, lifecycle management, and operational behavior that determine whether trades happen reliably and on time. It deliberately ignores trading strategy, market dynamics, and financial logic to focus exclusively on the concerns that HFT DevOps engineers, platform teams, and systems programmers face daily.

### What This System Represents

A real HFT platform is more than algorithms. Before any trading logic runs, infrastructure must ensure that market data arrives with trustworthy timestamps, events fan out to multiple consumers without blocking the critical path, the system knows whether it is healthy enough to execute, failures degrade gracefully rather than crash, and observability exists without adding latency. This simulator models those concerns in isolation, making the architectural patterns visible and testable without the complexity of actual market connectivity or trading logic.

### Who Would Care About This

- **HFT DevOps / SRE engineers** who need to understand how trading infrastructure behaves under pressure
- **Platform engineers** building low-latency event processing systems in any domain
- **Systems programmers** learning patterns that transfer to C++ or Rust implementations
- **Interviewers and candidates** discussing infrastructure design for latency-sensitive applications

### Non-Negotiable Constraints

The hot path, meaning the code that touches every event, must be predictable. This means no locks that could cause contention, no dynamic memory allocation that could trigger garbage collection, no system calls that could block, and no conditional branches based on observability state. These constraints are not optimizations to add later. They are architectural invariants that shape every design decision.

### What This Is Not

This is not a trading strategy backtester, a market simulator with order book dynamics, a distributed system, or production-ready code. It exists as an educational and interview artifact that demonstrates understanding of infrastructure principles, not as something you would deploy.

---

## Design Principles

### 1. Protect the Hot Path

The execution-critical path has exactly one job: process events with minimal, predictable latency. Everything else, including metrics, logging, and health checks, happens elsewhere.

**Why this matters:** In production HFT systems, a single lock acquisition on the hot path can add microseconds of jitter. A garbage collection pause can miss a trading opportunity. By establishing absolute separation between the hot path and supporting infrastructure, we ensure that operational concerns never compete with execution for resources or time.

### 2. Explicit State Over Inference

The system's operational state is always explicit. The lifecycle is a state machine with validated transitions, not a set of boolean flags that might drift out of sync. Components check state. They do not guess.

**Why this matters:** Distributed systems fail in subtle ways when components disagree about system state. A service that thinks it is healthy but is not will accept traffic it cannot handle. By making state explicit and transitions validated, we ensure that every component has the same understanding of whether the system should be executing, warming up, or degraded.

### 3. Determinism Over Throughput

We prefer predictable latency over peak throughput. A system that processes fewer events per second but with consistent timing is more valuable than one with higher throughput and unpredictable spikes.

**Why this matters:** Trading systems make decisions based on timing. If latency varies unpredictably, the system cannot reason about whether its view of the market is current. Known, stable latency, even if higher, enables correct decision-making. Unknown latency makes the system unreliable regardless of average performance.

### 4. Degrade Before Failing

When things go wrong, the system sheds load and signals degradation rather than crashing or lying. Slow consumers get dropped. Execution continues in degraded mode. Metrics report honestly.

**Why this matters:** Markets do not pause for system failures. A crashed trading system loses all optionality and cannot even observe what is happening. A degraded system can still gather data, report its state, and recover when conditions improve. Graceful degradation preserves information and options that hard failures destroy.

### 5. Observability Must Not Lie

Metrics that block the hot path are worse than no metrics. We accept lossy, best-effort aggregation over precise measurements that add latency.

**Why this matters:** The purpose of observability is to understand system behavior. If collecting metrics changes that behavior by adding latency, triggering allocations, or competing for CPU, then the metrics describe a different system than the one running without observation. Honest observability accepts that some data may be lost under stress rather than distorting the system it measures.

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

**Control Plane** contains components that monitor and influence the system but never touch individual events. Metrics aggregation, health probes, and failure injection scenarios all live here. These components can be slow, allocate memory, make system calls, and block because they operate outside the critical path.

**Lifecycle State** is the single source of truth for system operational status. Every component that needs to know whether execution is permitted reads from this state. The state machine enforces valid transitions. You cannot jump from initialization directly to degraded, and you cannot execute during initialization. This layer is minimal. It stores one enum value and validates transitions.

**Hot Path** is where market events flow. Data enters through ingestion, passes through the ring buffer for fan-out to multiple consumers, and reaches the execution consumer that produces acknowledgment records. Every operation here uses monotonic timestamps, avoids locks, and makes no allocations. The hot path is latency-critical and must remain undisturbed.

**Runtime Control** manages process lifecycle concerns that happen outside normal event processing. This includes warming up caches and JIT compilation before accepting traffic, probing readiness for orchestration systems, and coordinating graceful shutdown. These components interact with lifecycle state but never with the hot path directly.

### How Data Flows

Market data enters the system through the ingest component, which stamps each event with a monotonic timestamp at arrival time. Events are published to the ring buffer, which stores them in a fixed-size circular structure. Multiple consumers can read from the buffer independently, each maintaining its own cursor position. The execution consumer reads events, makes execution decisions based on lifecycle state, and produces acknowledgment records that capture both when the decision was made and when processing completed. These acknowledgments flow to an observability sink using the null-object pattern.

### How Control Influences the Hot Path

Control plane components influence the hot path through exactly one mechanism: lifecycle state. The failure injection system transitions the lifecycle to DEGRADED, which causes the executor to process events but mark them as not executed. The warm-up controller transitions from WARMUP to READY when the system is prepared for production traffic. Health probes read lifecycle state to report readiness.

Critically, control plane components never write to hot-path data structures, never inject code into the event processing loop, and never hold locks that hot-path code might need. The influence is indirect and mediated entirely through the validated state machine.

### What Isolation Exists

The architecture enforces strict import boundaries. Hot-path code in the core layer cannot import from control or runtime layers. This is not a convention. It is verified by tests that parse the abstract syntax tree of every source file. If hot-path code accidentally imports a control-plane module, tests fail.

The observability sink illustrates this isolation. The sink protocol is defined in the core layer because the executor needs to call it. But actual sink implementations that aggregate metrics live in the control layer. The executor receives a sink through dependency injection and calls its method on every event. If no real observability is configured, it receives a no-op implementation that compiles to nearly zero instructions.

This layering ensures that changes to metrics collection, health checking, or failure injection cannot accidentally add latency to event processing.

---

## Execution Hot Path Walkthrough

This section traces a single market event from arrival to completion. Understanding this flow is essential because every design decision in the system exists to protect it.

### Step 1: Market Data Arrives

An external market data tick arrives at the ingest component. This is where the event enters the system boundary.

**What happens:** The ingest component receives raw market data and wraps it in an event structure.

**What is avoided:** No parsing of complex formats on the hot path. No validation that could block. No logging that could trigger I/O.

**Latency implications:** This is the first moment we can measure. Any delay here propagates through the entire pipeline.

### Step 2: Timestamp Capture

Before anything else, the event receives a monotonic timestamp.

**What happens:** The system calls the monotonic clock and records the arrival time in nanoseconds. This timestamp becomes the reference point for all latency calculations.

**What is avoided:** Wall clock time is never used on the hot path. Wall clocks can jump backwards during NTP adjustments or leap seconds. Monotonic clocks only move forward.

**Latency implications:** Timestamp capture must happen immediately. If we defer it, we lose the ability to measure true arrival-to-decision latency.

### Step 3: Ring Buffer Publish

The timestamped event is published to the ring buffer for distribution to consumers.

**What happens:** The producer writes the event to the next slot in the circular buffer and advances the head pointer. The publish operation returns immediately with a sequence number.

**What is avoided:** The producer never blocks. It does not wait for consumers to catch up. It does not check if consumers have read previous events. It simply writes and moves on.

**Latency implications:** This is the fan-out point. Multiple consumers can process the same event independently. The ring buffer's bounded size means memory access patterns are predictable and cache-friendly.

### Step 4: Consumer Poll

The execution consumer polls the ring buffer for new events.

**What happens:** The consumer checks if any events are available beyond its current cursor position. If an event exists, it reads the data. If not, it returns immediately with no event.

**What is avoided:** No blocking waits. No condition variables. No sleeping. The poll is a simple comparison and read.

**Latency implications:** Polling must be non-blocking because the consumer might need to do other work between events. A blocking read would prevent responsive behavior during quiet periods.

### Step 5: Execution Decision

The executor evaluates whether to execute based on current lifecycle state.

**What happens:** The executor reads the current lifecycle state. If the state is READY, the execution decision is marked as live. If the state is WARMUP or DEGRADED, processing continues but the decision is marked as provisional.

**What is avoided:** The state check is a single enum comparison. There are no locks protecting the state read. The lifecycle state machine is designed so that stale reads are safe.

**Latency implications:** This is where the system decides whether to trust its own output. The state check adds essentially zero latency but provides critical safety guarantees.

### Step 6: Ack Emission

The executor produces an acknowledgment record with timing information.

**What happens:** The ack captures the original event sequence number, a decision timestamp showing when the execution logic ran, a completion timestamp showing when the ack was constructed, and a flag indicating whether this was a real execution or a provisional one.

**What is avoided:** No allocation for the ack structure. Acks use a fixed layout with pre-allocated fields. No serialization happens on the hot path.

**Latency implications:** The two timestamps in the ack allow precise measurement of decision latency versus total processing latency. This distinction matters for debugging slow paths.

### Step 7: Observability Handoff

The event and ack pair are passed to the observability sink.

**What happens:** The executor calls the sink's observe method with the event and ack. If a real sink is configured, it records the observation. If no sink is configured, the call goes to a no-op implementation.

**What is avoided:** No conditional check for whether observability is enabled. The null-object pattern means the call always happens. The branching is eliminated at configuration time, not runtime.

**Latency implications:** Observability is the final step specifically because it is the most likely to introduce latency. By placing it after the execution decision, we ensure that observation overhead never delays the actual trading logic.

---

## Lifecycle and Runtime Control

The lifecycle state machine is how the system knows what it should be doing. It separates the concerns of being ready to execute from the mechanics of actually executing.

### The Four States

**INIT** is the starting state. The system has just been created. Nothing is ready. Caches are empty. No events should be processed. Attempting to execute from INIT is an error that raises an exception.

**WARMUP** means the system is preparing for production traffic. Events can flow through the pipeline, but execution decisions are marked as provisional. This state exists because cold systems behave differently than warm ones. CPU branch predictors are untrained. JIT compilation has not optimized the hot paths. Memory pages are not in cache. Measurements during warmup are unreliable and should not be trusted.

**READY** means the system is prepared for production execution. Latency characteristics have stabilized. Cache hierarchies are warm. The system can make real execution decisions. This is the only state where the executed flag on acks is set to true.

**DEGRADED** means something is wrong but the system is still operational. A market data feed might be stale. A downstream dependency might be slow. The system continues processing to gather information and maintain the ability to recover, but execution decisions are marked as provisional just like during warmup.

### Valid Transitions

Not all state changes are allowed. The state machine enforces specific transition rules.

From INIT, you can only go to WARMUP. This is the system starting up.

From WARMUP, you can go to READY when warmup completes successfully, or to DEGRADED if something fails during warmup.

From READY, you can go to DEGRADED when a failure is detected.

From DEGRADED, you can go to READY when the failure is resolved, or back to WARMUP if a full restart is required.

You cannot go directly from INIT to READY. You cannot go directly from INIT to DEGRADED. These transitions would skip necessary initialization steps. Attempting an invalid transition raises an exception.

### Who Mutates State

Only runtime control components are allowed to change lifecycle state. The warmup controller transitions from INIT to WARMUP and from WARMUP to READY. The failure injection scenarios transition to and from DEGRADED. The shutdown controller manages graceful termination.

Hot-path components never mutate state. They only read it. This separation ensures that execution code cannot accidentally put the system into an invalid state. The hot path trusts that whatever state it reads was set deliberately by a component designed to manage transitions.

### Why Warmup is Deterministic

The warmup process is step-based rather than time-based. The controller ticks through a fixed number of steps, and warmup completes when all steps finish. This makes warmup behavior reproducible.

Time-based warmup would be non-deterministic. A system that warms up for 30 seconds might be ready on one machine but still cold on another. A system that warms up for 1000 ticks produces the same behavior everywhere. Tests can verify warmup logic without waiting for real time to pass.

### Why Readiness is Binary

The readiness probe returns a simple yes or no. Either the system is ready for traffic or it is not.

This binary answer exists because load balancers and orchestration systems need clear signals. A system that reports partial readiness creates ambiguity. Should the load balancer send 50% of traffic? How should Kubernetes interpret a 70% ready response?

By making readiness binary, we force the decision logic to be explicit. The system is READY, or it is not. There is no middle ground that could lead to inconsistent routing decisions.

---

## Backpressure and Overrun Semantics

Most systems handle backpressure by slowing down producers when consumers cannot keep up. This simulator does the opposite. Understanding why is key to understanding low-latency infrastructure design.

### Why the Producer Never Blocks

In a traditional queue, when the buffer fills up, the producer waits. This protects consumers from being overwhelmed but creates a serious problem: the producer's latency becomes unpredictable. If the producer is ingesting market data, blocking means market data backs up. Stale market data is worse than no market data because it creates a false picture of current prices.

The ring buffer design ensures that publishing always succeeds immediately. The producer writes to the next slot, advances the head pointer, and returns. If a consumer has not read the data in that slot, the data is overwritten. The producer does not know or care.

This design choice reflects a fundamental priority: fresh data matters more than complete data. A trading system that sees current prices but misses some historical ticks is more useful than one that sees complete history but is always behind.

### Why Slow Consumers Miss Data

When a consumer falls behind and its cursor points to data that has been overwritten, it receives an explicit overrun error. The consumer knows it missed data. It can then decide how to recover.

The alternative would be to buffer unlimited data until the consumer catches up. This creates memory pressure, increases latency for all consumers, and eventually fails anyway when memory runs out. Explicit overrun is honest about what happened and gives the consumer a chance to respond appropriately.

A slow consumer might reset its cursor to the current head, accepting the gap and resuming with fresh data. It might log the overrun for later analysis. It might signal degradation to upstream systems. What it cannot do is pretend nothing happened.

### Why Overruns Are Explicit Errors

Some ring buffer implementations silently drop data when consumers fall behind. The consumer keeps reading but never knows it missed anything. This is dangerous because it creates silent data loss.

In a trading system, silent data loss means the system's view of the market silently diverges from reality. Trades might be made based on stale information without any indication that the information is stale.

By making overrun an explicit exception, we force the system to acknowledge the problem. The exception propagates up the call stack. Error handling code runs. Metrics are recorded. Operators are alerted. The system cannot pretend everything is fine when it is not.

### Why This Is Safer Than Buffering

Unbounded buffering feels safer because no data is lost. But unbounded buffering trades immediate data loss for delayed system failure. The buffer grows until memory is exhausted. Garbage collection pauses increase. Latency becomes unpredictable. Eventually the system crashes anyway, but now it has also been lying about its health the entire time.

Bounded ring buffers with explicit overrun provide predictable behavior. Memory usage is constant. Latency is bounded. When the system cannot keep up, it says so immediately. Operators can respond to degradation signals rather than discovering problems only when the system finally collapses.

This is why the ring buffer design is fundamental to the simulator. It demonstrates that protecting the producer and accepting data loss in slow consumers is not a compromise. It is the correct design for latency-sensitive systems.

---

## Observability Without Latency Pollution

Observability is essential for operating any system. But in low-latency systems, naive observability implementations become the problem they are trying to solve. This section explains how the simulator achieves observability without polluting the hot path.

### Why No Logging on the Hot Path

Logging looks harmless. A single log statement seems like it cannot possibly matter. But logging involves string formatting, which allocates memory. It involves I/O, which can block. It involves locks if multiple threads share a log destination. Each of these effects is invisible in normal operation but catastrophic under load.

The hot path in this simulator contains zero log statements. If something goes wrong during event processing, the system does not log it inline. Instead, it records the problem in a way that can be observed later without affecting the current event. This might mean incrementing a counter, setting a flag, or simply letting the ack record indicate that something was wrong.

Logging happens in the control plane. Health probes can log. Metrics aggregators can log. Failure injection scenarios can log. These components are not latency-sensitive, so logging overhead is acceptable there.

### Why Metrics Are Lossy

Traditional metrics systems aim for accuracy. Every event is counted. Every latency is recorded. This precision comes at a cost: the metrics collection itself becomes a bottleneck.

The simulator accepts lossy metrics. Under normal load, metrics are accurate. Under extreme load, some observations may be dropped. This is acceptable because the alternative is worse. Precise metrics that slow down the system distort the very measurements they are trying to capture. Lossy metrics that do not affect performance give an honest picture of system behavior, even if that picture has some gaps.

The metrics aggregator uses techniques that avoid allocations on the observe path. It does not use locks. It does not buffer observations. It simply updates counters and running totals that can be read later. If the aggregator falls behind, it drops data rather than blocking the caller.

### Why Observability Is Optional

Not every deployment needs observability. A test environment might run with no metrics collection at all. A production environment might use a sophisticated observability pipeline. The hot path should not need to know or care which environment it is running in.

The simulator makes observability optional through dependency injection. The executor receives a sink at construction time. If no sink is provided, it receives a no-op implementation. The executor does not check which kind of sink it has. It simply calls the observe method and trusts that the sink will do the right thing.

This design means that observability can be enabled, disabled, or replaced without modifying hot-path code. Different deployments can use different observability backends. New observability features can be added without risk to the execution path.

### Why Null-Object Wiring Is Used

The obvious way to make observability optional is to check for it on every event. If a sink exists, call it. If not, skip the call. This approach adds a conditional branch to every event, which affects CPU branch prediction and adds latency even when the branch is not taken.

The null-object pattern eliminates this branch. The executor always has a sink. It always calls the sink. When observability is disabled, the sink is a no-op implementation whose observe method does nothing and returns immediately. The method call overhead is minimal and predictable. There is no branch to mispredict.

This pattern appears throughout the simulator wherever optional behavior exists. Instead of checking for null references or optional flags, the system uses polymorphism to eliminate conditionals from the hot path.

### Correctness Over Completeness

The fundamental tradeoff in low-latency observability is between correctness and completeness. A system can have perfectly accurate metrics that distort its behavior, or it can have approximate metrics that leave behavior undisturbed.

This simulator chooses correctness. The metrics it reports accurately reflect the behavior of the system when not being observed. Some data points may be missing under extreme load, but the data points that exist are trustworthy. An operator looking at the metrics sees what the system is actually doing, not what it would do if it were not being measured.

This is the only honest approach for latency-sensitive systems. Observability that changes behavior is not observability. It is interference.

---

## Failure Injection and Degradation

Testing failure handling requires the ability to inject failures deterministically. This section explains how the simulator models failures and why it uses lifecycle manipulation rather than component-level chaos.

### Why Failures Manipulate Lifecycle, Not Components

One approach to failure injection is to directly break components. Throw exceptions from the ingest layer. Corrupt data in the ring buffer. Make the executor crash. This approach creates realistic failure symptoms but makes testing difficult because the failures are unpredictable and hard to verify.

The simulator takes a different approach. Failure scenarios manipulate lifecycle state, not components. When a market data outage is simulated, the scenario transitions the lifecycle to DEGRADED. The ingest component continues working normally. The ring buffer is unaffected. Only the lifecycle state changes.

This approach works because all components already check lifecycle state. They already know how to behave differently in DEGRADED mode. Failure injection simply triggers the degradation path that already exists for handling real failures. The same code paths that handle production failures are exercised during testing.

This design also makes failures reversible. Activating a failure scenario is a state transition. Deactivating it is another state transition. The system cleanly enters and exits degraded mode without lingering effects from simulated component damage.

### What Happens on Ingest Failure

When market data ingestion fails in a real system, the trading system loses its view of current prices. It cannot make informed execution decisions because it does not know what the market looks like.

In the simulator, an ingest failure is modeled as a transition to DEGRADED state. The lifecycle changes, and all components observe this change. The executor continues processing any events already in the ring buffer, but it marks all execution decisions as provisional. The acks it produces have their executed flag set to false.

This models the real-world response: the system does not crash, but it also does not pretend it can make reliable decisions. It continues operating in a reduced capacity, gathering whatever information it can while signaling that its outputs should not be trusted.

### What Happens on Execution Failure

Execution failures are different from ingest failures. The system might still have good market data, but something is wrong with the execution path itself. Maybe a downstream system is unresponsive. Maybe an internal consistency check failed.

The simulator models execution failure the same way: a transition to DEGRADED state. The distinction between ingest failure and execution failure exists at the scenario level, not the state level. Both result in DEGRADED state because the system response is the same: continue processing, mark decisions as provisional, wait for recovery.

This simplification is intentional. Real systems might have more fine-grained degradation modes, but the fundamental pattern is the same. The system must distinguish between healthy operation and degraded operation. The specific cause of degradation matters for diagnosis but not for immediate operational response.

### How Recovery Works

Recovery is the inverse of failure. When a failure scenario is deactivated, the system transitions back to its previous state. If it was READY before the failure, it returns to READY. If it was in WARMUP when the failure occurred, it returns to WARMUP.

This state preservation is explicit. The failure scenario stores the previous state when it activates and restores it when it deactivates. This allows multiple failure and recovery cycles without state drift.

Recovery is also idempotent. Deactivating an already-inactive scenario has no effect. This prevents accidental state transitions from repeated recovery attempts.

### What Is Intentionally Not Simulated

The simulator does not model all possible failures. Some failure modes are excluded because they would require infrastructure that does not exist in the simulator. Others are excluded because they would not teach anything useful about the architecture.

Network partitions are not simulated because the simulator has no network layer. Disk failures are not simulated because the hot path has no persistence. Memory corruption is not simulated because detecting and handling memory corruption requires hardware support that Python cannot access.

Cascading failures across distributed components are not simulated because the simulator is a single-host system. Partial failures where some consumers are healthy and others are not are not simulated because modeling this correctly would require a more sophisticated consumer management system.

These exclusions are explicit. The simulator does not pretend to handle failures it cannot model. This prevents false confidence about failure handling capabilities.

---

## Capacity Model and Known Limits

Before measuring performance, it is important to understand what the system can and cannot do. This section documents the structural constraints that limit capacity.

### Single Producer Assumption

The ring buffer assumes a single producer. This is not a limitation to be fixed. It is a design decision that enables lock-free publishing. Multiple producers would require synchronization to coordinate access to the head pointer, and that synchronization would add latency.

Real HFT systems typically have a single ingest point per market data source. The single-producer model reflects this reality. If multiple data sources need to be combined, they are merged before entering the ring buffer, not inside it.

### Single Execution Consumer

The simulator has one execution consumer. This consumer processes events sequentially. There is no parallel execution of the decision logic.

This constraint exists because parallel execution introduces complexity that obscures the architectural patterns. Order-dependent processing, result aggregation, and resource contention would need to be addressed. The simulator focuses on the mechanics of a single execution path rather than the challenges of parallelism.

Production systems might use multiple execution consumers, but they typically partition work by symbol or market rather than processing the same events in parallel. The single-consumer model captures the essential behavior.

### Python Overhead Reality

Python is not a low-latency language. Function call overhead, dynamic dispatch, garbage collection, and the global interpreter lock all add latency that would not exist in a C++ or Rust implementation. The simulator does not pretend otherwise.

The absolute performance numbers from this simulator are not meaningful for comparison with production systems. What matters is the relative performance: how does latency change as load increases? Where do bottlenecks appear? How does the system behave as it approaches its limits?

The architectural patterns demonstrated here transfer to faster languages, but the numbers do not.

### Vertical Scaling Bias

The simulator is designed for vertical scaling. Making it faster means using a faster machine with more memory and faster CPUs. There is no mechanism for distributing work across multiple hosts.

This bias is intentional. Distributed systems introduce latency for coordination that defeats the purpose of low-latency design. Real HFT systems minimize distribution. They run on single servers with direct market connections. They scale vertically as far as possible before considering distribution.

The simulator reflects this bias. It does not include any mechanisms for clustering, sharding, or distributed coordination. These would be distractions from the core architectural patterns.

### Preliminary Status

This capacity model will be refined as testing proceeds. The constraints documented here are structural. The actual throughput and latency numbers will be measured in subsequent phases. This section establishes what can be measured, not what the measurements are.

---

## Non-Goals

This section explicitly states what the simulator does not do. These exclusions are deliberate. They prevent scope creep and focus attention on the core concerns.

### No Trading Strategy

The simulator has no concept of trading strategy. It does not know what a buy order is. It does not know what a sell order is. It does not know about positions, risk limits, or profit and loss.

Events are opaque data structures with timestamps. The execution consumer does not interpret them. It simply processes them and produces acknowledgment records. Any trading logic would be added outside the simulator's scope.

This exclusion exists because trading strategy is a separate concern from infrastructure. The infrastructure should work regardless of what strategy runs on top of it. By excluding strategy, the simulator can focus on the platform concerns that strategies depend on.

### No Exchange Connectivity

The simulator does not connect to real exchanges. It does not speak FIX protocol. It does not have market data adapters for specific venues. It does not send orders anywhere.

Real exchange connectivity requires network infrastructure, protocol handling, and venue-specific logic. These are complex systems in their own right. Including them would shift focus away from the core architectural patterns.

The simulator's ingest component produces synthetic market events. The execution consumer produces acknowledgment records that go nowhere. This is sufficient to demonstrate the infrastructure patterns without the complexity of real connectivity.

### No Kubernetes

The simulator does not include Kubernetes manifests, Helm charts, or container orchestration logic. It does not have liveness probes formatted for Kubernetes health checks. It does not integrate with service meshes.

This exclusion exists because Kubernetes orchestration is orthogonal to low-latency infrastructure design. The patterns demonstrated here would work on Kubernetes, on bare metal, or in any other deployment environment. Including Kubernetes-specific integration would couple the simulator to a specific deployment model.

The readiness probe provides a simple boolean that any orchestration system can query. How that query happens is outside the simulator's scope.

### No Distributed Tracing

The simulator does not integrate with Jaeger, Zipkin, or other distributed tracing systems. It does not propagate trace contexts. It does not emit spans.

Distributed tracing is designed for request-response systems with moderate latency budgets. The overhead of creating and propagating trace contexts is acceptable in web services but problematic in HFT infrastructure. The simulator uses monotonic timestamps for latency attribution rather than distributed tracing.

If distributed tracing were needed, it would be added as an observability sink implementation in the control plane, not integrated into the hot path.

### No Auto-Scaling

The simulator does not scale automatically based on load. It does not have a metrics-based autoscaler. It does not integrate with cloud provider APIs for adding or removing capacity.

Auto-scaling is an anti-pattern for low-latency systems. Scaling events introduce latency spikes as new instances warm up. The time to provision new capacity is often longer than the time window where capacity is needed. Latency-sensitive systems provision for peak load and accept underutilization during quiet periods.

The simulator reflects this approach. It has fixed capacity determined at startup. It does not attempt to adjust capacity dynamically.

---

## How to Read and Extend This System

This section provides guidance for understanding the codebase and making changes safely.

### Where to Add New Consumers

New consumers of market events should follow the existing consumer pattern. Create a consumer from the ring buffer. Poll for events in a loop. Process events according to the consumer's purpose.

New consumers belong in the core layer if they are latency-sensitive, or in the control layer if they are not. An analytics consumer that aggregates statistics would go in control. A hedging consumer that needs to react quickly would go in core.

Each consumer maintains its own cursor. Consumers do not interfere with each other. Adding a new consumer does not affect the behavior of existing consumers, except that more consumers increase the chance that slow consumers will experience overruns.

### Where Policy Lives

Policy decisions, meaning the rules that govern system behavior, live in specific locations depending on their nature.

Lifecycle policies live in the state module. The valid transitions, the initial state, and the rules for what each state means are all defined there.

Operational policies live in the runtime layer. When to transition from warmup to ready, how to determine if the system is healthy, and when to initiate shutdown are all runtime concerns.

Hot-path policies live in the core layer. How to handle overruns, when to emit timestamps, and what to include in acknowledgment records are all decided there.

Configuration policies live in the config layer. Default values, tunable parameters, and environment-specific settings belong there.

### Where Changes Are Forbidden

Some areas of the codebase should not be changed without extreme care.

The ring buffer implementation in core/bus should not be modified casually. It is the foundation of the fan-out mechanism. Changes here affect every consumer and every event.

The lifecycle state machine in core/state should not be extended with new states without careful thought about all the places that check state. Adding a new state is not just adding an enum value. It requires auditing every state check in the system.

The timestamp functions in core/time should not be replaced with alternative implementations. The choice of monotonic time over wall time is fundamental. Changing this would invalidate all the latency reasoning in the system.

Import boundaries should never be violated. If you find yourself wanting to import a control-layer module from core, stop. The design needs to change so that the dependency flows the other way or does not exist at all.

### Signs of Architectural Drift

Watch for these warning signs that the architecture is being compromised:

Conditionals appearing on the hot path that check configuration values at runtime. These should be resolved at initialization time through dependency injection.

Locks appearing anywhere in the core layer. The core layer should be lock-free. If coordination is needed, it should happen in the control or runtime layers.

Log statements appearing in core layer code. Logging belongs in the control plane.

New dependencies from core to control or runtime. The dependency direction should always be into core, never out of it.

Growing complexity in the lifecycle state machine. The four states exist for specific reasons. Adding states to handle special cases usually indicates that the special case should be handled differently.

If you notice any of these patterns emerging, pause and reconsider the approach. The architecture is designed to make certain kinds of changes easy and other kinds of changes impossible. Fighting the architecture usually means the change does not belong where you are trying to put it.

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

1. **How do you prevent slow consumers from affecting producers?**
   The ring buffer design ensures producers never block. Consumers read independently with their own cursors, and if they fall behind, they receive explicit notification rather than blocking the producer.

2. **How do you handle failure without crashing?**
   The lifecycle state machine supports graceful degradation. Components check state before executing and adjust behavior accordingly, continuing to process while signaling that execution decisions are provisional.

3. **How do you add observability without adding latency?**
   The null-object pattern means observability calls are always made, but when disabled, they resolve to empty implementations. No conditional branches check whether observability is enabled on every event.

4. **Why not use a queue?**
   Queues can block producers when full. Ring buffers have bounded, predictable behavior. The producer always succeeds, and consumers either keep up or receive explicit overrun notification.

5. **What is the difference between WARMUP and READY?**
   During warm-up, caches are cold, JIT compilation is incomplete, and branch predictors are untrained. Measurements during warm-up do not reflect steady-state performance. READY means the system's latency characteristics have stabilized.

6. **How do you test failure scenarios without randomness?**
   Failure scenarios are explicit objects with deterministic activation and deactivation. Tests control exactly when failures occur, making failure behavior reproducible and verifiable.

---

## License

MIT License. See LICENSE file.
