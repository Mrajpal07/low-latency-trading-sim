import pytest
from core.state import State, Lifecycle, InvalidTransition


def test_initial_state_is_init():
    lc = Lifecycle()
    assert lc.current() == State.INIT


def test_valid_transition_init_to_warmup():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    assert lc.current() == State.WARMUP


def test_valid_transition_warmup_to_ready():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)
    assert lc.current() == State.READY


def test_valid_transition_warmup_to_degraded():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.DEGRADED)
    assert lc.current() == State.DEGRADED


def test_valid_transition_ready_to_degraded():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)
    lc.transition(State.DEGRADED)
    assert lc.current() == State.DEGRADED


def test_valid_transition_degraded_to_ready():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.DEGRADED)
    lc.transition(State.READY)
    assert lc.current() == State.READY


def test_invalid_transition_init_to_ready():
    lc = Lifecycle()
    with pytest.raises(InvalidTransition):
        lc.transition(State.READY)
    assert lc.current() == State.INIT


def test_invalid_transition_init_to_degraded():
    lc = Lifecycle()
    with pytest.raises(InvalidTransition):
        lc.transition(State.DEGRADED)
    assert lc.current() == State.INIT


def test_invalid_transition_ready_to_warmup():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)
    with pytest.raises(InvalidTransition):
        lc.transition(State.WARMUP)
    assert lc.current() == State.READY


def test_invalid_transition_ready_to_init():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)
    with pytest.raises(InvalidTransition):
        lc.transition(State.INIT)
    assert lc.current() == State.READY


def test_read_safety_under_repetition():
    lc = Lifecycle()
    for _ in range(1000):
        assert lc.current() == State.INIT
    lc.transition(State.WARMUP)
    for _ in range(1000):
        assert lc.current() == State.WARMUP


def test_no_implicit_state_changes():
    lc = Lifecycle()
    _ = lc.current()
    _ = lc.current()
    assert lc.current() == State.INIT
