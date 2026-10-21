"""Publish/subscribe between the service and whoever listens."""

from __future__ import annotations

from typing import Any, Callable


class EventBus:
    def __init__(self) -> None:
        self._listeners: list[Callable[[str, Any], None]] = []

    def subscribe(self, listener: Callable[[str, Any], None]) -> None:
        self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[str, Any], None]) -> None:
        self._listeners.remove(listener)

    def publish(self, event: str, payload: Any) -> None:
        for listener in list(self._listeners):
            listener(event, payload)
