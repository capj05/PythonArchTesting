"""A synchronous event bus: every subscriber of an event's name, in order."""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import enforce_runtime_observer

from typing import Any, Callable

Handler = Callable[[Any], None]


class EventBus:
    __archtest__: Annotated[
        None,
        enforce_runtime_observer(
            subscribe="subscribe",
            notify="publish",
            unsubscribe="unsubscribe",
            subscribe_args=["booked"],
            notify_args=[
                {
                    "$new": "domain.events.AppointmentBooked",
                    "args": ["A1", "P1", "day 2"],
                }
            ],
            cases=[{"args": []}],
        ),
    ]

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}

    def subscribe(self, name: str, handler: Handler) -> None:
        self._handlers.setdefault(name, []).append(handler)

    def unsubscribe(self, name: str, handler: Handler) -> None:
        self._handlers.get(name, []).remove(handler)

    def publish(self, event: Any) -> None:
        for handler in list(self._handlers.get(event.name, [])):
            handler(event)
