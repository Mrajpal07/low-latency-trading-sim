from core.state import Lifecycle, State


class ReadinessProbe:
    __slots__ = ("_lifecycle",)

    def __init__(self, lifecycle: Lifecycle) -> None:
        self._lifecycle = lifecycle

    def is_ready(self) -> bool:
        return self._lifecycle.current() == State.READY

    def is_alive(self) -> bool:
        return True  # Process is running

    def is_degraded(self) -> bool:
        return self._lifecycle.current() == State.DEGRADED

    def current_state_name(self) -> str:
        return self._lifecycle.current().name
