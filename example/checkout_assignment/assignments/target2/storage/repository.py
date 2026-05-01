"""In-memory order repository — target 2."""

from __future__ import annotations

from ..models import Order


class InMemoryOrderRepository:
    def __init__(self) -> None:
        self._items: dict[str, Order] = {}

    def save(self, order: Order) -> Order:
        self._items[order.id] = order
        return order

    def get(self, order_id: str) -> Order:
        return self._items[order_id]
