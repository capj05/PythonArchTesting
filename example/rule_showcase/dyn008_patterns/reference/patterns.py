"""Reference module for the DYN008 design-pattern showcase.

Three classic patterns, each checked on what the code does when it runs,
not on how it is spelled:

- ``AppConfig`` is a Singleton: ``AppConfig.instance()`` hands out one shared
  object (``is_runtime_singleton``).
- ``EventBus`` is an Observer subject: a listener registered with
  ``subscribe`` is called by ``publish`` and no longer after ``unsubscribe``
  (``enforce_runtime_observer``). The probe registers its own recording
  listener.
- ``PriceCalculator`` uses a Strategy: ``total`` must hand the discount to the
  injected strategy object (``require_runtime_delegation``). The case injects
  a recording spy with ``{"$spy": "strategy"}``.

None of the rules looks at results — only at identity, notification, and
delegation.
"""

from __future__ import annotations

from typing import Annotated, Any, Callable

from pythonarchtesting.rules import (
    enforce_runtime_observer,
    is_runtime_singleton,
    require_runtime_delegation,
)


class AppConfig:
    __archtest__: Annotated[
        None, is_runtime_singleton(access="instance", cases=[{"args": []}])
    ]

    _instance: "AppConfig | None" = None

    def __init__(self) -> None:
        self.values: dict[str, Any] = {}

    @classmethod
    def instance(cls) -> "AppConfig":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


class EventBus:
    __archtest__: Annotated[
        None,
        enforce_runtime_observer(
            subscribe="subscribe",
            notify="publish",
            unsubscribe="unsubscribe",
            notify_args=["order_placed"],
            cases=[{"args": []}],
        ),
    ]

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
        __archtest__: Annotated[  # noqa: F842
            None,
            require_runtime_delegation(
                "strategy",
                member="apply",
                init={"args": [{"$spy": "strategy"}]},
                cases=[{"args": [[10.0, 5.5]]}],
            ),
        ]
        return float(self.strategy.apply(sum(prices)))
