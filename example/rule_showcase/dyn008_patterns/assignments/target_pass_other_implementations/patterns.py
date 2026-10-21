"""Same patterns, other implementations.

The singleton lives in ``__new__``, the bus keeps listeners in a dict by
id and calls ``listener.__call__`` explicitly, and the calculator rounds
after the strategy has applied its discount."""

from __future__ import annotations

from typing import Any, Callable


class AppConfig:
    _shared: "AppConfig | None" = None

    def __new__(cls) -> "AppConfig":
        if cls._shared is None:
            cls._shared = super().__new__(cls)
            cls._shared.values = {}
        return cls._shared

    @classmethod
    def instance(cls) -> "AppConfig":
        return cls()


class EventBus:
    def __init__(self) -> None:
        self._listeners: dict[int, Callable[[str], None]] = {}

    def subscribe(self, listener: Callable[[str], None]) -> None:
        self._listeners[id(listener)] = listener

    def unsubscribe(self, listener: Callable[[str], None]) -> None:
        self._listeners.pop(id(listener), None)

    def publish(self, event: str) -> None:
        for listener in list(self._listeners.values()):
            listener.__call__(event)


class PriceCalculator:
    def __init__(self, strategy: Any) -> None:
        self._strategy = strategy

    def total(self, prices: list[float]) -> float:
        subtotal = 0.0
        for price in prices:
            subtotal += price
        return round(float(self._strategy.apply(subtotal)), 2)
