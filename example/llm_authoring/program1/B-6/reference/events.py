"""Publish/subscribe between the service and whoever listens."""

from __future__ import annotations

from typing import Any, Callable


from typing import Annotated

from pythonarchtesting.rules import enforce_runtime_observer


class EventBus:
    __archtest__: Annotated[
        None,
        enforce_runtime_observer(
            subscribe="subscribe", notify="publish", unsubscribe="unsubscribe",
            notify_args=["order_placed", "A1"], cases=[{"args": []}],
        ),
    ]

    def __init__(self) -> None:
        self._listeners: list[Callable[[str, Any], None]] = []

    def subscribe(self, listener: Callable[[str, Any], None]) -> None:
        self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[str, Any], None]) -> None:
        self._listeners.remove(listener)

    def publish(self, event: str, payload: Any) -> None:
        for listener in list(self._listeners):
            listener(event, payload)
