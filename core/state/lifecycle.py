from enum import IntEnum


class State(IntEnum):
    INIT = 0
    WARMUP = 1
    READY = 2
    DEGRADED = 3


VALID_TRANSITIONS = {
    State.INIT: (State.WARMUP,),
    State.WARMUP: (State.READY, State.DEGRADED),
    State.READY: (State.DEGRADED,),
    State.DEGRADED: (State.READY,),
}


class InvalidTransition(Exception):
    pass


class Lifecycle:
    __slots__ = ("_state",)

    def __init__(self) -> None:
        self._state = State.INIT

    def current(self) -> State:
        return self._state

    def transition(self, target: State) -> None:
        if target not in VALID_TRANSITIONS[self._state]:
            raise InvalidTransition(f"{self._state.name} -> {target.name}")
        self._state = target
