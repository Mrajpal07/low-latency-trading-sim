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


# === Additional coverage for edge cases ===


def test_idempotent_deactivation():
    """Multiple deactivate calls are safe."""
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)

    outage = MarketDataOutage(lc)
    outage.activate()
    outage.deactivate()
    outage.deactivate()  # Second call
    outage.deactivate()  # Third call

    assert not outage.is_active()
    assert lc.current() == State.READY


def test_deactivate_without_activation():
    """Deactivate when never activated is safe."""
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)

    outage = MarketDataOutage(lc)
    outage.deactivate()  # Never activated

    assert not outage.is_active()
    assert lc.current() == State.READY


def test_no_activation_from_degraded():
    """Cannot activate when already in DEGRADED state."""
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.DEGRADED)

    outage = MarketDataOutage(lc)
    outage.activate()

    # Should not activate since state is already DEGRADED
    assert not outage.is_active()
    assert lc.current() == State.DEGRADED


def test_execution_failure_from_warmup():
    """ExecutionFailure works from WARMUP state."""
    lc = Lifecycle()
    lc.transition(State.WARMUP)

    fail = ExecutionFailure(lc)
    fail.activate()
    assert lc.current() == State.DEGRADED

    fail.deactivate()
    assert lc.current() == State.WARMUP


def test_activate_deactivate_activate_cycle():
    """Re-activation after recovery works correctly."""
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)

    outage = MarketDataOutage(lc)

    # First cycle
    outage.activate()
    assert lc.current() == State.DEGRADED
    outage.deactivate()
    assert lc.current() == State.READY

    # Second cycle
    outage.activate()
    assert lc.current() == State.DEGRADED
    assert outage.is_active()
    outage.deactivate()
    assert lc.current() == State.READY
    assert not outage.is_active()


def test_multiple_scenarios_same_lifecycle():
    """Multiple failure scenarios on same lifecycle."""
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)

    outage = MarketDataOutage(lc)
    exec_fail = ExecutionFailure(lc)

    # Activate first scenario
    outage.activate()
    assert lc.current() == State.DEGRADED
    assert outage.is_active()

    # Second scenario can't activate (already degraded)
    exec_fail.activate()
    assert not exec_fail.is_active()

    # Deactivate first
    outage.deactivate()
    assert lc.current() == State.READY

    # Now second can activate
    exec_fail.activate()
    assert lc.current() == State.DEGRADED
    assert exec_fail.is_active()


def test_scenarios_are_independent():
    """Different scenarios on different lifecycles are independent."""
    lc1 = Lifecycle()
    lc2 = Lifecycle()
    lc1.transition(State.WARMUP)
    lc1.transition(State.READY)
    lc2.transition(State.WARMUP)
    lc2.transition(State.READY)

    outage1 = MarketDataOutage(lc1)
    outage2 = MarketDataOutage(lc2)

    outage1.activate()

    assert lc1.current() == State.DEGRADED
    assert lc2.current() == State.READY
    assert outage1.is_active()
    assert not outage2.is_active()


def test_external_state_change_during_failure():
    """State changed externally while failure is active."""
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)

    outage = MarketDataOutage(lc)
    outage.activate()
    assert lc.current() == State.DEGRADED

    # External recovery (e.g., manual intervention)
    lc.transition(State.READY)

    # Deactivate should be safe (state already not DEGRADED)
    outage.deactivate()
    assert lc.current() == State.READY
    assert not outage.is_active()


def test_protocol_interface():
    """FailureScenario protocol is correctly implemented."""
    from control.failure import FailureScenario

    lc = Lifecycle()
    lc.transition(State.WARMUP)

    outage = MarketDataOutage(lc)
    exec_fail = ExecutionFailure(lc)

    # Both implement the protocol
    assert hasattr(outage, 'activate')
    assert hasattr(outage, 'deactivate')
    assert hasattr(outage, 'is_active')

    assert hasattr(exec_fail, 'activate')
    assert hasattr(exec_fail, 'deactivate')
    assert hasattr(exec_fail, 'is_active')

    # Callable
    assert callable(outage.activate)
    assert callable(outage.deactivate)
    assert callable(outage.is_active)


def test_no_illegal_transitions():
    """Scenarios only use valid lifecycle transitions."""
    from core.state import InvalidTransition

    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)

    outage = MarketDataOutage(lc)

    # These should not raise InvalidTransition
    outage.activate()  # READY -> DEGRADED (valid)
    outage.deactivate()  # DEGRADED -> READY (valid)

    # No exception means valid transitions


def test_no_hot_path_imports():
    """Verify scenarios.py doesn't import from hot-path modules."""
    import ast
    with open("control/failure/scenarios.py", "r") as f:
        source = f.read()
    tree = ast.parse(source)

    forbidden = ["core.bus", "core.execution", "core.ingest", "runtime"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden_module in forbidden:
                    assert not alias.name.startswith(forbidden_module), \
                        f"Hot-path import violation: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for forbidden_module in forbidden:
                    assert not node.module.startswith(forbidden_module), \
                        f"Hot-path import violation: {node.module}"


def test_state_preserved_correctly():
    """Previous state is correctly saved and restored."""
    lc = Lifecycle()
    lc.transition(State.WARMUP)

    outage = MarketDataOutage(lc)
    outage.activate()
    assert outage._previous_state == State.WARMUP

    outage.deactivate()
    assert lc.current() == State.WARMUP

    # Now from READY
    lc.transition(State.READY)
    outage.activate()
    assert outage._previous_state == State.READY

    outage.deactivate()
    assert lc.current() == State.READY


def test_is_active_reflects_state():
    """is_active() accurately reflects scenario state."""
    lc = Lifecycle()
    lc.transition(State.WARMUP)
    lc.transition(State.READY)

    outage = MarketDataOutage(lc)

    assert outage.is_active() is False

    outage.activate()
    assert outage.is_active() is True

    outage.deactivate()
    assert outage.is_active() is False
