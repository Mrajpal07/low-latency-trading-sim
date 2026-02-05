from typing import NamedTuple


class Snapshot(NamedTuple):
    count: int
    total_latency_ns: int
    min_latency_ns: int
    max_latency_ns: int


class Metrics:
    __slots__ = ("_count", "_total", "_min", "_max")

    def __init__(self) -> None:
        self._count = 0
        self._total = 0
        self._min = 0
        self._max = 0

    def observe(self, latency_ns: int) -> None:
        if self._count == 0:
            self._min = latency_ns
            self._max = latency_ns
        else:
            if latency_ns < self._min:
                self._min = latency_ns
            if latency_ns > self._max:
                self._max = latency_ns
        self._count += 1
        self._total += latency_ns

    def snapshot(self) -> Snapshot:
        return Snapshot(
            count=self._count,
            total_latency_ns=self._total,
            min_latency_ns=self._min,
            max_latency_ns=self._max,
        )

    def reset(self) -> Snapshot:
        s = self.snapshot()
        self._count = 0
        self._total = 0
        self._min = 0
        self._max = 0
        return s
