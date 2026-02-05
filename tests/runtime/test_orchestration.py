import pytest
from core.state import Lifecycle, State
from runtime.warmup import WarmUpController
from runtime.readiness import ReadinessProbe
from runtime.shutdown import ShutdownController


def test_warmup_flow():
    lc = Lifecycle()
    ctrl = WarmUpController(lc, steps=5)
    
    assert lc.current() == State.INIT
    ctrl.start()
    assert lc.current() == State.WARMUP
    
    for _ in range(5):
        assert not ctrl.is_complete()
        ctrl.tick()
        
    assert ctrl.is_complete()
    ctrl.complete()
    assert lc.current() == State.READY


def test_warmup_requires_completion():
    lc = Lifecycle()
    ctrl = WarmUpController(lc, steps=5)
    ctrl.start()
    
    # Not enough ticks
    ctrl.tick()
    ctrl.complete()
    
    assert lc.current() == State.WARMUP


def test_readiness_probe():
    lc = Lifecycle()
    probe = ReadinessProbe(lc)
    
    assert not probe.is_ready()
    assert probe.current_state_name() == "INIT"
    
    lc.transition(State.WARMUP)
    lc.transition(State.READY)
    
    assert probe.is_ready()
    assert probe.current_state_name() == "READY"


def test_shutdown_degradation():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)
    
    sd = ShutdownController(lc)
    sd.degrade()
    
    assert lc.current() == State.DEGRADED


def test_recovery_from_degraded():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)
    
    sd = ShutdownController(lc)
    sd.degrade()
    assert lc.current() == State.DEGRADED
    
    sd.recover()
    assert lc.current() == State.READY


def test_idempotent_transitions():
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)
    
    sd = ShutdownController(lc)
    
    # Already degraded (simulated double call)
    sd.degrade()
    sd.degrade()
    
    assert lc.current() == State.DEGRADED


def test_warmup_tick_noop_if_not_warming():
    lc = Lifecycle()
    ctrl = WarmUpController(lc, steps=5)
    
    # In INIT
    ctrl.tick()
    assert not ctrl.is_complete() # Tick ignored
    
    ctrl.start()
    ctrl.tick()
    # Now counting
