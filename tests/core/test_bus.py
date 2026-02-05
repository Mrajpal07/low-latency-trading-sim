import pytest
from core.bus import RingBuffer, Consumer, Overrun


def test_publish_returns_sequence():
    ring = RingBuffer[int](8)
    assert ring.publish(100) == 0
    assert ring.publish(200) == 1
    assert ring.publish(300) == 2


def test_head_tracks_publishes():
    ring = RingBuffer[int](8)
    assert ring.head() == 0
    ring.publish(1)
    assert ring.head() == 1
    ring.publish(2)
    ring.publish(3)
    assert ring.head() == 3


def test_get_retrieves_published_item():
    ring = RingBuffer[int](8)
    ring.publish(42)
    ring.publish(99)
    assert ring.get(0) == 42
    assert ring.get(1) == 99


def test_get_raises_on_unpublished_sequence():
    ring = RingBuffer[int](8)
    ring.publish(1)
    with pytest.raises(ValueError):
        ring.get(1)


def test_get_raises_on_negative_sequence():
    ring = RingBuffer[int](8)
    with pytest.raises(ValueError):
        ring.get(-1)


def test_overrun_detection():
    ring = RingBuffer[int](4)
    for i in range(10):
        ring.publish(i)
    with pytest.raises(Overrun):
        ring.get(0)


def test_capacity_wraparound():
    ring = RingBuffer[int](4)
    for i in range(10):
        ring.publish(i)
    assert ring.get(6) == 6
    assert ring.get(7) == 7
    assert ring.get(8) == 8
    assert ring.get(9) == 9


def test_consumer_starts_at_current_head():
    ring = RingBuffer[int](8)
    ring.publish(1)
    ring.publish(2)
    c = Consumer(ring)
    assert c.cursor() == 2


def test_consumer_poll_advances_cursor():
    ring = RingBuffer[int](8)
    c = Consumer(ring)
    ring.publish(10)
    ring.publish(20)
    assert c.poll() == 10
    assert c.cursor() == 1
    assert c.poll() == 20
    assert c.cursor() == 2


def test_consumer_poll_returns_none_when_empty():
    ring = RingBuffer[int](8)
    c = Consumer(ring)
    assert c.poll() is None


def test_consumer_available():
    ring = RingBuffer[int](8)
    c = Consumer(ring)
    assert c.available() == 0
    ring.publish(1)
    ring.publish(2)
    assert c.available() == 2
    c.poll()
    assert c.available() == 1


def test_independent_consumer_cursors():
    ring = RingBuffer[int](8)
    c1 = Consumer(ring)
    c2 = Consumer(ring)
    ring.publish(1)
    ring.publish(2)
    c1.poll()
    assert c1.cursor() == 1
    assert c2.cursor() == 0


def test_consumer_overrun_detection():
    ring = RingBuffer[int](4)
    c = Consumer(ring)
    for i in range(10):
        ring.publish(i)
    with pytest.raises(Overrun):
        c.poll()


def test_consumer_reset_to_head():
    ring = RingBuffer[int](4)
    c = Consumer(ring)
    for i in range(10):
        ring.publish(i)
    c.reset_to_head()
    assert c.cursor() == 10
    assert c.available() == 0


def test_producer_independence():
    ring = RingBuffer[int](4)
    c = Consumer(ring)
    for i in range(100):
        seq = ring.publish(i)
        assert seq == i
    assert ring.head() == 100


# === Additional coverage for edge cases ===


def test_capacity_one():
    """Minimal buffer size edge case."""
    ring = RingBuffer[int](1)
    assert ring.publish(10) == 0
    assert ring.get(0) == 10
    ring.publish(20)
    with pytest.raises(Overrun):
        ring.get(0)
    assert ring.get(1) == 20


def test_capacity_method():
    """capacity() returns configured size."""
    for cap in [1, 4, 16, 1024]:
        ring = RingBuffer[int](cap)
        assert ring.capacity() == cap


def test_overrun_boundary_exact():
    """Reading at exact capacity boundary (head - seq == cap) is valid."""
    ring = RingBuffer[int](4)
    for i in range(8):
        ring.publish(i)
    # head=8, seq=4, head-seq=4=cap => still valid (oldest readable)
    assert ring.get(4) == 4
    # seq=3, head-seq=5>cap => overrun
    with pytest.raises(Overrun):
        ring.get(3)


def test_multiple_complete_wraparounds():
    """Buffer correctness after many full cycles."""
    ring = RingBuffer[int](4)
    for i in range(100):
        ring.publish(i)
    # Only last 4 items readable: 96, 97, 98, 99
    for seq in range(96, 100):
        assert ring.get(seq) == seq
    with pytest.raises(Overrun):
        ring.get(95)


def test_divergent_consumer_cursors():
    """Fast and slow consumers maintain independent state."""
    ring = RingBuffer[int](8)
    fast = Consumer(ring)
    slow = Consumer(ring)

    for i in range(5):
        ring.publish(i)

    # Fast consumer reads all
    for i in range(5):
        assert fast.poll() == i
    assert fast.cursor() == 5
    assert fast.available() == 0

    # Slow consumer reads only 2
    assert slow.poll() == 0
    assert slow.poll() == 1
    assert slow.cursor() == 2
    assert slow.available() == 3

    # More publishes
    ring.publish(5)
    ring.publish(6)

    assert fast.available() == 2
    assert slow.available() == 5


def test_poll_after_reset_recovery():
    """Consumer can poll successfully after reset_to_head recovery."""
    ring = RingBuffer[int](4)
    c = Consumer(ring)

    for i in range(10):
        ring.publish(i)

    # Consumer is overrun
    with pytest.raises(Overrun):
        c.poll()

    # Recovery
    c.reset_to_head()
    assert c.cursor() == 10

    # New publishes work
    ring.publish(100)
    ring.publish(200)
    assert c.poll() == 100
    assert c.poll() == 200
    assert c.available() == 0


def test_late_joining_consumer():
    """Consumer created after publishes starts at current head."""
    ring = RingBuffer[int](8)

    for i in range(5):
        ring.publish(i)

    late = Consumer(ring)
    assert late.cursor() == 5
    assert late.available() == 0

    ring.publish(100)
    assert late.available() == 1
    assert late.poll() == 100


def test_large_sequence_numbers():
    """Correctness with large sequence numbers (no overflow issues)."""
    ring = RingBuffer[int](4)
    n = 100_000
    for i in range(n):
        ring.publish(i)

    assert ring.head() == n
    # Last 4 items
    for seq in range(n - 4, n):
        assert ring.get(seq) == seq


def test_generic_type_with_objects():
    """Buffer works with non-primitive types."""
    class Event:
        def __init__(self, val: int):
            self.val = val

    ring = RingBuffer[Event](4)
    events = [Event(i) for i in range(4)]

    for e in events:
        ring.publish(e)

    for i in range(4):
        assert ring.get(i).val == i


def test_multiple_consumers_no_interference():
    """Many consumers reading same items independently."""
    ring = RingBuffer[int](8)
    consumers = [Consumer(ring) for _ in range(10)]

    for i in range(5):
        ring.publish(i)

    # Each consumer reads all 5 items independently
    for c in consumers:
        for expected in range(5):
            assert c.poll() == expected
        assert c.available() == 0


def test_publish_never_fails():
    """Producer publish always succeeds regardless of consumer state."""
    ring = RingBuffer[int](4)
    c = Consumer(ring)

    # Publish far beyond capacity - never raises
    for i in range(10_000):
        seq = ring.publish(i)
        assert seq == i  # Always returns correct sequence
