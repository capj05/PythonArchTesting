"""A synchronous event bus: every subscriber of an event's name, in order."""

from __future__ import annotations
from typing import Any, Callable

Handler = Callable[[Any], None]


class EventBus:

    def __init__(self) -> None:
        raise NotImplementedError

    def subscribe(self, name: str, handler: Handler) -> None:
        raise NotImplementedError

    def unsubscribe(self, name: str, handler: Handler) -> None:
        raise NotImplementedError

    def publish(self, event: Any) -> None:
        raise NotImplementedError
