from typing import Any

from core.bus import Consumer, RingBuffer
from core.time import now
from core.state import State, Lifecycle


from .observability import NoOpSink


class NotReady(Exception):
    pass


class Ack:
    __slots__ = ("seq", "decision_ts", "completion_ts", "executed")

    def __init__(self, seq: int, decision_ts: int, completion_ts: int, executed: bool) -> None:
        self.seq = seq
        self.decision_ts = decision_ts
        self.completion_ts = completion_ts
        self.executed = executed


class Executor:
    __slots__ = ("_consumer", "_lifecycle", "_sink")

    def __init__(self, ring: RingBuffer[Any], lifecycle: Lifecycle, sink: Any = None) -> None:
        self._consumer = Consumer(ring)
        self._lifecycle = lifecycle
        self._sink = sink if sink is not None else NoOpSink()

    def process(self) -> Ack | None:
        state = self._lifecycle.current()
        if state == State.INIT:
            raise NotReady()

        event = self._consumer.poll()
        if event is None:
            return None

        decision_ts = now()
        executed = state == State.READY
        completion_ts = now()

        ack = Ack(
            seq=self._consumer.cursor() - 1,
            decision_ts=decision_ts,
            completion_ts=completion_ts,
            executed=executed,
        )
        self._sink.observe(event, ack)
        return ack

    def cursor(self) -> int:
        return self._consumer.cursor()
