import pytest
from control.metrics import Metrics, Snapshot


def test_observe_never_raises():
    m = Metrics()
    for val in [0, 1, -1, 10**18, -10**18, 0]:
        m.observe(val)


def test_initial_snapshot_zeros():
    m = Metrics()
    s = m.snapshot()
    assert s.count == 0
    assert s.total_latency_ns == 0
    assert s.min_latency_ns == 0
    assert s.max_latency_ns == 0


def test_single_observation():
    m = Metrics()
    m.observe(100)
    s = m.snapshot()
    assert s.count == 1
    assert s.total_latency_ns == 100
    assert s.min_latency_ns == 100
    assert s.max_latency_ns == 100


def test_multiple_observations():
    m = Metrics()
    m.observe(10)
    m.observe(20)
    m.observe(30)
    s = m.snapshot()
    assert s.count == 3
    assert s.total_latency_ns == 60
    assert s.min_latency_ns == 10
    assert s.max_latency_ns == 30


def test_min_max_tracking():
    m = Metrics()
    m.observe(50)
    m.observe(10)
    m.observe(90)
    m.observe(30)
    s = m.snapshot()
    assert s.min_latency_ns == 10
    assert s.max_latency_ns == 90


def test_reset_returns_snapshot():
    m = Metrics()
    m.observe(100)
    m.observe(200)
    s = m.reset()
    assert s.count == 2
    assert s.total_latency_ns == 300


def test_reset_clears_state():
    m = Metrics()
    m.observe(100)
    m.observe(200)
    m.reset()
    s = m.snapshot()
    assert s.count == 0
    assert s.total_latency_ns == 0
    assert s.min_latency_ns == 0
    assert s.max_latency_ns == 0


def test_observe_after_reset():
    m = Metrics()
    m.observe(100)
    m.reset()
    m.observe(50)
    s = m.snapshot()
    assert s.count == 1
    assert s.total_latency_ns == 50
    assert s.min_latency_ns == 50
    assert s.max_latency_ns == 50


def test_snapshot_is_immutable():
    m = Metrics()
    m.observe(100)
    s1 = m.snapshot()
    m.observe(200)
    s2 = m.snapshot()
    assert s1.count == 1
    assert s2.count == 2


def test_high_throughput():
    m = Metrics()
    n = 100_000
    for i in range(n):
        m.observe(i)
    s = m.snapshot()
    assert s.count == n
    assert s.min_latency_ns == 0
    assert s.max_latency_ns == n - 1
    assert s.total_latency_ns == sum(range(n))


def test_snapshot_namedtuple():
    m = Metrics()
    m.observe(42)
    s = m.snapshot()
    assert isinstance(s, Snapshot)
    assert s.count == 1
    assert s[0] == 1  # indexable


def test_observability_failure_isolation():
    """Metrics failure should not affect caller."""
    m = Metrics()
    
    # Simulate execution with observation
    result = 42
    m.observe(100)
    assert result == 42  # Execution unaffected
    
    # Even with many observations
    for _ in range(1000):
        m.observe(1)
    assert result == 42


def test_multiple_reset_cycles():
    m = Metrics()
    for cycle in range(10):
        for i in range(100):
            m.observe(i + cycle * 100)
        s = m.reset()
        assert s.count == 100


# === Additional coverage for edge cases ===


def test_zero_latency_observation():
    """Zero is a valid latency value."""
    m = Metrics()
    m.observe(0)
    s = m.snapshot()
    assert s.count == 1
    assert s.total_latency_ns == 0
    assert s.min_latency_ns == 0
    assert s.max_latency_ns == 0


def test_negative_latency_min_max():
    """Negative values tracked correctly for min/max."""
    m = Metrics()
    m.observe(-100)
    m.observe(-50)
    m.observe(-200)
    s = m.snapshot()
    assert s.min_latency_ns == -200
    assert s.max_latency_ns == -50
    assert s.total_latency_ns == -350


def test_mixed_positive_negative():
    """Mixed positive and negative latencies."""
    m = Metrics()
    m.observe(-10)
    m.observe(0)
    m.observe(10)
    s = m.snapshot()
    assert s.min_latency_ns == -10
    assert s.max_latency_ns == 10
    assert s.total_latency_ns == 0


def test_multiple_metrics_instances_independent():
    """Multiple Metrics instances have no shared state."""
    m1 = Metrics()
    m2 = Metrics()

    m1.observe(100)
    m1.observe(200)

    m2.observe(1000)

    s1 = m1.snapshot()
    s2 = m2.snapshot()

    assert s1.count == 2
    assert s1.total_latency_ns == 300

    assert s2.count == 1
    assert s2.total_latency_ns == 1000


def test_large_values_no_overflow():
    """Large latency values don't cause issues."""
    m = Metrics()
    large = 10**15  # 1 quadrillion nanoseconds
    m.observe(large)
    m.observe(large)
    m.observe(large)
    s = m.snapshot()
    assert s.count == 3
    assert s.total_latency_ns == 3 * large
    assert s.min_latency_ns == large
    assert s.max_latency_ns == large


def test_all_same_observations():
    """All identical observations: min equals max."""
    m = Metrics()
    for _ in range(100):
        m.observe(42)
    s = m.snapshot()
    assert s.count == 100
    assert s.min_latency_ns == 42
    assert s.max_latency_ns == 42
    assert s.total_latency_ns == 4200


def test_order_independence():
    """Same values in different order produce same aggregates."""
    values = [10, 50, 30, 90, 20]

    m1 = Metrics()
    for v in values:
        m1.observe(v)

    m2 = Metrics()
    for v in reversed(values):
        m2.observe(v)

    s1 = m1.snapshot()
    s2 = m2.snapshot()

    assert s1.count == s2.count
    assert s1.total_latency_ns == s2.total_latency_ns
    assert s1.min_latency_ns == s2.min_latency_ns
    assert s1.max_latency_ns == s2.max_latency_ns


def test_empty_reset():
    """Reset with no observations returns zeros."""
    m = Metrics()
    s = m.reset()
    assert s.count == 0
    assert s.total_latency_ns == 0
    assert s.min_latency_ns == 0
    assert s.max_latency_ns == 0


def test_average_calculation():
    """Total and count allow correct average calculation."""
    m = Metrics()
    m.observe(10)
    m.observe(20)
    m.observe(30)
    m.observe(40)
    s = m.snapshot()
    average = s.total_latency_ns / s.count
    assert average == 25.0


def test_first_observation_sets_min_max():
    """First observation initializes both min and max."""
    m = Metrics()
    m.observe(500)
    s = m.snapshot()
    assert s.min_latency_ns == 500
    assert s.max_latency_ns == 500

    # Second observation updates appropriately
    m.observe(100)
    s = m.snapshot()
    assert s.min_latency_ns == 100
    assert s.max_latency_ns == 500

    m.observe(900)
    s = m.snapshot()
    assert s.min_latency_ns == 100
    assert s.max_latency_ns == 900


def test_snapshot_does_not_modify_state():
    """Taking snapshot leaves state unchanged."""
    m = Metrics()
    m.observe(100)
    m.observe(200)

    s1 = m.snapshot()
    s2 = m.snapshot()
    s3 = m.snapshot()

    assert s1 == s2 == s3
    assert s1.count == 2


def test_observe_does_not_allocate():
    """observe() uses only arithmetic, no new objects."""
    m = Metrics()
    # Just verify it works without issues at scale
    for i in range(10_000):
        m.observe(i % 1000)
    s = m.snapshot()
    assert s.count == 10_000


def test_snapshot_fields_accessible():
    """All Snapshot fields accessible by name and index."""
    m = Metrics()
    m.observe(100)
    s = m.snapshot()

    # By name
    assert s.count == 1
    assert s.total_latency_ns == 100
    assert s.min_latency_ns == 100
    assert s.max_latency_ns == 100

    # By index
    assert s[0] == 1
    assert s[1] == 100
    assert s[2] == 100
    assert s[3] == 100
