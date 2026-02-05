import pytest
from core.state import Lifecycle, State
from core.ingest import MarketDataSource, MarketEvent, NotReady


def test_no_emission_in_init():
    lc = Lifecycle()
    src = MarketDataSource(lc)
    with pytest.raises(NotReady):
        src.emit()


def test_emission_in_warmup():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    src = MarketDataSource(lc)
    event = src.emit()
    assert isinstance(event, MarketEvent)
    assert event.seq == 1


def test_emission_in_ready():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)
    src = MarketDataSource(lc)
    event = src.emit()
    assert isinstance(event, MarketEvent)
    assert event.seq == 1


def test_emission_in_degraded():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.DEGRADED)
    src = MarketDataSource(lc)
    event = src.emit()
    assert isinstance(event, MarketEvent)
    assert event.seq == 1


def test_sequence_monotonicity():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    src = MarketDataSource(lc)
    prev_seq = 0
    for _ in range(100):
        event = src.emit()
        assert event.seq > prev_seq
        prev_seq = event.seq


def test_timestamp_presence():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    src = MarketDataSource(lc)
    event = src.emit()
    assert isinstance(event.ts, int)
    assert event.ts > 0


def test_timestamp_monotonicity():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    src = MarketDataSource(lc)
    prev_ts = 0
    for _ in range(100):
        event = src.emit()
        assert event.ts >= prev_ts
        prev_ts = event.ts


def test_deterministic_sequence_start():
    lc1 = Lifecycle()
    lc1.transition(State.WARMUP)
    src1 = MarketDataSource(lc1)

    lc2 = Lifecycle()
    lc2.transition(State.WARMUP)
    src2 = MarketDataSource(lc2)

    assert src1.emit().seq == src2.emit().seq == 1


def test_sequence_independent_of_state_transitions():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    src = MarketDataSource(lc)
    
    e1 = src.emit()
    lc.transition(State.READY)
    e2 = src.emit()
    lc.transition(State.DEGRADED)
    e3 = src.emit()
    
    assert e1.seq == 1
    assert e2.seq == 2
    assert e3.seq == 3


def test_no_wall_clock_dependency():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    src = MarketDataSource(lc)
    events = [src.emit() for _ in range(10)]
    seqs = [e.seq for e in events]
    assert seqs == list(range(1, 11))
