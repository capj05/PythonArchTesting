"""Application service: the only layer that talks to storage.

Its collaborators are injected, so nothing here imports the repository, the
discount strategies, or the event bus.
"""

from __future__ import annotations

from typing import Any

from .models import Order


class OrderService:
    def __init__(self, repository: Any, discount: Any, bus: Any) -> None:
        self._repository = repository
        self._discount = discount
        self._bus = bus

    def place(self, order_id: str, prices: list[float]) -> float:
        order = Order(order_id)
        for price in prices:
            order.add(price)
        order.apply_total(self._discount.apply(order.total))
        order.mark_placed()
        self._repository.save(order)
        self._bus.publish("order_placed", order.order_id)
        return order.total
