from dataclasses import dataclass, field
from typing import List, Any, Optional

from core.state import Lifecycle
from core.bus import RingBuffer, Overrun
from core.ingest import MarketDataSource
from core.execution import Executor
from control.metrics import Metrics
from runtime.warmup import WarmUpController
from control.failure import MarketDataOutage
from .scenarios import Scenario

@dataclass
class DemoStepResult:
    step_index: int
    lifecycle_state: str
    overruns: int

@dataclass
class DemoSummary:
    total_ingested: int
    total_acks: int
    final_state: str
    steps: List[DemoStepResult] = field(default_factory=list)

class DemoRunner:
    def run(self, scenario: Scenario) -> DemoSummary:
        # Initialize
        lifecycle = Lifecycle()
        ring = RingBuffer[Any](scenario.ring_capacity)
        source = MarketDataSource(lifecycle)
        metrics = Metrics()
        # Minimal sink adapter (we don't strictly need metrics for the demo flow, 
        # but wiring it correctly matches system design)
        class NoOpSink:
             def observe(self, e, a): pass
        
        executor = Executor(ring, lifecycle, sink=NoOpSink())
        
        warmup_ctrl = WarmUpController(lifecycle, steps=scenario.warmup_ticks)
        failure_ctrl = MarketDataOutage(lifecycle)
        
        total_ingested = 0
        total_acks = 0
        steps = []
        
        warmup_ctrl.start()
        
        for step_i in range(scenario.total_steps):
            # 1. Injections / Control
            if step_i in scenario.injections:
                action = scenario.injections[step_i]
                if action == "activate_failure":
                    failure_ctrl.activate()
                elif action == "deactivate_failure":
                    failure_ctrl.deactivate()

            # 2. Lifecycle Ticks
            # Warmup logic
            if step_i < scenario.warmup_ticks:
                warmup_ctrl.tick()
            elif step_i == scenario.warmup_ticks:
                warmup_ctrl.complete()
            
            # 3. Ingest
            for _ in range(scenario.ingest_ticks_per_step):
                # Only ingest if allowed by lifecycle (source.emit raises NotReady if INIT)
                # But here we are in WARMUP or READY.
                # Actually source.emit() checks state.
                # If we are in DEGRADED, emit works? Yes.
                # If we are in INIT, emit raises. 
                # Warmup starts at step begin.
                try:
                    event = source.emit()
                    ring.publish(event)
                    total_ingested += 1
                except Exception:
                    pass # INIT state or other blocks

            # 4. Execute
            overruns_this_step = 0
            for _ in range(scenario.execution_polls_per_step):
                try:
                    ack = executor.process()
                    if ack is not None:
                        total_acks += 1
                except Overrun:
                    overruns_this_step += 1
                except Exception:
                    pass # Can happen if not ready
            
            steps.append(DemoStepResult(
                step_index=step_i,
                lifecycle_state=lifecycle.current().name,
                overruns=overruns_this_step
            ))
            
        return DemoSummary(
            total_ingested=total_ingested,
            total_acks=total_acks,
            final_state=lifecycle.current().name,
            steps=steps
        )
