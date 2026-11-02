"""A synchronous event bus: every subscriber of an event's name, in order."""

from __future__ import annotations

from typing import Any, Callable

Handler = Callable[[Any], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}

    def subscribe(self, name: str, handler: Handler) -> None:
        self._handlers.setdefault(name, []).append(handler)

    def unsubscribe(self, name: str, handler: Handler) -> None:
        self._handlers.get(name, []).remove(handler)

    def publish(self, event: Any) -> None:
        for handler in list(self._handlers.get(event.name, [])):
            handler(event)
