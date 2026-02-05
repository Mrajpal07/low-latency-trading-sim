from typing import Protocol, Any
from core.state import Lifecycle, State


class FailureScenario(Protocol):
    def activate(self) -> None: ...
    def deactivate(self) -> None: ...
    def is_active(self) -> bool: ...


class MarketDataOutage(FailureScenario):
    """Simulates a market data outage by forcing state to DEGRADED."""
    __slots__ = ("_lifecycle", "_previous_state", "_active")

    def __init__(self, lifecycle: Lifecycle) -> None:
        self._lifecycle = lifecycle
        self._previous_state = State.INIT
        self._active = False

    def activate(self) -> None:
        if self._active:
            return
        
        current = self._lifecycle.current()
        if current in (State.WARMUP, State.READY):
            self._previous_state = current
            self._lifecycle.transition(State.DEGRADED)
            self._active = True

    def deactivate(self) -> None:
        if not self._active:
            return
            
        if self._lifecycle.current() == State.DEGRADED:
            self._lifecycle.transition(self._previous_state)
        self._active = False

    def is_active(self) -> bool:
        return self._active


class ExecutionFailure(FailureScenario):
    """Simulates execution failures by forcing state to DEGRADED."""
    # Reuse valid transition mechanic for now - execution check relies on state
    __slots__ = ("_lifecycle", "_previous_state", "_active")

    def __init__(self, lifecycle: Lifecycle) -> None:
        self._lifecycle = lifecycle
        self._previous_state = State.INIT
        self._active = False

    def activate(self) -> None:
        if self._active:
            return
        
        current = self._lifecycle.current()
        if current in (State.WARMUP, State.READY):
            self._previous_state = current
            self._lifecycle.transition(State.DEGRADED)
            self._active = True

    def deactivate(self) -> None:
        if not self._active:
            return
            
        if self._lifecycle.current() == State.DEGRADED:
            self._lifecycle.transition(self._previous_state)
        self._active = False

    def is_active(self) -> bool:
        return self._active
