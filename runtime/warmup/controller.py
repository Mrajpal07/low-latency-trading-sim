from core.state import Lifecycle, State, InvalidTransition


class WarmUpController:
    __slots__ = ("_lifecycle", "_steps", "_current_step")

    def __init__(self, lifecycle: Lifecycle, steps: int = 1000) -> None:
        self._lifecycle = lifecycle
        self._steps = steps
        self._current_step = 0

    def start(self) -> None:
        if self._lifecycle.current() == State.INIT:
            self._lifecycle.transition(State.WARMUP)

    def tick(self) -> None:
        if self._lifecycle.current() != State.WARMUP:
            return
        
        if self._current_step < self._steps:
            self._current_step += 1

    def is_complete(self) -> bool:
        return self._current_step >= self._steps

    def complete(self) -> None:
        if self.is_complete() and self._lifecycle.current() == State.WARMUP:
            self._lifecycle.transition(State.READY)
