from time import perf_counter_ns

PRECISION_NS = 1


def now() -> int:
    return perf_counter_ns()


def delta(start: int, end: int) -> int:
    return end - start
