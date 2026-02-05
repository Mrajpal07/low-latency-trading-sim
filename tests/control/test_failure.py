import pytest
from core.state import Lifecycle, State
from control.failure import MarketDataOutage, ExecutionFailure


def test_market_data_outage_activation():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)
    
    outage = MarketDataOutage(lc)
    assert not outage.is_active()
    assert lc.current() == State.READY
    
    outage.activate()
    assert outage.is_active()
    assert lc.current() == State.DEGRADED


def test_market_data_outage_deactivation_restores_state():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)
    
    outage = MarketDataOutage(lc)
    outage.activate()
    assert lc.current() == State.DEGRADED
    
    outage.deactivate()
    assert not outage.is_active()
    assert lc.current() == State.READY


def test_market_data_outage_from_warmup():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    
    outage = MarketDataOutage(lc)
    outage.activate()
    assert lc.current() == State.DEGRADED
    
    outage.deactivate()
    assert lc.current() == State.WARMUP


def test_execution_failure_same_logic():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)
    
    fail = ExecutionFailure(lc)
    fail.activate()
    assert lc.current() == State.DEGRADED
    
    fail.deactivate()
    assert lc.current() == State.READY


def test_idempotent_activation():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)
    
    outage = MarketDataOutage(lc)
    outage.activate()
    outage.activate() # Second call
    
    assert lc.current() == State.DEGRADED
    
    outage.deactivate()
    assert lc.current() == State.READY


def test_no_activation_in_init():
    lc = Lifecycle()
    outage = MarketDataOutage(lc)
    
    outage.activate()
    assert not outage.is_active() # Cannot degrade INIT
    assert lc.current() == State.INIT
