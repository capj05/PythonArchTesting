"""Application service: the only layer that talks to storage.

Its collaborators are injected, so nothing here imports the repository, the
discount strategies, or the event bus.
"""

from __future__ import annotations

from typing import Annotated, Any

from pythonarchtesting.rules import (
    forbid_foreign_writes,
    forbid_imports,
    forbid_runtime_instantiation,
    require_runtime_delegation,
)

from .models import Order

__archtest__: Annotated[
    None,
    forbid_imports("repository", "pricing", "events", "sqlite3", "pickle",
                   scope="module", mode="direct"),
]


class OrderService:
    def __init__(self, repository: Any, discount: Any, bus: Any) -> None:
        self._repository = repository
        self._discount = discount
        self._bus = bus

    def place(self, order_id: str, prices: list[float]) -> float:
        __archtest__: Annotated[
            None,
            forbid_runtime_instantiation(
                "repository", "pricing", "events",
                init={"args": [{"$new": "repository.OrderRepository"},
                               {"$new": "pricing.NoDiscount"},
                               {"$new": "events.EventBus"}]},
                cases=[{"args": ["A1", [10.0, 5.5]]}],
            ),
            forbid_foreign_writes(
                init={"args": [{"$new": "repository.OrderRepository"},
                               {"$new": "pricing.NoDiscount"},
                               {"$new": "events.EventBus"}]},
                cases=[{"args": ["A1", [10.0, 5.5]]}],
            ),
            require_runtime_delegation(
                "discount", member="apply",
                init={"args": [{"$new": "repository.OrderRepository"},
                               {"$spy": "discount"},
                               {"$new": "events.EventBus"}]},
                cases=[{"args": ["A1", [10.0, 5.5]]}],
            ),
        ]
        order = Order(order_id)
        for price in prices:
            order.add(price)
        order.apply_total(self._discount.apply(order.total))
        order.mark_placed()
        self._repository.save(order)
        self._bus.publish("order_placed", order.order_id)
        return order.total
