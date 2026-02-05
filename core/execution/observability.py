from __future__ import annotations
from typing import Any, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from .executor import Ack


class ObservabilitySink(Protocol):
    def observe(self, event: Any, ack: Ack) -> None: ...


class NoOpSink:
    def observe(self, event: Any, ack: Ack) -> None:
        pass
