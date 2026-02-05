from typing import Any, Generic, TypeVar


T = TypeVar("T")


class Overrun(Exception):
    pass


class RingBuffer(Generic[T]):
    __slots__ = ("_buf", "_cap", "_head")

    def __init__(self, capacity: int) -> None:
        self._buf: list[T | None] = [None] * capacity
        self._cap = capacity
        self._head = 0

    def publish(self, item: T) -> int:
        seq = self._head
        self._buf[seq % self._cap] = item
        self._head = seq + 1
        return seq

    def head(self) -> int:
        return self._head

    def capacity(self) -> int:
        return self._cap

    def get(self, seq: int) -> T:
        if seq < 0:
            raise ValueError("negative sequence")
        if seq >= self._head:
            raise ValueError("sequence not yet published")
        if self._head - seq > self._cap:
            raise Overrun()
        item = self._buf[seq % self._cap]
        return item  # type: ignore


class Consumer(Generic[T]):
    __slots__ = ("_ring", "_cursor")

    def __init__(self, ring: RingBuffer[T]) -> None:
        self._ring = ring
        self._cursor = ring.head()

    def cursor(self) -> int:
        return self._cursor

    def available(self) -> int:
        return self._ring.head() - self._cursor

    def poll(self) -> T | None:
        if self._cursor >= self._ring.head():
            return None
        try:
            item = self._ring.get(self._cursor)
            self._cursor += 1
            return item
        except Overrun:
            raise

    def reset_to_head(self) -> None:
        self._cursor = self._ring.head()
