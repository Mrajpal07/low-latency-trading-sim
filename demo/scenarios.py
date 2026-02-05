from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class Scenario:
    name: str
    description: str
    ingest_ticks_per_step: int
    execution_polls_per_step: int
    warmup_ticks: int = 10
    total_steps: int = 50
    # Step index -> action (e.g. "activate_failure", "deactivate_failure")
    injections: Dict[int, str] = field(default_factory=dict)
    # Additional metadata
    ring_capacity: int = 64


SCENARIOS = {
    "balanced": Scenario(
        name="balanced",
        description="Prove stable READY execution with no overruns",
        ingest_ticks_per_step=5,
        execution_polls_per_step=5
    ),
    "producer-heavy": Scenario(
        name="producer-heavy",
        description="Prove explicit backpressure and deterministic overruns",
        ingest_ticks_per_step=8,
        execution_polls_per_step=3
    ),
    "consumer-heavy": Scenario(
        name="consumer-heavy",
        description="Prove clean behavior under sparse data (empty polls)",
        ingest_ticks_per_step=3,
        execution_polls_per_step=8
    ),
    "failure-recovery": Scenario(
        name="failure-recovery",
        description="Prove runtime authority, degradation, and recovery",
        ingest_ticks_per_step=5,
        execution_polls_per_step=5,
        injections={
            20: "activate_failure",
            40: "deactivate_failure"
        }
    )
}
