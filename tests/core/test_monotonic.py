"""
Deterministic tests for core.time.monotonic

Test requirements:
- Monotonicity
- Delta correctness
- Stability under repeated calls
- Independence from wall clock

Constraints:
- No sleeps
- No timing assumptions
"""

import unittest
from unittest.mock import patch

from core.time.monotonic import now, delta, PRECISION_NS


class TestMonotonicity(unittest.TestCase):
    """Prove that successive calls never decrease."""

    def test_successive_calls_are_non_decreasing(self):
        """Each call returns a value >= the previous call."""
        previous = now()
        for _ in range(10_000):
            current = now()
            self.assertGreaterEqual(
                current,
                previous,
                f"Monotonicity violated: {current} < {previous}"
            )
            previous = current

    def test_batch_samples_are_sorted(self):
        """A batch of samples should already be sorted (non-decreasing)."""
        samples = [now() for _ in range(1_000)]
        self.assertEqual(samples, sorted(samples))

    def test_no_negative_deltas_between_successive_calls(self):
        """Delta between successive calls is never negative."""
        timestamps = [now() for _ in range(1_000)]
        for i in range(1, len(timestamps)):
            d = delta(timestamps[i - 1], timestamps[i])
            self.assertGreaterEqual(d, 0, f"Negative delta at index {i}")


class TestDeltaCorrectness(unittest.TestCase):
    """Prove delta computation is mathematically correct."""

    def test_delta_is_subtraction(self):
        """delta(start, end) == end - start for synthetic values."""
        test_cases = [
            (0, 0),
            (0, 100),
            (100, 200),
            (1_000_000_000, 1_000_000_001),
            (0, 2**63 - 1),  # Large value
        ]
        for start, end in test_cases:
            with self.subTest(start=start, end=end):
                self.assertEqual(delta(start, end), end - start)

    def test_delta_with_real_timestamps(self):
        """delta(a, b) == b - a for actual timestamps."""
        a = now()
        b = now()
        self.assertEqual(delta(a, b), b - a)

    def test_delta_allows_negative_result(self):
        """delta does not enforce ordering - returns negative if end < start."""
        self.assertEqual(delta(100, 50), -50)

    def test_delta_zero_when_equal(self):
        """delta(x, x) == 0."""
        for val in [0, 1, 1_000_000_000, 2**62]:
            with self.subTest(val=val):
                self.assertEqual(delta(val, val), 0)

    def test_delta_associativity(self):
        """delta(a, b) + delta(b, c) == delta(a, c)."""
        a, b, c = 100, 250, 500
        self.assertEqual(delta(a, b) + delta(b, c), delta(a, c))


class TestStability(unittest.TestCase):
    """Prove consistent behavior under repeated calls."""

    def test_returns_integer(self):
        """now() always returns an int."""
        for _ in range(100):
            result = now()
            self.assertIsInstance(result, int)

    def test_returns_positive(self):
        """now() returns positive values (perf_counter_ns is non-negative)."""
        for _ in range(100):
            self.assertGreaterEqual(now(), 0)

    def test_high_frequency_calls_do_not_fail(self):
        """Rapid successive calls do not raise exceptions."""
        try:
            for _ in range(100_000):
                now()
        except Exception as e:
            self.fail(f"High frequency calls raised: {e}")

    def test_delta_with_high_frequency_timestamps(self):
        """delta works correctly with rapidly generated timestamps."""
        timestamps = [now() for _ in range(10_000)]
        deltas = [delta(timestamps[i], timestamps[i + 1]) for i in range(len(timestamps) - 1)]

        # All deltas should be non-negative (monotonicity)
        self.assertTrue(all(d >= 0 for d in deltas))

        # Sum of deltas should equal total span
        total_delta = delta(timestamps[0], timestamps[-1])
        self.assertEqual(sum(deltas), total_delta)

    def test_precision_constant_is_documented(self):
        """PRECISION_NS is defined and positive."""
        self.assertIsInstance(PRECISION_NS, int)
        self.assertGreater(PRECISION_NS, 0)


class TestWallClockIndependence(unittest.TestCase):
    """Prove monotonic timing is independent from wall clock."""

    def test_unaffected_by_time_time_mock(self):
        """now() does not use time.time()."""
        with patch('time.time', side_effect=Exception("time.time called")):
            # Should not raise - now() uses perf_counter_ns, not time.time
            result = now()
            self.assertIsInstance(result, int)

    def test_unaffected_by_datetime_mock(self):
        """now() does not use datetime.datetime.now()."""
        with patch('datetime.datetime') as mock_dt:
            mock_dt.now.side_effect = Exception("datetime.now called")
            # Should not raise
            result = now()
            self.assertIsInstance(result, int)

    def test_monotonicity_unaffected_by_wall_clock_mock(self):
        """Monotonicity holds even when wall clock is mocked."""
        with patch('time.time', return_value=0):
            samples = [now() for _ in range(1_000)]
            self.assertEqual(samples, sorted(samples))

    def test_delta_is_pure_arithmetic(self):
        """delta() is pure math, no external dependencies."""
        # Completely synthetic - no time functions involved
        with patch('time.time', side_effect=Exception("time.time called")):
            with patch('time.perf_counter_ns', side_effect=Exception("perf_counter_ns called")):
                # delta should work - it's just subtraction
                self.assertEqual(delta(100, 200), 100)
                self.assertEqual(delta(500, 300), -200)


if __name__ == '__main__':
    unittest.main()
