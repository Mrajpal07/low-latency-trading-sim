from dataclasses import dataclass, asdict, field
from typing import List, Any
import json

from core.state import Lifecycle, State
from core.bus import RingBuffer, Overrun
from core.ingest import MarketDataSource
from core.execution import Executor, Ack
from control.metrics import Metrics, Snapshot
from runtime.warmup import WarmUpController
from control.failure import MarketDataOutage


@dataclass
class StepResult:
    step_index: int
    lifecycle_state: str
    ingest_calls: int
    execution_polls: int
    acks_produced: int
    overruns: int
    metrics_snapshot: Snapshot


@dataclass
class ExperimentSummary:
    steps: List[StepResult] = field(default_factory=list)


class MetricsAdapter:
    """Adapts Executor sink protocol to Metrics aggregator."""
    def __init__(self, metrics: Metrics):
        self._metrics = metrics

    def observe(self, event: Any, ack: Ack) -> None:
        # Measure total pipeline latency: completion - decision (as a proxy for hot path work)
        # Using decision_ts to completion_ts captures the execution cost.
        latency = ack.completion_ts - ack.decision_ts
        self._metrics.observe(latency)


class CapacityHarness:
    RING_CAPACITY = 64
    WARMUP_TICKS = 10
    INGEST_TICKS_PER_STEP = 5
    EXECUTION_POLLS_PER_STEP = 5
    TOTAL_STEPS = 50

    def run(self) -> ExperimentSummary:
        # Initialize
        lifecycle = Lifecycle()
        ring = RingBuffer[Any](self.RING_CAPACITY)
        source = MarketDataSource(lifecycle)
        metrics = Metrics()
        adapter = MetricsAdapter(metrics)
        executor = Executor(ring, lifecycle, sink=adapter)
        
        warmup_ctrl = WarmUpController(lifecycle, steps=self.WARMUP_TICKS)
        failure_ctrl = MarketDataOutage(lifecycle)
        
        summary = ExperimentSummary()

        # Phase 1: INIT -> WARMUP
        warmup_ctrl.start()

        for step_i in range(self.TOTAL_STEPS):
            # Lifecycle Management
            # 0-9: WARMUP
            # 10: Transition to READY
            # 40: Transition to DEGRADED
            
            if step_i < self.WARMUP_TICKS:
                warmup_ctrl.tick()
            elif step_i == self.WARMUP_TICKS:
                warmup_ctrl.complete()
            elif step_i == 40:
                failure_ctrl.activate()

            # Balanced Load Execution
            # Ingest
            for _ in range(self.INGEST_TICKS_PER_STEP):
                event = source.emit()
                ring.publish(event)

            # Poll
            acks_count = 0
            overruns_count = 0
            for _ in range(self.EXECUTION_POLLS_PER_STEP):
                try:
                    ack = executor.process()
                    if ack is not None:
                        acks_count += 1
                except Overrun:
                    # In real app, consumer resets. Here we just count it.
                    # We need to access private consumer to reset or just expose reset in Executor?
                    # Executor doesn't expose reset. 
                    # Assuming for this balanced harness we shouldn't hit overruns if 5 in 5 out.
                    # But if we do, we catch it.
                    overruns_count += 1

            # Record Results
            result = StepResult(
                step_index=step_i,
                lifecycle_state=lifecycle.current().name,
                ingest_calls=self.INGEST_TICKS_PER_STEP,
                execution_polls=self.EXECUTION_POLLS_PER_STEP,
                acks_produced=acks_count,
                overruns=overruns_count,
                metrics_snapshot=metrics.snapshot()
            )
            summary.steps.append(result)

        return summary


if __name__ == "__main__":
    harness = CapacityHarness()
    result = harness.run()
    
    # Simple print of the summary
    print(f"Experiment Complete. Total Steps: {len(result.steps)}")
    print(f"Final State: {result.steps[-1].lifecycle_state}")
    print("Step 0 State:", result.steps[0].lifecycle_state)
    print("Step 10 State:", result.steps[10].lifecycle_state)
    print("Step 40 State:", result.steps[40].lifecycle_state)
