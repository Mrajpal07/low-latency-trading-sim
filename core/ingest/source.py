from core.time import now
from core.state import State, Lifecycle


class NotReady(Exception):
    pass


class MarketEvent:
    __slots__ = ("seq", "ts")

    def __init__(self, seq: int, ts: int) -> None:
        self.seq = seq
        self.ts = ts


class MarketDataSource:
    __slots__ = ("_seq", "_lifecycle")

    def __init__(self, lifecycle: Lifecycle) -> None:
        self._seq = 0
        self._lifecycle = lifecycle

    def emit(self) -> MarketEvent:
        state = self._lifecycle.current()
        if state == State.INIT:
            raise NotReady()
        self._seq += 1
        return MarketEvent(self._seq, now())
