"""Application service: the only layer that talks to storage.

Its collaborators are injected, so nothing here imports the repository, the
discount strategies, or the event bus.
"""

from __future__ import annotations

from typing import Annotated, Any

from pythonarchtesting.rules import (
    forbid_foreign_writes,
    forbid_imports,
    forbid_runtime_imports,
    forbid_runtime_instantiation,
    require_runtime_delegation,
)

from .models import Order

__archtest__: Annotated[
    None,
    forbid_imports(
        "sqlite3",
        "pickle",
        "repository",
        "pricing",
        "events",
        scope="module",
        mode="direct",
    ),
    forbid_runtime_imports("sqlite3", "pickle"),
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
                "repository",
                "pricing",
                "events",
                transitive=True,
                init={
                    "args": [
                        {"$new": "repository.OrderRepository"},
                        {"$new": "pricing.PercentDiscount", "args": [10]},
                        {"$new": "events.EventBus"},
                    ]
                },
                cases=[{"args": ["A1", [10.0, 20.0]]}],
            ),
            forbid_foreign_writes(
                init={
                    "args": [
                        {"$new": "repository.OrderRepository"},
                        {"$new": "pricing.PercentDiscount", "args": [10]},
                        {"$new": "events.EventBus"},
                    ]
                },
                cases=[{"args": ["A1", [10.0, 20.0]]}],
            ),
            require_runtime_delegation(
                "discount",
                member="apply",
                init={
                    "args": [
                        {"$new": "repository.OrderRepository"},
                        {"$spy": "discount"},
                        {"$new": "events.EventBus"},
                    ]
                },
                cases=[{"args": ["A1", [10.0, 20.0]]}],
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
