import pytest
from core.bus import RingBuffer
from core.state import Lifecycle, State
from core.execution import Executor, Ack, ObservabilitySink, NoOpSink


class MockSink:
    def __init__(self):
        self.observations = []

    def observe(self, event, ack):
        self.observations.append((event, ack))


def test_default_sink_is_noop():
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    ex = Executor(ring, lc)
    assert isinstance(ex._sink, NoOpSink)


def test_execution_behavior_unchanged_with_default_sink():
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)
    ex = Executor(ring, lc)

    ring.publish(100)
    ack = ex.process()
    assert ack is not None
    assert ack.executed is True
    assert ack.seq == 0


def test_custom_sink_injection():
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    sink = MockSink()
    ex = Executor(ring, lc, sink=sink)
    assert ex._sink is sink


def test_observations_emitted():
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)
    sink = MockSink()
    ex = Executor(ring, lc, sink=sink)

    ring.publish(42)
    ack = ex.process()

    assert len(sink.observations) == 1
    event, observed_ack = sink.observations[0]
    assert event == 42
    assert observed_ack is ack


def test_sink_does_not_affect_execution_return():
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    ex = Executor(ring, lc, sink=NoOpSink())

    ring.publish(1)
    ack = ex.process()
    assert ack is not None
    assert ack.seq == 0


def test_no_observation_on_empty_poll():
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    sink = MockSink()
    ex = Executor(ring, lc, sink=sink)

    assert ex.process() is None
    assert len(sink.observations) == 0


def test_polymorphism_no_branching():
    """Verify we can pass any object satisfying the protocol (duck typing)."""
    class DuckSink:
        def observe(self, event, ack):
            pass

    ring = RingBuffer[int](8)
    lc = Lifecycle()
    ex = Executor(ring, lc, sink=DuckSink())
    # Should not raise
    pass
