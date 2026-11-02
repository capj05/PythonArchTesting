"""Domain objects: an order changes only through its own methods.

I9: other modules use this module only through its public names, checked on
every import and on the calls made while the controller handles an order.
"""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import module_interface

__archtest__: Annotated[
    None,
    module_interface(
        entry="controller.handle_order",
        cases=[
            {
                "args": [
                    {"id": "A1", "prices": [10.0, 5.5]},
                    {
                        "$new": "service.OrderService",
                        "args": [
                            {"$new": "repository.OrderRepository"},
                            {"$new": "pricing.PercentDiscount", "args": [10]},
                            {"$new": "events.EventBus"},
                        ],
                    },
                ]
            }
        ],
    ),
]


class Order:
    def __init__(self, order_id: str) -> None:
        self.order_id = order_id
        self.items: list[float] = []
        self.total = 0.0
        self.status = "new"

    def add(self, price: float) -> None:
        self.items.append(price)
        self.total += price

    def apply_total(self, total: float) -> None:
        self.total = total

    def mark_placed(self) -> None:
        self.status = "placed"
