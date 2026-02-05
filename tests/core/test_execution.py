import pytest
from core.bus import RingBuffer
from core.state import Lifecycle, State
from core.execution import Executor, Ack, NotReady


def test_not_ready_in_init():
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    ex = Executor(ring, lc)
    with pytest.raises(NotReady):
        ex.process()


def test_process_in_warmup():
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    ex = Executor(ring, lc)
    ring.publish(100)
    ack = ex.process()
    assert isinstance(ack, Ack)


def test_process_in_ready():
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)
    ex = Executor(ring, lc)
    ring.publish(100)
    ack = ex.process()
    assert isinstance(ack, Ack)
    assert ack.executed is True


def test_process_in_degraded():
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.DEGRADED)
    ex = Executor(ring, lc)
    ring.publish(100)
    ack = ex.process()
    assert isinstance(ack, Ack)
    assert ack.executed is False


def test_executed_only_in_ready():
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    ex = Executor(ring, lc)
    ring.publish(1)
    ack_warmup = ex.process()
    assert ack_warmup.executed is False

    lc.transition(State.READY)
    ring.publish(2)
    ack_ready = ex.process()
    assert ack_ready.executed is True

    lc.transition(State.DEGRADED)
    ring.publish(3)
    ack_degraded = ex.process()
    assert ack_degraded.executed is False


def test_returns_none_when_no_events():
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    ex = Executor(ring, lc)
    assert ex.process() is None


def test_ack_contains_sequence():
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    ex = Executor(ring, lc)
    ring.publish(10)
    ring.publish(20)
    ring.publish(30)
    ack1 = ex.process()
    ack2 = ex.process()
    ack3 = ex.process()
    assert ack1.seq == 0
    assert ack2.seq == 1
    assert ack3.seq == 2


def test_decision_timestamp_present():
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    ex = Executor(ring, lc)
    ring.publish(1)
    ack = ex.process()
    assert isinstance(ack.decision_ts, int)
    assert ack.decision_ts > 0


def test_completion_timestamp_present():
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    ex = Executor(ring, lc)
    ring.publish(1)
    ack = ex.process()
    assert isinstance(ack.completion_ts, int)
    assert ack.completion_ts > 0


def test_completion_after_decision():
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    ex = Executor(ring, lc)
    ring.publish(1)
    ack = ex.process()
    assert ack.completion_ts >= ack.decision_ts


def test_timestamps_monotonic_across_acks():
    ring = RingBuffer[int](16)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    ex = Executor(ring, lc)
    for i in range(10):
        ring.publish(i)
    prev_decision = 0
    prev_completion = 0
    for _ in range(10):
        ack = ex.process()
        assert ack.decision_ts >= prev_decision
        assert ack.completion_ts >= prev_completion
        prev_decision = ack.decision_ts
        prev_completion = ack.completion_ts


def test_exactly_once_ack():
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    ex = Executor(ring, lc)
    ring.publish(1)
    ack1 = ex.process()
    ack2 = ex.process()
    assert ack1 is not None
    assert ack2 is None


def test_cursor_advances():
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    ex = Executor(ring, lc)
    assert ex.cursor() == 0
    ring.publish(1)
    ring.publish(2)
    ex.process()
    assert ex.cursor() == 1
    ex.process()
    assert ex.cursor() == 2


def test_deterministic_outcome():
    ring1 = RingBuffer[int](8)
    ring2 = RingBuffer[int](8)
    lc1 = Lifecycle()
    lc2 = Lifecycle()
    lc1.transition(State.WARMUP)
    lc1.transition(State.READY)
    lc2.transition(State.WARMUP)
    lc2.transition(State.READY)
    ex1 = Executor(ring1, lc1)
    ex2 = Executor(ring2, lc2)
    ring1.publish(42)
    ring2.publish(42)
    ack1 = ex1.process()
    ack2 = ex2.process()
    assert ack1.executed == ack2.executed
    assert ack1.seq == ack2.seq


# === Additional coverage for edge cases ===


def test_lifecycle_change_between_events():
    """Executor picks up state change for each event."""
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)
    ex = Executor(ring, lc)

    ring.publish(1)
    ring.publish(2)
    ring.publish(3)

    ack1 = ex.process()
    assert ack1.executed is True

    lc.transition(State.DEGRADED)
    ack2 = ex.process()
    assert ack2.executed is False

    lc.transition(State.READY)
    ack3 = ex.process()
    assert ack3.executed is True


def test_ready_degraded_ready_cycle():
    """executed flag correctly flips through state cycle."""
    ring = RingBuffer[int](16)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)
    ex = Executor(ring, lc)

    for i in range(6):
        ring.publish(i)

    assert ex.process().executed is True  # READY
    assert ex.process().executed is True  # READY

    lc.transition(State.DEGRADED)
    assert ex.process().executed is False  # DEGRADED
    assert ex.process().executed is False  # DEGRADED

    lc.transition(State.READY)
    assert ex.process().executed is True  # READY again
    assert ex.process().executed is True  # READY again


def test_not_ready_does_not_consume():
    """NotReady exception leaves cursor unchanged."""
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    ex = Executor(ring, lc)

    ring.publish(100)
    initial_cursor = ex.cursor()

    with pytest.raises(NotReady):
        ex.process()

    assert ex.cursor() == initial_cursor

    # After transitioning, event is still available
    lc.transition(State.WARMUP)
    ack = ex.process()
    assert ack.seq == 0


def test_overrun_propagates():
    """Overrun from underlying consumer propagates."""
    from core.bus import Overrun

    ring = RingBuffer[int](4)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    ex = Executor(ring, lc)

    # Publish more than capacity, causing overrun
    for i in range(10):
        ring.publish(i)

    with pytest.raises(Overrun):
        ex.process()


def test_multiple_executors_independent():
    """Multiple executors on same ring have independent cursors."""
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)

    ex1 = Executor(ring, lc)
    ex2 = Executor(ring, lc)

    ring.publish(10)
    ring.publish(20)
    ring.publish(30)

    # ex1 processes all 3
    ack1a = ex1.process()
    ack1b = ex1.process()
    ack1c = ex1.process()
    assert ack1a.seq == 0
    assert ack1b.seq == 1
    assert ack1c.seq == 2

    # ex2 independently processes all 3
    ack2a = ex2.process()
    ack2b = ex2.process()
    ack2c = ex2.process()
    assert ack2a.seq == 0
    assert ack2b.seq == 1
    assert ack2c.seq == 2


def test_late_joining_executor():
    """Executor created after publishes starts at current head."""
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)

    ring.publish(1)
    ring.publish(2)
    ring.publish(3)

    late_ex = Executor(ring, lc)
    assert late_ex.cursor() == 3
    assert late_ex.process() is None

    ring.publish(100)
    ack = late_ex.process()
    assert ack.seq == 3


def test_high_throughput():
    """Correctness with many events processed in batches."""
    ring = RingBuffer[int](64)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)
    ex = Executor(ring, lc)

    n = 10_000
    expected_seq = 0

    # Process in batches to avoid overrun
    batch_size = 32
    for batch_start in range(0, n, batch_size):
        for i in range(batch_start, min(batch_start + batch_size, n)):
            ring.publish(i)
        for _ in range(min(batch_size, n - batch_start)):
            ack = ex.process()
            assert ack.seq == expected_seq
            assert ack.executed is True
            expected_seq += 1

    assert ex.process() is None
    assert expected_seq == n


def test_ack_independence():
    """Each Ack is independent, no shared state."""
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    ex = Executor(ring, lc)

    ring.publish(1)
    ring.publish(2)

    ack1 = ex.process()
    ack2 = ex.process()

    # Different objects
    assert ack1 is not ack2

    # Different values
    assert ack1.seq != ack2.seq

    # Verify distinct values
    assert ack1.seq == 0
    assert ack2.seq == 1


def test_timestamps_independent_of_wall_clock():
    """Timestamps use monotonic clock, not wall clock."""
    from unittest.mock import patch

    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    ex = Executor(ring, lc)
    ring.publish(1)

    with patch('time.time', side_effect=Exception("wall clock used")):
        ack = ex.process()
        assert isinstance(ack.decision_ts, int)
        assert isinstance(ack.completion_ts, int)


def test_multiple_none_returns():
    """Multiple process calls on empty ring all return None."""
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    ex = Executor(ring, lc)

    for _ in range(100):
        assert ex.process() is None

    # Cursor unchanged
    assert ex.cursor() == 0


def test_process_does_not_block():
    """process() returns immediately, never blocks."""
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    ex = Executor(ring, lc)

    # Call many times rapidly - should never block
    results = [ex.process() for _ in range(1000)]
    assert all(r is None for r in results)


# === Feature 7: Observability Wiring Tests ===


from core.execution import ObservabilitySink, NoOpSink


class RecordingSink:
    """Test sink that records all observations."""

    def __init__(self):
        self.observations = []

    def observe(self, event, ack):
        self.observations.append((event, ack))


def test_default_sink_is_noop():
    """Executor uses NoOpSink by default."""
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    ex = Executor(ring, lc)

    # Should work without any sink configuration
    ring.publish(100)
    ack = ex.process()
    assert ack is not None
    assert ack.seq == 0


def test_custom_sink_receives_observations():
    """Custom sink's observe() is called for each event."""
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    sink = RecordingSink()
    ex = Executor(ring, lc, sink=sink)

    ring.publish(100)
    ring.publish(200)

    ex.process()
    ex.process()

    assert len(sink.observations) == 2


def test_sink_receives_correct_event():
    """Sink receives the actual event from the ring."""
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    sink = RecordingSink()
    ex = Executor(ring, lc, sink=sink)

    ring.publish(42)
    ring.publish(99)

    ex.process()
    ex.process()

    assert sink.observations[0][0] == 42
    assert sink.observations[1][0] == 99


def test_sink_receives_correct_ack():
    """Sink receives ack with correct seq and executed flag."""
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)
    sink = RecordingSink()
    ex = Executor(ring, lc, sink=sink)

    ring.publish(100)
    ack = ex.process()

    observed_event, observed_ack = sink.observations[0]
    assert observed_ack.seq == ack.seq
    assert observed_ack.executed == ack.executed
    assert observed_ack.decision_ts == ack.decision_ts
    assert observed_ack.completion_ts == ack.completion_ts


def test_sink_not_called_when_no_event():
    """Sink.observe() not called when process() returns None."""
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    sink = RecordingSink()
    ex = Executor(ring, lc, sink=sink)

    # No events published
    result = ex.process()
    assert result is None
    assert len(sink.observations) == 0


def test_sink_called_exactly_once_per_event():
    """Each event triggers exactly one observe() call."""
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    sink = RecordingSink()
    ex = Executor(ring, lc, sink=sink)

    for i in range(5):
        ring.publish(i)

    for _ in range(5):
        ex.process()

    assert len(sink.observations) == 5

    # Subsequent calls with no events don't trigger observe
    for _ in range(10):
        ex.process()

    assert len(sink.observations) == 5


def test_noop_sink_does_nothing():
    """NoOpSink.observe() can be called without error."""
    sink = NoOpSink()
    # Create a mock ack-like object
    class FakeAck:
        seq = 0
        decision_ts = 1000
        completion_ts = 2000
        executed = True

    # Should not raise
    sink.observe(42, FakeAck())
    sink.observe("event", FakeAck())
    sink.observe(None, FakeAck())


def test_multiple_executors_different_sinks():
    """Each executor can have its own independent sink."""
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)

    sink1 = RecordingSink()
    sink2 = RecordingSink()

    ex1 = Executor(ring, lc, sink=sink1)
    ex2 = Executor(ring, lc, sink=sink2)

    ring.publish(100)
    ring.publish(200)

    ex1.process()
    ex1.process()

    ex2.process()

    assert len(sink1.observations) == 2
    assert len(sink2.observations) == 1


def test_sink_receives_observations_in_order():
    """Observations are received in processing order."""
    ring = RingBuffer[int](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    sink = RecordingSink()
    ex = Executor(ring, lc, sink=sink)

    for i in range(5):
        ring.publish(i * 10)

    for _ in range(5):
        ex.process()

    events = [obs[0] for obs in sink.observations]
    assert events == [0, 10, 20, 30, 40]


def test_observability_no_control_imports():
    """Verify observability.py doesn't import from control.*"""
    import ast
    with open("core/execution/observability.py", "r") as f:
        source = f.read()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("control"), \
                    f"Layering violation: imports {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert not node.module.startswith("control"), \
                    f"Layering violation: imports from {node.module}"


def test_execution_unchanged_with_sink():
    """Execution behavior identical with or without custom sink."""
    ring1 = RingBuffer[int](8)
    ring2 = RingBuffer[int](8)
    lc1 = Lifecycle()
    lc2 = Lifecycle()
    lc1.transition(State.WARMUP)
    lc1.transition(State.READY)
    lc2.transition(State.WARMUP)
    lc2.transition(State.READY)

    # One with default sink, one with custom
    ex_default = Executor(ring1, lc1)
    ex_custom = Executor(ring2, lc2, sink=RecordingSink())

    ring1.publish(42)
    ring2.publish(42)

    ack1 = ex_default.process()
    ack2 = ex_custom.process()

    assert ack1.seq == ack2.seq
    assert ack1.executed == ack2.executed


def test_sink_with_complex_event_types():
    """Sink works with non-primitive event types."""
    class ComplexEvent:
        def __init__(self, data):
            self.data = data

    ring = RingBuffer[ComplexEvent](8)
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    sink = RecordingSink()
    ex = Executor(ring, lc, sink=sink)

    event = ComplexEvent({"key": "value"})
    ring.publish(event)
    ex.process()

    observed_event, _ = sink.observations[0]
    assert observed_event is event
    assert observed_event.data == {"key": "value"}
