from core.state import Lifecycle, State, InvalidTransition


class ShutdownController:
    __slots__ = ("_lifecycle",)

    def __init__(self, lifecycle: Lifecycle) -> None:
        self._lifecycle = lifecycle

    def degrade(self) -> None:
        """Mark system as degraded (stop executing trades)."""
        current = self._lifecycle.current()
        if current in (State.WARMUP, State.READY):
            self._lifecycle.transition(State.DEGRADED)

    def recover(self) -> None:
        """Attempt to recover from degraded state."""
        if self._lifecycle.current() == State.DEGRADED:
            self._lifecycle.transition(State.READY)
