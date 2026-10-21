"""``instance()`` builds a fresh object on every call."""

from __future__ import annotations

from typing import Any, Callable


class AppConfig:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}

    @classmethod
    def instance(cls) -> "AppConfig":
        return cls()


class EventBus:
    def __init__(self) -> None:
        self._listeners: list[Callable[[str], None]] = []

    def subscribe(self, listener: Callable[[str], None]) -> None:
        self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[str], None]) -> None:
        self._listeners.remove(listener)

    def publish(self, event: str) -> None:
        for listener in list(self._listeners):
            listener(event)


class PriceCalculator:
    def __init__(self, strategy: Any) -> None:
        self.strategy = strategy

    def total(self, prices: list[float]) -> float:
        return float(self.strategy.apply(sum(prices)))
