"""Publish/subscribe between the service and whoever listens."""

from __future__ import annotations
from typing import Any, Callable


class EventBus:

    def __init__(self) -> None:
        raise NotImplementedError

    def subscribe(self, listener: Callable[[str, Any], None]) -> None:
        raise NotImplementedError

    def unsubscribe(self, listener: Callable[[str, Any], None]) -> None:
        raise NotImplementedError

    def publish(self, event: str, payload: Any) -> None:
        raise NotImplementedError
